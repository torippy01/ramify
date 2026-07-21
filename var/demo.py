"""ramify のお試しデモスクリプト.

実行方法:
    uv run --no-project --with-editable . python var/demo.py
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

from ramify import GlobalStateError, Session

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("ramify.demo")


def make_demo_repo() -> Path:
    """デモ用の使い捨て git リポジトリを作成する."""
    repo = Path(tempfile.mkdtemp(prefix="ramify-demo-")) / "app"
    repo.mkdir()
    for cmd in (
        ["init", "-b", "main"],
        ["config", "user.email", "demo@ramify.dev"],
        ["config", "user.name", "Ramify Demo"],
    ):
        subprocess.run(["git", "-C", str(repo), *cmd], check=True, capture_output=True)
    (repo / "app.py").write_text("print('v1')\n")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "init"], check=True, capture_output=True
    )
    return repo


def main() -> None:
    repo = make_demo_repo()
    with Session(cwd=repo) as s:
        logger.info("=== 1. ステートフルなセッション ===")
        s.run("mkdir sub && cd sub")
        logger.info("cd後のCWD: %s", s.cwd)
        s.run("export MY_VAR=hello")
        logger.info("env追跡: %s", s.run("echo $MY_VAR").to_llm_json())

        logger.info("=== 2. SafetyGuard ===")
        try:
            s.run("sudo rm -rf /")
        except GlobalStateError as exc:
            logger.info("ブロックされた: %s", exc)

        logger.info("=== 3. 演算子コマンド構築 ===")
        result = (s.printf("apple\\nbanana\\napricot\\n") | s.grep("ap")).exec()
        logger.info("%s", result.to_llm_json())

        logger.info("=== 4. ブランチ隔離 -> merge -> close ===")
        s.run("cd ..")
        branch = s.branch("risky-experiment")
        logger.info("worktree: %s", branch.worktree_path)
        branch.run("echo \"print('v2 experimental')\" > app.py")
        logger.info("branch側 app.py: %s", branch.run("cat app.py").stdout.strip())
        logger.info("本筋側 app.py  : %s (隔離されている)", (repo / "app.py").read_text().strip())

        s.merge(branch)
        logger.info("merge後の本筋  : %s", (repo / "app.py").read_text().strip())

        worktree_path = branch.worktree_path
        branch.close()
        logger.info("close後にworktree残存? %s", Path(worktree_path).exists())


if __name__ == "__main__":
    main()
