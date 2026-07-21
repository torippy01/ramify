# Ramify Kanban

最終更新: 2026-07-21

このボードは、`ROADMAP.md`とGitHub Issues/PRの実際の状態を反映します。

## Done

### Phase 1: MVP Core

- Stateful Session: `cd`、環境変数、コマンド履歴の状態保持
- Git Worktree Branching: 作成、隔離、merge、close時の削除
- Safety Guard: グローバル状態を変更するコマンドの実行前ブロック

### Phase 2.2: LLM Output Sanitization & Token Saver

- [Issue #1](https://github.com/torippy01/ramify/issues/1) — 完了
- [PR #7](https://github.com/torippy01/ramify/pull/7) — 環境変数追跡ノイズ修正
- [PR #8](https://github.com/torippy01/ramify/pull/8) — 変更ファイル検出
- [PR #9](https://github.com/torippy01/ramify/pull/9) — 出力サニタイズ・エラー要約
- [PR #10](https://github.com/torippy01/ramify/pull/10) — JSON統合・ドキュメント

実装済みのLLM向けJSON項目:

- `cmd`, `exit`, `cwd`
- サニタイズ・圧縮済みの`stdout`／`stderr`
- 失敗時の`error_tail`
- `env_changes`
- Git管理下での`modified_files`

## Next Up

### Phase 3.1: Docker Context Isolation

- [Issue #2](https://github.com/torippy01/ramify/issues/2) — Open
- `COMPOSE_PROJECT_NAME`の分離は実装済み
- 残作業: ホストポート衝突回避、Composeリソース追跡、Dockerなしでのテスト

## Backlog

### Phase 3.2: MCP Server

- [Issue #12](https://github.com/torippy01/ramify/issues/12) — Open
- `ramify_run`、`ramify_branch`、`ramify_close`、`ramify_merge`
- `ramify-mcp`のパッケージ化とPyPI公開

### GitHub Actions Claude PR Review

- [Issue #11](https://github.com/torippy01/ramify/issues/11) — Open
- Phase 3の実装完了後に着手
- fork PRのSecrets保護、最小権限、ActionのSHA固定を必須とする

## Workflow

1. `Next Up`のIssueを実装単位のDraft PRへ分割する
2. テスト・ruff・mypyを通過させる
3. PRレビュー後にmergeする
4. Issueとこのボードを更新して次のカードへ進む
