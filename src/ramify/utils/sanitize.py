"""Output sanitization and token-reduction helpers."""

from __future__ import annotations

import re

_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from *text*."""
    return _ANSI_RE.sub("", text)


def truncate_middle(text: str, limit: int) -> str:
    """Truncate *text* to at most roughly *limit* chars, keeping head and tail.

    The middle is replaced by a marker so an LLM can see both the start
    (usually the important context) and the end (usually the error/summary).
    """
    if limit <= 0 or len(text) <= limit:
        return text
    head = limit * 2 // 3
    tail = limit - head
    omitted = len(text) - head - tail
    return f"{text[:head]}\n...[{omitted} chars truncated]...\n{text[-tail:]}"
