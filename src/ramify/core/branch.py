"""SessionBranch: instant, disposable sandbox forked from a Session."""

from __future__ import annotations

import logging

from ramify.core.session import Session
from ramify.drivers.docker import DockerDriver
from ramify.drivers.git_worktree import GitWorktreeDriver
from ramify.exceptions import BranchError, SessionClosedError

logger = logging.getLogger(__name__)


class SessionBranch(Session):
    """A sandboxed fork of a :class:`Session`, backed by a git worktree.

    File changes are fully isolated from the parent. Use
    ``parent.merge(branch)`` to write changes back, and :meth:`close`
    to destroy the worktree (and any Docker project) deterministically.
    """

    def __init__(
        self,
        parent: Session,
        name: str,
        worktree_path: str,
        git_branch: str,
        driver: GitWorktreeDriver,
        docker: DockerDriver | None,
    ) -> None:
        super().__init__(
            cwd=worktree_path,
            env=dict(parent.env),
            guard=parent.guard,
            shell=parent.shell,
            timeout=parent.timeout,
        )
        self.parent = parent
        self.name = name
        self.worktree_path = worktree_path
        self.git_branch = git_branch
        self._driver = driver
        self._docker = docker
        if docker is not None:
            self.env.update(docker.isolation_env())

    # ------------------------------------------------------------- creation

    @classmethod
    def create(cls, parent: Session, name: str, *, docker: bool = False) -> SessionBranch:
        driver = GitWorktreeDriver(parent.repo_root())
        worktree_path, git_branch = driver.create(name)
        docker_driver = DockerDriver(name) if docker else None
        branch = cls(parent, name, worktree_path, git_branch, driver, docker_driver)
        logger.info("branched session %r -> %s", name, worktree_path)
        return branch

    # ---------------------------------------------------------------- merge

    def merge_into(self, target: Session) -> None:
        """Apply this branch's file changes (incl. untracked files) to *target*."""
        if self._closed:
            raise SessionClosedError(f"Branch {self.name!r} is closed")
        patch = self._driver.diff_patch(self.worktree_path)
        if not patch.strip():
            logger.info("branch %r has no changes to merge", self.name)
            return
        target_root = target.repo_root()
        if target_root == self.worktree_path:
            raise BranchError("Cannot merge a branch into itself")
        self._driver.apply_patch(target_root, patch)
        logger.info("merged branch %r into %s", self.name, target_root)

    # ---------------------------------------------------------------- close

    def close(self) -> None:
        """Destroy the sandbox: containers first, then the worktree and branch."""
        if self._closed:
            return
        super().close()  # closes nested branches, marks self closed
        if self._docker is not None:
            self._docker.teardown(self.worktree_path)
        self._driver.remove(self.worktree_path, self.git_branch)
        self.parent._forget_branch(self)
        logger.info("closed branch %r", self.name)
