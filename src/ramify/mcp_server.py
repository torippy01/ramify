"""MCP server exposing Ramify sessions and branches to agent clients."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from ramify.core.branch import SessionBranch
from ramify.core.session import Session


class MCPRuntime:
    """Own MCP-created sessions and branches for the server lifetime."""

    def __init__(self) -> None:
        self.sessions: dict[str, Session] = {}
        self.branches: dict[str, tuple[str, SessionBranch]] = {}

    def create_session(self, cwd: str | None = None) -> str:
        path = Path(cwd or os.getcwd()).expanduser().resolve()
        if not path.is_dir():
            raise ValueError(f"Working directory does not exist: {path}")
        session_id = uuid.uuid4().hex
        self.sessions[session_id] = Session(cwd=path)
        return session_id

    def session(self, session_id: str) -> Session:
        try:
            return self.sessions[session_id]
        except KeyError as exc:
            raise ValueError(f"Unknown session_id: {session_id}") from exc

    def run(
        self,
        command: str,
        session_id: str | None = None,
        branch_id: str | None = None,
        cwd: str | None = None,
        unsafe: bool = False,
    ) -> dict[str, Any]:
        if session_id is not None and branch_id is not None:
            raise ValueError("Provide only one of session_id or branch_id")
        created = session_id is None and branch_id is None
        target: Session | SessionBranch
        if branch_id is not None:
            owner_id, target = self._branch(branch_id)
            active_id = owner_id
        else:
            active_id = session_id or self.create_session(cwd)
            target = self.session(active_id)
        result = target.run(command, unsafe=unsafe)
        payload = json.loads(result.to_llm_json())
        response: dict[str, Any] = {"session_id": active_id, "result": payload}
        if branch_id is not None:
            response["branch_id"] = branch_id
        if created:
            response["created"] = True
        return response

    def branch(self, session_id: str, name: str, docker: bool = False) -> dict[str, str]:
        session = self.session(session_id)
        branch = session.branch(name, docker=docker)
        branch_id = uuid.uuid4().hex
        self.branches[branch_id] = (session_id, branch)
        return {
            "session_id": session_id,
            "branch_id": branch_id,
            "name": name,
            "worktree_path": branch.worktree_path,
        }

    def merge(self, session_id: str, branch_id: str) -> dict[str, str]:
        owner_id, branch = self._branch(branch_id)
        if owner_id != session_id:
            raise ValueError("Branch does not belong to session_id")
        self.session(session_id).merge(branch)
        return {"session_id": session_id, "branch_id": branch_id, "merged": "true"}

    def close(self, session_id: str | None = None, branch_id: str | None = None) -> dict[str, str]:
        if (session_id is None) == (branch_id is None):
            raise ValueError("Provide exactly one of session_id or branch_id")
        if branch_id is not None:
            owner_id, branch = self._branch(branch_id)
            branch.close()
            del self.branches[branch_id]
            return {"branch_id": branch_id, "session_id": owner_id, "closed": "true"}

        assert session_id is not None
        session = self.session(session_id)
        session.close()
        for current_id, (owner_id, _) in list(self.branches.items()):
            if owner_id == session_id:
                del self.branches[current_id]
        del self.sessions[session_id]
        return {"session_id": session_id, "closed": "true"}

    def close_all(self) -> None:
        for session_id in list(self.sessions):
            self.close(session_id=session_id)

    def _branch(self, branch_id: str) -> tuple[str, SessionBranch]:
        try:
            return self.branches[branch_id]
        except KeyError as exc:
            raise ValueError(f"Unknown branch_id: {branch_id}") from exc


def build_server(runtime: MCPRuntime | None = None) -> tuple[Any, MCPRuntime]:
    """Build the FastMCP server and its lifecycle runtime."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            "MCP support is optional; install it with `pip install ramify[mcp]`."
        ) from exc

    app = runtime or MCPRuntime()
    server = FastMCP("Ramify", json_response=True)

    @server.tool()
    def ramify_run(
        command: str,
        session_id: str | None = None,
        branch_id: str | None = None,
        cwd: str | None = None,
        unsafe: bool = False,
    ) -> dict[str, Any]:
        """Run a command in a stateful session or isolated branch."""
        return app.run(
            command,
            session_id=session_id,
            branch_id=branch_id,
            cwd=cwd,
            unsafe=unsafe,
        )

    @server.tool()
    def ramify_branch(session_id: str, name: str, docker: bool = False) -> dict[str, str]:
        """Create an isolated worktree branch for a session."""
        return app.branch(session_id, name, docker=docker)

    @server.tool()
    def ramify_merge(session_id: str, branch_id: str) -> dict[str, str]:
        """Merge a branch's changes into its parent session."""
        return app.merge(session_id, branch_id)

    @server.tool()
    def ramify_close(
        session_id: str | None = None, branch_id: str | None = None
    ) -> dict[str, str]:
        """Close a branch or session and deterministically clean it up."""
        return app.close(session_id=session_id, branch_id=branch_id)

    return server, app


def main() -> None:
    """Run the MCP server over stdio for Claude Desktop and similar clients."""
    server, runtime = build_server()
    try:
        server.run(transport="stdio")
    finally:
        runtime.close_all()


if __name__ == "__main__":
    main()
