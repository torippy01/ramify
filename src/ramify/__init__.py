"""Ramify: stateful terminal sessions with instant branching for AI agents."""

from __future__ import annotations

from ramify.core.session import Session
from ramify.exceptions import GlobalStateError, RamifyError
from ramify.models.result import CommandResult

__all__ = ["CommandResult", "GlobalStateError", "RamifyError", "Session"]
__version__ = "0.1.0"
