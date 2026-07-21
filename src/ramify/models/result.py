"""Structured command results optimized for LLM consumption."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from ramify.utils.sanitize import error_tail, summarize_output


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Result of a single command execution inside a :class:`~ramify.core.session.Session`."""

    command: str
    stdout: str
    stderr: str
    exit_code: int
    cwd: str
    env_changes: dict[str, str | None] = field(default_factory=dict)
    duration_ms: int = 0
    modified_files: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    def to_llm_json(self, max_output_chars: int = 2000) -> str:
        """Serialize to the compact, stable LLM-facing result schema.

        ``stdout``/``stderr`` are sanitized and reduced only for this JSON
        representation; the raw values remain available on the result. Empty
        optional fields are omitted, and failed commands expose an
        ``error_tail`` for efficient diagnosis.
        """
        payload: dict[str, Any] = {
            "cmd": self.command,
            "exit": self.exit_code,
            "cwd": self.cwd,
        }
        stdout = summarize_output(self.stdout, max_output_chars)
        stderr = summarize_output(self.stderr, max_output_chars)
        if stdout:
            payload["stdout"] = stdout
        if stderr:
            payload["stderr"] = stderr
        if not self.ok:
            failure_output = self.stderr or self.stdout
            tail = error_tail(failure_output, max_output_chars)
            if tail:
                payload["error_tail"] = tail
        if self.env_changes:
            payload["env_changes"] = self.env_changes
        if self.modified_files:
            payload["modified_files"] = list(self.modified_files)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
