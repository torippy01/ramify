# Ramify

AIエージェント向けのターミナル実行ライブラリ。**ステートフルなセッション**と**即時ブランチ（サンドボックス）**を提供します。

- `cd` や `export` を記憶する常駐型セッション
- `git worktree` による高速なファイル隔離ブランチ（作成 → 実験 → merge / 破棄）
- `COMPOSE_PROJECT_NAME` によるDocker隔離
- `sudo` / `systemctl` / `apt` / `brew` などグローバル影響コマンドの実行前ブロック
- LLM向けにトークン最適化されたJSON結果（`to_llm_json()`）
  - ANSI・進捗ログのサニタイズ
  - 変更ファイル一覧（Gitリポジトリ内の場合）
  - 失敗時の`error_tail`

## 必要環境

- Python 3.10+
- git（ブランチ機能に必須）
- docker（Docker隔離を使う場合のみ）

## インストール

### pip

```bash
# ローカルのソースからインストール
pip install /path/to/ramify

# 開発向け（editable: ソース編集が即反映される）
pip install -e /path/to/ramify
```

### uv

```bash
# 仮想環境にインストール
uv pip install -e /path/to/ramify

# インストールせずに都度実行
uv run --no-project --with-editable /path/to/ramify python your_script.py
```

> エディタ（Pylance等）で `import ramify` が解決されない場合は、
> エディタが参照している仮想環境に `pip install -e .` されているか確認してください。

## クイックスタート

```python
from ramify import Session, GlobalStateError

s = Session(cwd="/path/to/your/git/repo")

# 1. ステートフル: cd や export が次の run() にも引き継がれる
s.run("cd src")
s.run("export API_KEY=xxx")

# 2. 結果はLLM向けのコンパクトなJSONに
result = s.run("pytest -q")
print(result.to_llm_json())   # {"cmd":"pytest -q","exit":0,"cwd":...,"stdout":...}

# 生のstdout/stderrはresultに保持され、LLM向けJSONだけが圧縮される
print(result.stdout)

# 失敗時はerror_tail、Gitリポジトリ内の変更はmodified_filesに含まれる
# {"cmd":"pytest -q","exit":1,"cwd":"...","error_tail":"...","modified_files":[...]}

# 3. 演算子でコマンド構築
(s.cat("app.log") | s.grep("ERROR")).exec()
(s.echo("hello") > "out.txt").exec()

# 4. グローバル影響コマンドはブロックされる
try:
    s.run("sudo apt-get install nginx")
except GlobalStateError as e:
    print(e)

# 5. ブランチ: git worktreeで即座にサンドボックス複製
b = s.branch("risky-experiment")          # docker=True でDocker隔離も
b.run("rm -rf tests/ && echo experiment > note.txt")   # 本筋には影響なし
s.merge(b)                                # 良ければ差分を本筋へ書き戻し
b.close()                                 # worktree・コンテナを一括削除

s.close()
```

### `CommandResult.to_llm_json()` の形式

常に出力される項目は `cmd`、`exit`、`cwd` です。以下の項目は値が存在する場合だけ出力されます。

| キー | 内容 |
| --- | --- |
| `stdout` | ANSI・進捗ノイズを除去し、長い場合は先頭と末尾を残した標準出力 |
| `stderr` | サニタイズ・圧縮された標準エラー |
| `error_tail` | 失敗時の診断用エラー末尾。stderrを優先 |
| `env_changes` | コマンド前後で変化した環境変数 |
| `modified_files` | Gitリポジトリ相対の変更ファイル一覧 |

JSONは空白を含まないコンパクト形式です。生の出力が必要な場合は、`CommandResult.stdout`と`CommandResult.stderr`を直接参照してください。

デモスクリプト: [`var/demo.py`](var/demo.py)

```bash
uv run --no-project --with-editable . python var/demo.py
```

## 開発

```bash
uv pip install -e ".[dev]"

pytest tests/          # テスト
ruff check . && ruff format .   # lint / format
mypy --strict src/     # 型チェック
```

## ディレクトリ構造

```
src/ramify/
├── core/       # Session, SessionBranch, Command（構築演算子）
├── drivers/    # Git Worktree / Docker 隔離バックエンド
├── guards/     # SafetyGuard（グローバル影響コマンド検査）
├── models/     # CommandResult
└── utils/      # 出力サニタイズ・トークン削減
```
