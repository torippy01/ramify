# Ramify

AIエージェント向けのステートフルなターミナル実行と、Git worktreeによる破棄可能なサンドボックスを提供します。

## ドキュメント

- [MCPサーバーの利用手順](guide/mcp.md)
- [Core APIリファレンス](api/core.md)
- [MCP Toolsリファレンス](api/mcp.md)

## まず読むもの

通常のPython利用では、`Session`を作成してコマンドを実行します。Claude DesktopなどのMCPクライアントから利用する場合は、MCPサーバーのoptional dependencyをインストールして`ramify-mcp`を起動します。

```python
from ramify import Session

with Session(cwd="/path/to/repository") as session:
    result = session.run("pytest -q")
    print(result.to_llm_json())
```
