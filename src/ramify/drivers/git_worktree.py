"""Git worktree driver: fast filesystem isolation for session branches."""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

from ramify.exceptions import GitError

logger = logging.getLogger(__name__)


def _git(repo: str | Path, *args: str, input_text: str | None = None) -> str:
    proc = subprocess.run(  # noqa: S603
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        input=input_text,
    )
    if proc.returncode != 0:
        raise GitError(list(args), proc.stderr)
    return proc.stdout


class GitWorktreeDriver:
    """Creates and destroys lightweight `git worktree` sandboxes."""

    BRANCH_PREFIX = "ramify/"

    def __init__(self, repo_root: str) -> None:
        self.repo_root = repo_root

    def create(self, name: str) -> tuple[str, str]:
        """Create a worktree on a new branch. Returns ``(worktree_path, git_branch)``."""
        path = tempfile.mkdtemp(prefix=f"ramify-{name}-")
        git_branch = f"{self.BRANCH_PREFIX}{name}"
        # -B: reuse a stale branch from a previously crashed run
        _git(self.repo_root, "worktree", "add", "-B", git_branch, path, "HEAD")
        logger.info("created worktree %s on branch %s", path, git_branch)
        return path, git_branch

    def diff_patch(self, worktree_path: str) -> str:
        """Return a binary patch of ALL changes (incl. untracked) in the worktree."""
        _git(worktree_path, "add", "-A")
        try:
            return _git(worktree_path, "diff", "--cached", "--binary", "HEAD")
        finally:
            _git(worktree_path, "reset", "--quiet", "HEAD")

    def apply_patch(self, target_path: str, patch: str) -> None:
        if not patch.strip():
            return
        _git(target_path, "apply", "--whitespace=nowarn", "-", input_text=patch)

    def remove(self, worktree_path: str, git_branch: str) -> None:
        """Remove the worktree and its temporary branch. Idempotent."""
        try:
            _git(self.repo_root, "worktree", "remove", "--force", worktree_path)
        except GitError as exc:
            logger.warning("worktree remove failed (already gone?): %s", exc)
        try:
            _git(self.repo_root, "branch", "-D", git_branch)
        except GitError:
            pass
        try:
            _git(self.repo_root, "worktree", "prune")
        except GitError:
            pass
