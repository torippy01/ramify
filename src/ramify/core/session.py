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

        delim = f"__RAMIFY_STATE_{uuid.uuid4().hex}__"
        script = f"{text}\n__ramify_rc=$?\nprintf '\\n%s\\n' {delim}\npwd\nenv\nexit $__ramify_rc\n"
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

        stdout, new_cwd, new_env = self._parse_state(proc.stdout, delim)
        env_changes = self._apply_env(new_env)
        if new_cwd and Path(new_cwd).is_dir():
            self.cwd = new_cwd

        result = CommandResult(
            command=text,
            stdout=stdout,
            stderr=proc.stderr,
            exit_code=proc.returncode,
            cwd=self.cwd,
            env_changes=env_changes,
            duration_ms=duration_ms,
        )
        self.history.append(result)
        logger.debug("ran %r -> exit=%d cwd=%s", text, result.exit_code, self.cwd)
        return result

    @staticmethod
    def _parse_state(raw_stdout: str, delim: str) -> tuple[str, str | None, dict[str, str]]:
        marker = f"\n{delim}\n"
        if marker not in raw_stdout:
            # Command exited the shell early (e.g. `exec`, `exit`): no state block.
            return raw_stdout, None, {}
        stdout, _, state = raw_stdout.rpartition(marker)
        lines = state.splitlines()
        new_cwd = lines[0] if lines else None
        new_env: dict[str, str] = {}
        for line in lines[1:]:
            key, sep, value = line.partition("=")
            if sep:
                new_env[key] = value
        return stdout, new_cwd, new_env

    def _apply_env(self, new_env: dict[str, str]) -> dict[str, str | None]:
        if not new_env:
            return {}
        changes: dict[str, str | None] = {}
        for key, value in new_env.items():
            if key in _IGNORED_ENV_KEYS:
                continue
            if self.env.get(key) != value:
                changes[key] = value
        for key in self.env:
            if key not in new_env and key not in _IGNORED_ENV_KEYS:
                changes[key] = None
        for key, value in changes.items():
            if value is None:
                self.env.pop(key, None)
            else:
                self.env[key] = value
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
