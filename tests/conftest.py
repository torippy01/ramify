from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ramify import Session


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    """A throwaway git repo with one commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@ramify.dev")
    _git(repo, "config", "user.name", "Ramify Test")
    (repo / "README.md").write_text("# test repo\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "initial")
    return repo


@pytest.fixture()
def session(git_repo: Path):
    s = Session(cwd=git_repo)
    yield s
    s.close()
