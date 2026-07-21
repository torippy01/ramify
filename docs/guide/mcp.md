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

シェルからuvのプロジェクト環境で起動する場合は、次のコマンドを使えます。

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

GitHub上のソースを直接使う場合は、`uvx`を指定できます。

```json
{
  "mcpServers": {
    "ramify": {
      "command": "/Users/torip/.local/bin/uvx",
      "args": [
        "--from",
        "ramify[mcp] @ git+https://github.com/torippy01/ramify",
        "ramify-mcp"
      ]
    }
  }
}
```

## stdioサーバーを端末で直接起動する場合

`ramify-mcp`は人間が対話入力するCLIではなく、AIクライアントとJSON-RPCをstdioで交換するサーバーです。端末で単独起動して空行を入力すると、`Invalid JSON`や`EOF while parsing`が表示されます。これはパッケージのインストール失敗ではありません。

通常はClaude CodeやClaude DesktopなどのMCP設定から起動してください。動作確認では、MCPクライアントから`initialize`と`tools/list`を送信し、`ramify_run`、`ramify_branch`、`ramify_merge`、`ramify_close`が返ることを確認します。

## このリポジトリでClaude Codeから使う

リポジトリルートの`.mcp.json`に設定済みです。Claude Codeをこのディレクトリで起動すると、`ramify`サーバーがプロジェクトMCPとして認識されます。

```bash
claude
```

Claude Code内では`/mcp`で接続状態を確認できます。`ramify_run`、`ramify_branch`、`ramify_merge`、`ramify_close`の4ツールが表示されれば利用可能です。初回はプロジェクトMCPサーバーの起動許可を求められる場合があります。

設定は`uv run --extra mcp ramify-mcp`で起動するため、プロジェクトの`.venv`を手動で有効化する必要はありません。

Claude Desktopのようにコマンドを直接起動するクライアントでは、MCPをインストールした環境の実行ファイルを絶対パスで指定します。uvのプロジェクト環境なら、通常は`.venv/bin/ramify-mcp`です。

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

シェルでは`uv run --extra mcp ramify-mcp`を使い、Claude Desktopでは`.venv/bin/ramify-mcp`などインストール済み環境の絶対パスを`command`に指定してください。

### `Unknown session_id`

セッション終了後のID、または別のMCPサーバープロセスで作成したIDは使えません。サーバー起動後に新しいセッションを作成してください。

### Gitリポジトリではないディレクトリでbranchできない

`ramify_branch`はGit worktreeを使うため、`ramify_run`の`cwd`をGitリポジトリ内に指定してください。
