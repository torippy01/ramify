"""Custom exception hierarchy for ramify."""

from __future__ import annotations


class RamifyError(Exception):
    """Base exception for all ramify errors."""


class SessionClosedError(RamifyError):
    """Raised when an operation is attempted on a closed session or branch."""


class GlobalStateError(RamifyError):
    """Raised when a command would mutate un-sandboxable global state.

    Examples: ``sudo``, ``systemctl``, ``apt-get install``, ``brew install``.
    """

    def __init__(self, command: str, reason: str) -> None:
        self.command = command
        self.reason = reason
        super().__init__(f"Blocked global-state command: {command!r} ({reason})")


class BranchError(RamifyError):
    """Raised when branch creation, merge, or cleanup fails."""


class GitError(BranchError):
    """Raised when an underlying git operation fails."""

    def __init__(self, args: list[str], stderr: str) -> None:
        self.args_list = args
        self.stderr = stderr
        super().__init__(f"git {' '.join(args)} failed: {stderr.strip()}")
