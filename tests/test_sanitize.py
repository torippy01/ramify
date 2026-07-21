from __future__ import annotations

from ramify.utils.sanitize import (
    collapse_progress_lines,
    collapse_repeated_lines,
    error_tail,
    normalize_terminal_output,
    strip_ansi,
)


def test_strip_ansi_removes_csi_and_osc_sequences() -> None:
    text = "\x1b[31mred\x1b[0m \x1b]8;;https://example.com\x07link\x1b]8;;\x07"
    assert strip_ansi(text) == "red link"


def test_normalize_terminal_output_handles_progress_carriage_returns() -> None:
    assert normalize_terminal_output("10%\r20%\r100%") == "10%\n20%\n100%"


def test_collapse_repeated_lines_preserves_context() -> None:
    result = collapse_repeated_lines("start\nsame\nsame\nsame\nend")
    assert result == "start\nsame\n...[2 repeated lines omitted]...\nsame\nend"


def test_collapse_progress_lines_keeps_final_progress_line() -> None:
    result = collapse_progress_lines(
        "Downloading one\nDownloading two\nDownloading three\nsummary"
    )
    assert result == "...[2 progress lines omitted]...\nDownloading three\nsummary"


def test_error_tail_keeps_failure_end() -> None:
    result = error_tail("context\n" + "x" * 100, 20)
    assert result.startswith("...[error tail truncated]...")
    assert result.endswith("x" * 20)
