# MCPサーバーの利用手順

## インストール

MCP機能はoptional dependencyです。

```bash
pip install "ramify[mcp]"
```

開発中のソースを使う場合：

```bash
uv pip install -e ".[mcp]"
```

uvでプロジェクト環境から起動する場合は、次のコマンドを使えます。

```bash
uv run --extra mcp ramify-mcp
```

## Claude Desktopへの登録

Claude Desktopの設定ファイルに、`ramify-mcp`をstdioサーバーとして登録します。

```json
{
  "mcpServers": {
    "ramify": {
      "command": "ramify-mcp"
    }
  }
}
```

実行ファイルの場所を明示する必要がある場合は、絶対パスを指定します。

```json
{
  "mcpServers": {
    "ramify": {
      "command": "/path/to/venv/bin/ramify-mcp"
    }
  }
}
```

## 基本的な利用順序

1. `ramify_run`を`cwd`付きで呼び出し、セッションを作成する
2. 戻り値の`session_id`を使って以後のコマンドを実行する
3. 実験が必要なら`ramify_branch`でブランチを作成する
4. ブランチ内では`ramify_run`に`branch_id`を渡して実行する
5. 採用する場合は`ramify_merge`、破棄する場合は`ramify_close`を呼ぶ
6. 最後に`session_id`を指定してセッションを閉じる

## 安全性

- `sudo`、`apt`、`systemctl`などのグローバル状態変更コマンドは、デフォルトでSafetyGuardにより拒否されます
- `unsafe: true`は、明示的に必要な場合だけ使用してください
- ブランチを閉じるとworktreeとDockerリソースが削除されます
- MCPサーバーはプロセス終了時に管理中のセッションをクリーンアップします

## トラブルシュート

### `ramify-mcp: command not found`

MCP optional dependencyをインストールした環境の実行ファイルを、Claude Desktopの`command`に指定してください。uvのプロジェクト環境を使う場合は、`uv run --extra mcp ramify-mcp`で起動できるため、Claude Desktopの設定では`.venv/bin/ramify-mcp`の絶対パスを指定します。

### `Unknown session_id`

セッション終了後のID、または別のMCPサーバープロセスで作成したIDは使えません。サーバー起動後に新しいセッションを作成してください。

### Gitリポジトリではないディレクトリでbranchできない

`ramify_branch`はGit worktreeを使うため、`ramify_run`の`cwd`をGitリポジトリ内に指定してください。
