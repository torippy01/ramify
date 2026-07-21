from __future__ import annotations

import pytest

pytest.importorskip("mcp")

from ramify.mcp_server import MCPRuntime, build_server


def test_runtime_run_creates_and_reuses_session(tmp_path) -> None:
    runtime = MCPRuntime()
    first = runtime.run("export MCP_TEST=ok; printf '%s' \"$MCP_TEST\"", cwd=str(tmp_path))
    second = runtime.run("printf '%s' \"$MCP_TEST\"", session_id=first["session_id"])

    assert first["created"] is True
    assert first["result"]["stdout"] == "ok"
    assert second["result"]["stdout"] == "ok"
    runtime.close_all()


def test_runtime_branch_run_merge_and_close(git_repo) -> None:
    runtime = MCPRuntime()
    session_id = runtime.create_session(str(git_repo))
    branch = runtime.branch(session_id, "mcp-feature")
    runtime.run("echo mcp > created.txt", branch_id=branch["branch_id"])
    runtime.merge(session_id, branch["branch_id"])
    runtime.close(branch_id=branch["branch_id"])

    assert (git_repo / "created.txt").read_text().strip() == "mcp"
    runtime.close(session_id=session_id)


def test_build_server_registers_required_tools() -> None:
    server, runtime = build_server()
    tools = set(server._tool_manager._tools)
    assert tools == {"ramify_run", "ramify_branch", "ramify_merge", "ramify_close"}
    runtime.close_all()
