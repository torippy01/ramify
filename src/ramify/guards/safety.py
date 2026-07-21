"""SafetyGuard: detect commands that mutate un-sandboxable global state."""

from __future__ import annotations

import logging
import re
import shlex

from ramify.exceptions import GlobalStateError

logger = logging.getLogger(__name__)

# Commands whose effects escape any worktree/container sandbox.
GLOBAL_STATE_COMMANDS: dict[str, str] = {
    "sudo": "privilege escalation affects the whole host",
    "su": "privilege escalation affects the whole host",
    "systemctl": "manages host-wide services",
    "service": "manages host-wide services",
    "launchctl": "manages host-wide macOS services",
    "apt": "modifies system package state",
    "apt-get": "modifies system package state",
    "dpkg": "modifies system package state",
    "yum": "modifies system package state",
    "dnf": "modifies system package state",
    "pacman": "modifies system package state",
    "brew": "modifies system package state",
    "shutdown": "halts or reboots the host",
    "reboot": "halts or reboots the host",
    "halt": "halts the host",
    "mkfs": "formats block devices",
    "mount": "alters host filesystem mounts",
    "umount": "alters host filesystem mounts",
}

# Transparent wrappers: inspect the command that follows them.
_WRAPPERS = frozenset({"command", "nohup", "time", "nice", "xargs", "exec"})

_SEGMENT_SPLIT_RE = re.compile(r"(?:\|\|?|&&|;|\n)")
_ENV_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


class SafetyGuard:
    """Inspects shell command lines and raises :class:`GlobalStateError`
    when a segment would mutate global state that cannot be sandboxed."""

    def __init__(self, extra_blocked: dict[str, str] | None = None) -> None:
        self._blocked = dict(GLOBAL_STATE_COMMANDS)
        if extra_blocked:
            self._blocked.update(extra_blocked)

    def check(self, command: str) -> None:
        """Raise :class:`GlobalStateError` if *command* contains a blocked program."""
        for segment in _SEGMENT_SPLIT_RE.split(command):
            segment = segment.strip()
            if not segment:
                continue
            try:
                tokens = shlex.split(segment)
            except ValueError:
                # Unparseable (e.g. unbalanced quotes from a split heredoc);
                # fall back to a whitespace split for inspection.
                tokens = segment.split()
            for token in tokens:
                if _ENV_ASSIGN_RE.match(token):
                    continue  # leading VAR=value assignments
                name = token.rsplit("/", 1)[-1]
                if name in self._blocked:
                    logger.warning("Blocked global-state command: %s", segment)
                    raise GlobalStateError(command, self._blocked[name])
                if name in _WRAPPERS or name == "env":
                    continue  # look at the wrapped command
                break  # first real program in this segment is safe

    def is_safe(self, command: str) -> bool:
        try:
            self.check(command)
        except GlobalStateError:
            return False
        return True
