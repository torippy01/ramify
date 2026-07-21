"""Output sanitization and token-reduction helpers."""

from __future__ import annotations

import re

_CSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_OSC_RE = re.compile(r"\x1b\][^\x07]*(?:\x07|\x1b\\)")
_PROGRESS_RE = re.compile(
    r"^\s*(?:Downloading|Installing|Collecting|Resolving|Building|Progress|npm\s+(?:http|info))\b",
    re.IGNORECASE,
)


def strip_ansi(text: str) -> str:
    """Remove CSI and OSC terminal escape sequences from *text*."""
    return _CSI_RE.sub("", _OSC_RE.sub("", text))


def normalize_terminal_output(text: str) -> str:
    """Turn carriage-return progress updates into ordinary lines."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def collapse_repeated_lines(text: str, minimum: int = 3) -> str:
    """Collapse consecutive identical lines while retaining their context."""
    lines = text.splitlines()
    compacted: list[str] = []
    index = 0
    while index < len(lines):
        end = index + 1
        while end < len(lines) and lines[end] == lines[index]:
            end += 1
        count = end - index
        compacted.append(lines[index])
        if count >= minimum:
            compacted.append(f"...[{count - 1} repeated lines omitted]...")
            compacted.append(lines[end - 1])
        index = end
    return "\n".join(compacted)


def collapse_progress_lines(text: str, minimum: int = 3) -> str:
    """Collapse consecutive package-manager/download progress lines."""
    lines = text.splitlines()
    compacted: list[str] = []
    index = 0
    while index < len(lines):
        if not _PROGRESS_RE.match(lines[index]):
            compacted.append(lines[index])
            index += 1
            continue
        end = index + 1
        while end < len(lines) and _PROGRESS_RE.match(lines[end]):
            end += 1
        count = end - index
        if count >= minimum:
            compacted.append(f"...[{count - 1} progress lines omitted]...")
            compacted.append(lines[end - 1])
        else:
            compacted.extend(lines[index:end])
        index = end
    return "\n".join(compacted)


def summarize_output(text: str, limit: int) -> str:
    """Sanitize and compact normal command output before truncation."""
    cleaned = normalize_terminal_output(strip_ansi(text)).rstrip()
    cleaned = collapse_progress_lines(cleaned)
    cleaned = collapse_repeated_lines(cleaned)
    return truncate_middle(cleaned, limit)


def error_tail(text: str, limit: int) -> str:
    """Return a sanitized tail of failure output, preserving the final lines."""
    cleaned = normalize_terminal_output(strip_ansi(text)).rstrip()
    if len(cleaned) <= limit:
        return cleaned
    return f"...[error tail truncated]...\n{cleaned[-limit:]}"


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
