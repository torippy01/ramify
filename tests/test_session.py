from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from ramify import GlobalStateError, Session
from ramify.core.command import Command


class TestStatefulness:
    def test_remembers_cd(self, session: Session, git_repo: Path) -> None:
        (git_repo / "sub").mkdir()
        session.run("cd sub")
        assert session.cwd == str((git_repo / "sub").resolve())
        result = session.run("pwd")
        assert result.stdout.strip().endswith("sub")

    def test_cd_persists_across_multiple_runs(self, session: Session, git_repo: Path) -> None:
        (git_repo / "a" / "b").mkdir(parents=True)
        session.run("cd a")
        session.run("cd b")
        assert session.cwd == str((git_repo / "a" / "b").resolve())

    def test_tracks_env_changes(self, session: Session) -> None:
        result = session.run("export RAMIFY_TEST_VAR=hello")
        assert result.env_changes.get("RAMIFY_TEST_VAR") == "hello"
        assert session.env["RAMIFY_TEST_VAR"] == "hello"
        # visible in the next command
        result2 = session.run("printf '%s' \"$RAMIFY_TEST_VAR\"")
        assert result2.stdout == "hello"

    def test_noop_command_has_no_environment_noise(self, session: Session) -> None:
        result = session.run("echo hello")
        assert result.env_changes == {}

    def test_tracks_environment_values_with_special_characters(self, session: Session) -> None:
        result = session.run("export RAMIFY_SPECIAL=$'left=right\\nsecond-line'")
        assert result.env_changes["RAMIFY_SPECIAL"] == "left=right\nsecond-line"
        assert session.env["RAMIFY_SPECIAL"] == "left=right\nsecond-line"

    def test_unset_env_is_tracked(self, session: Session) -> None:
        session.run("export RAMIFY_GONE=1")
        result = session.run("unset RAMIFY_GONE")
        assert result.env_changes.get("RAMIFY_GONE", "missing") is None
        assert "RAMIFY_GONE" not in session.env


class TestResult:
    def test_exit_code_and_stderr(self, session: Session) -> None:
        result = session.run("echo out; echo err >&2; exit 3")
        assert result.exit_code == 3
        assert not result.ok
        assert result.stdout.strip() == "out"
        assert result.stderr.strip() == "err"

    def test_to_llm_json_is_compact(self, session: Session) -> None:
        result = session.run("echo hello")
        payload = json.loads(result.to_llm_json())
        assert payload["exit"] == 0
        assert payload["stdout"] == "hello"
        assert "stderr" not in payload  # empty fields dropped
        assert "env_changes" not in payload

    def test_to_llm_json_truncates_long_output(self, session: Session) -> None:
        result = session.run("seq 1 5000")
        payload = json.loads(result.to_llm_json(max_output_chars=500))
        assert "chars truncated" in payload["stdout"]
        assert len(payload["stdout"]) < 700

    def test_reports_created_modified_and_deleted_files(
        self, session: Session, git_repo: Path
    ) -> None:
        (git_repo / "tracked.txt").write_text("before\n")
        subprocess.run(["git", "-C", str(git_repo), "add", "tracked.txt"], check=True)
        subprocess.run(
            ["git", "-C", str(git_repo), "commit", "-m", "add tracked file"], check=True
        )

        result = session.run(
            "printf 'after\\n' > tracked.txt; printf 'new\\n' > created.txt; rm README.md"
        )

        assert result.modified_files == ("README.md", "created.txt", "tracked.txt")

    def test_reports_both_paths_for_rename(self, session: Session, git_repo: Path) -> None:
        result = session.run("mv README.md renamed.md")
        assert result.modified_files == ("README.md", "renamed.md")

    def test_modified_files_are_optional_outside_git(self, tmp_path: Path) -> None:
        session = Session(cwd=tmp_path)
        try:
            result = session.run("touch created.txt")
            assert result.modified_files == ()
        finally:
            session.close()


class TestCommandBuilder:
    def test_getattr_builds_command(self, session: Session) -> None:
        cmd = session.git("status")
        assert isinstance(cmd, Command)
        assert cmd.text == "git status"

    def test_pipe_operator(self, session: Session) -> None:
        cmd = session.printf("a\\nb\\nab\\n") | session.grep("ab")
        assert cmd.text == "printf 'a\\nb\\nab\\n' | grep ab"
        result = cmd.exec()
        assert result.stdout.strip() == "ab"

    def test_redirect_operator(self, session: Session, git_repo: Path) -> None:
        (session.echo("redirected") > "out.txt").exec()
        assert (git_repo / "out.txt").read_text().strip() == "redirected"


class TestSafetyGuard:
    @pytest.mark.parametrize(
        "command",
        [
            "sudo rm -rf /",
            "systemctl restart nginx",
            "apt-get install curl",
            "brew install jq",
            "echo hi && sudo reboot",
            "FOO=1 sudo ls",
        ],
    )
    def test_blocks_global_commands(self, session: Session, command: str) -> None:
        with pytest.raises(GlobalStateError):
            session.run(command)

    def test_allows_safe_commands(self, session: Session) -> None:
        assert session.run("echo 'talk about sudo safely'").ok

    def test_unsafe_flag_bypasses_guard(self, session: Session) -> None:
        # guard would block this, unsafe=True lets it through (command itself is harmless)
        result = session.run("sudo -h > /dev/null 2>&1; true", unsafe=True)
        assert result.ok
