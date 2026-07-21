from __future__ import annotations

import subprocess
from pathlib import Path

from ramify import Session
from ramify.core.branch import SessionBranch


def _worktree_list(repo: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "worktree", "list"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


class TestBranchIsolation:
    def test_branch_starts_with_parent_files(self, session: Session) -> None:
        branch = session.branch("exp1")
        try:
            assert isinstance(branch, SessionBranch)
            assert Path(branch.worktree_path, "README.md").is_file()
            assert branch.worktree_path != session.cwd
        finally:
            branch.close()

    def test_files_are_fully_isolated(self, session: Session, git_repo: Path) -> None:
        branch = session.branch("exp2")
        try:
            branch.run("echo risky > risky.txt")
            branch.run("rm README.md")
            # parent untouched
            assert not (git_repo / "risky.txt").exists()
            assert (git_repo / "README.md").is_file()
            # branch sees its own changes
            assert Path(branch.worktree_path, "risky.txt").is_file()
            assert not Path(branch.worktree_path, "README.md").exists()
        finally:
            branch.close()

    def test_docker_isolation_env(self, session: Session) -> None:
        branch = session.branch("exp3", docker=True)
        try:
            assert branch.env["COMPOSE_PROJECT_NAME"].startswith("ramify-exp3-")
            assert "COMPOSE_PROJECT_NAME" not in session.env
            assert branch.env["RAMIFY_PORT_BASE"].isdigit()
        finally:
            branch.close()


class TestBranchCleanup:
    def test_close_removes_worktree_and_branch(self, session: Session, git_repo: Path) -> None:
        branch = session.branch("gone")
        path = branch.worktree_path
        assert path in _worktree_list(git_repo)
        branch.close()
        assert not Path(path).exists()
        assert path not in _worktree_list(git_repo)
        branches = subprocess.run(
            ["git", "-C", str(git_repo), "branch", "--list", "ramify/gone"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        assert branches.strip() == ""

    def test_close_is_idempotent(self, session: Session) -> None:
        branch = session.branch("twice")
        branch.close()
        branch.close()  # must not raise

    def test_session_close_cleans_branches(self, git_repo: Path) -> None:
        session = Session(cwd=git_repo)
        branch = session.branch("orphan")
        path = branch.worktree_path
        session.close()
        assert not Path(path).exists()


class TestMerge:
    def test_merge_writes_changes_back(self, session: Session, git_repo: Path) -> None:
        branch = session.branch("feature")
        try:
            branch.run("echo new-file > created.txt")
            branch.run("echo appended >> README.md")
            session.merge(branch)
        finally:
            branch.close()
        assert (git_repo / "created.txt").read_text().strip() == "new-file"
        assert "appended" in (git_repo / "README.md").read_text()

    def test_merge_with_no_changes_is_noop(self, session: Session, git_repo: Path) -> None:
        before = sorted(p.name for p in git_repo.iterdir())
        branch = session.branch("idle")
        try:
            session.merge(branch)
        finally:
            branch.close()
        assert sorted(p.name for p in git_repo.iterdir()) == before

    def test_branch_survives_after_merge(self, session: Session) -> None:
        branch = session.branch("cont")
        try:
            branch.run("echo v1 > file.txt")
            session.merge(branch)
            result = branch.run("cat file.txt")
            assert result.stdout.strip() == "v1"
        finally:
            branch.close()
