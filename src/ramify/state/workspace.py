"""Git-backed workspace snapshots for command side-effect reporting."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class WorkspaceSnapshot:
    """A lightweight snapshot of the Git status of a workspace.

    ``root`` is ``None`` when the workspace is not inside a Git repository or
    Git is unavailable. In that case the snapshot is intentionally inert so
    command execution remains useful outside Git repositories.
    """

    root: str | None = None
    statuses: dict[str, str] = field(default_factory=dict)

    @classmethod
    def capture(cls, cwd: str | Path) -> WorkspaceSnapshot:
        """Capture tracked, untracked, deleted, and renamed workspace paths."""
        root_proc = subprocess.run(  # noqa: S603
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            capture_output=True,
            text=True,
        )
        if root_proc.returncode != 0:
            return cls()

        root = root_proc.stdout.strip()
        status_proc = subprocess.run(  # noqa: S603
            ["git", "status", "--porcelain=v1", "--untracked-files=all", "-z"],
            cwd=root,
            capture_output=True,
            text=True,
        )
        if status_proc.returncode != 0:
            return cls()
        return cls(root=root, statuses=cls._parse_status(status_proc.stdout))

    def changed_files_since(self, after: WorkspaceSnapshot) -> tuple[str, ...]:
        """Return repository-relative paths whose status changed between snapshots."""
        if self.root is None or after.root is None or self.root != after.root:
            return ()
        paths = {
            path
            for path in self.statuses.keys() | after.statuses.keys()
            if self.statuses.get(path) != after.statuses.get(path)
        }
        return tuple(sorted(paths))

    @staticmethod
    def _parse_status(raw: str) -> dict[str, str]:
        """Parse porcelain-v1 NUL-delimited status output.

        Rename/copy records carry a second path. Both paths are reported so
        callers can explain the complete filesystem change to an agent.
        """
        statuses: dict[str, str] = {}
        records = raw.split("\0")
        index = 0
        while index < len(records):
            record = records[index]
            index += 1
            if not record or len(record) < 4:
                continue
            status = record[:2]
            path = record[3:]
            statuses[path] = status
            if "R" in status or "C" in status:
                if index < len(records) and records[index]:
                    statuses[records[index]] = status
                    index += 1
        return statuses
