"""Structured command results optimized for LLM consumption."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from ramify.utils.sanitize import strip_ansi, truncate_middle


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Result of a single command execution inside a :class:`~ramify.core.session.Session`."""

    command: str
    stdout: str
    stderr: str
    exit_code: int
    cwd: str
    env_changes: dict[str, str | None] = field(default_factory=dict)
    modified_files: tuple[str, ...] = ()
    duration_ms: int = 0

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    def to_llm_json(self, max_output_chars: int = 2000) -> str:
        """Serialize to compact JSON, dropping empty fields and truncating long output.

        Designed to minimize tokens: no whitespace, no empty values, ANSI
        codes stripped, and long output truncated in the middle.
        """
        payload: dict[str, Any] = {
            "cmd": self.command,
            "exit": self.exit_code,
            "cwd": self.cwd,
        }
        stdout = truncate_middle(strip_ansi(self.stdout).rstrip(), max_output_chars)
        stderr = truncate_middle(strip_ansi(self.stderr).rstrip(), max_output_chars)
        if stdout:
            payload["stdout"] = stdout
        if stderr:
            payload["stderr"] = stderr
        if self.env_changes:
            payload["env_changes"] = self.env_changes
        if self.modified_files:
            payload["modified_files"] = list(self.modified_files)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
