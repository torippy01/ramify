"""Stateful shell session tracking CWD and environment across commands."""

from __future__ import annotations

import logging
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ramify.core.command import Command
from ramify.exceptions import RamifyError, SessionClosedError
from ramify.guards.safety import SafetyGuard
from ramify.models.result import CommandResult
from ramify.state.workspace import WorkspaceSnapshot

if TYPE_CHECKING:
    from ramify.core.branch import SessionBranch

logger = logging.getLogger(__name__)

# Session-internal variables that must never leak into env_changes noise.
_IGNORED_ENV_KEYS = frozenset({"_", "SHLVL", "PWD", "OLDPWD"})


class Session:
    """A resident shell session for AI agents.

    Every :meth:`run` call executes in a fresh subprocess, but CWD and
    environment mutations (``cd``, ``export``) are captured and replayed,
    so the session *behaves* like a persistent shell without keeping a
    zombie-prone long-lived process around.
    """

    def __init__(
        self,
        cwd: str | Path | None = None,
        env: dict[str, str] | None = None,
        guard: SafetyGuard | None = None,
        shell: str = "/bin/bash",
        timeout: float = 120.0,
    ) -> None:
        self.cwd = str(Path(cwd or os.getcwd()).resolve())
        self.env: dict[str, str] = dict(env) if env is not None else dict(os.environ)
        self.guard = guard if guard is not None else SafetyGuard()
        self.shell = shell
        self.timeout = timeout
        self.history: list[CommandResult] = []
        self._closed = False
        self._branches: list[SessionBranch] = []

    # ------------------------------------------------------------------ run

    def run(
        self,
        command: str | Command,
        *,
        unsafe: bool = False,
        timeout: float | None = None,
    ) -> CommandResult:
        """Execute *command*, tracking CWD/env changes into the session.

        Set ``unsafe=True`` to bypass the :class:`SafetyGuard`.
        """
        if self._closed:
            raise SessionClosedError("Session is closed")
        text = command.text if isinstance(command, Command) else command
        if not unsafe:
            self.guard.check(text)
        workspace_before = WorkspaceSnapshot.capture(self.cwd)

        # Capture the environment in the same shell immediately before and
        # after the command.  Comparing the post-command environment with
        # ``self.env`` is noisy because shell startup (and test runners) may
        # add variables between Session construction and execution.
        before_delim = f"__RAMIFY_BEFORE_{uuid.uuid4().hex}__"
        command_delim = f"__RAMIFY_COMMAND_{uuid.uuid4().hex}__"
        after_delim = f"__RAMIFY_AFTER_{uuid.uuid4().hex}__"
        script = (
            f"printf '\\n%s\\n' {before_delim}\n"
            f"env -0\n"
            f"printf '\\n%s\\n' {command_delim}\n"
            f"{text}\n"
            f"__ramify_rc=$?\n"
            f"printf '\\n%s\\n' {after_delim}\n"
            f"pwd\n"
            f"env -0\n"
            f"exit $__ramify_rc\n"
        )
        started = time.monotonic()
        proc = subprocess.run(  # noqa: S603
            [self.shell, "-c", script],
            cwd=self.cwd,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=timeout if timeout is not None else self.timeout,
        )
        duration_ms = int((time.monotonic() - started) * 1000)

        stdout, before_env, new_cwd, new_env = self._parse_state(
            proc.stdout, before_delim, command_delim, after_delim
        )
        env_changes = self._apply_env(before_env, new_env)
        if new_cwd and Path(new_cwd).is_dir():
            self.cwd = new_cwd
        workspace_after = WorkspaceSnapshot.capture(self.cwd)
        modified_files = workspace_before.changed_files_since(workspace_after)

        result = CommandResult(
            command=text,
            stdout=stdout,
            stderr=proc.stderr,
            exit_code=proc.returncode,
            cwd=self.cwd,
            env_changes=env_changes,
            modified_files=modified_files,
            duration_ms=duration_ms,
        )
        self.history.append(result)
        logger.debug("ran %r -> exit=%d cwd=%s", text, result.exit_code, self.cwd)
        return result

    @staticmethod
    def _parse_state(
        raw_stdout: str,
        before_delim: str,
        command_delim: str,
        after_delim: str,
    ) -> tuple[str, dict[str, str], str | None, dict[str, str]]:
        before_marker = f"\n{before_delim}\n"
        command_marker = f"\n{command_delim}\n"
        after_marker = f"\n{after_delim}\n"

        before_stdout, before_sep, before_state = raw_stdout.partition(before_marker)
        if not before_sep:
            # Command exited the shell before the state block (e.g. `exec`).
            return raw_stdout, {}, None, {}

        before_raw, command_sep, command_stdout = before_state.partition(command_marker)
        if not command_sep:
            return before_stdout, {}, None, {}

        stdout, after_sep, after_state = command_stdout.partition(after_marker)
        if not after_sep:
            return before_stdout + stdout, {}, None, {}

        new_cwd, _, after_env_raw = after_state.partition("\n")
        return (
            stdout,
            Session._parse_env0(before_raw),
            new_cwd or None,
            Session._parse_env0(after_env_raw),
        )

    @staticmethod
    def _parse_env0(raw: str) -> dict[str, str]:
        values: dict[str, str] = {}
        for entry in raw.split("\0"):
            key, sep, value = entry.partition("=")
            if sep:
                values[key] = value
        return values

    def _apply_env(
        self, before_env: dict[str, str], after_env: dict[str, str]
    ) -> dict[str, str | None]:
        if not before_env and not after_env:
            return {}
        changes: dict[str, str | None] = {}
        for key, value in after_env.items():
            if key in _IGNORED_ENV_KEYS:
                continue
            if before_env.get(key) != value:
                changes[key] = value
        for key in before_env:
            if key not in after_env and key not in _IGNORED_ENV_KEYS:
                changes[key] = None
        for key, new_value in changes.items():
            if new_value is None:
                self.env.pop(key, None)
            else:
                self.env[key] = new_value
        return changes

    # ------------------------------------------------- dynamic command builder

    def __getattr__(self, name: str) -> Command:
        if name.startswith("_"):
            raise AttributeError(name)
        # docker_compose -> docker-compose, apt_get -> apt-get
        return Command(self, name.replace("_", "-"))

    # ------------------------------------------------------------ branching

    def branch(self, name: str, *, docker: bool = False) -> SessionBranch:
        """Fork this session into an isolated git-worktree sandbox."""
        from ramify.core.branch import SessionBranch

        branch = SessionBranch.create(self, name, docker=docker)
        self._branches.append(branch)
        return branch

    def merge(self, branch: SessionBranch) -> None:
        """Write the branch's file changes back into this session's worktree."""
        branch.merge_into(self)

    def repo_root(self) -> str:
        """Return the git repository root for the session CWD."""
        proc = subprocess.run(  # noqa: S603
            ["git", "rev-parse", "--show-toplevel"],
            cwd=self.cwd,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise RamifyError(f"Not inside a git repository: {self.cwd}")
        return proc.stdout.strip()

    # ------------------------------------------------------------- lifecycle

    def close(self) -> None:
        """Close the session and clean up any live branches."""
        for branch in list(self._branches):
            branch.close()
        self._branches.clear()
        self._closed = True

    def _forget_branch(self, branch: Any) -> None:
        if branch in self._branches:
            self._branches.remove(branch)

    def __enter__(self) -> Session:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
