# MCP Tools API

MCPサーバーはstdio transportで起動し、以下の4つのtoolを公開します。

## `ramify_run`

コマンドをステートフルなセッション、またはworktreeブランチ内で実行します。

| 引数 | 型 | 必須 | 説明 |
| --- | --- | --- | --- |
| `command` | `string` | Yes | 実行するshellコマンド |
| `session_id` | `string` | No | 既存セッションのID |
| `branch_id` | `string` | No | 既存ブランチのID |
| `cwd` | `string` | No | 新規セッションの作業ディレクトリ |
| `unsafe` | `boolean` | No | SafetyGuardを迂回するか |

`session_id`と`branch_id`を省略すると新規セッションを作成します。

## `ramify_branch`

| 引数 | 型 | 必須 | 説明 |
| --- | --- | --- | --- |
| `session_id` | `string` | Yes | 親セッションのID |
| `name` | `string` | Yes | ブランチ名 |
| `docker` | `boolean` | No | Docker Compose分離を有効にするか |

戻り値には`branch_id`、`session_id`、worktreeのパスが含まれます。

## `ramify_merge`

`branch_id`の変更を、指定した`session_id`へ適用します。ブランチはmerge後も利用でき、不要になった時点で`ramify_close`を呼びます。

| 引数 | 型 | 必須 |
| --- | --- | --- |
| `session_id` | `string` | Yes |
| `branch_id` | `string` | Yes |

## `ramify_close`

セッションまたはブランチを閉じます。`session_id`と`branch_id`のどちらか一方だけを指定します。

| 引数 | 型 | 必須 |
| --- | --- | --- |
| `session_id` | `string` | 条件付き |
| `branch_id` | `string` | 条件付き |

セッションを閉じると、そのセッションが管理する未終了ブランチも閉じられます。
