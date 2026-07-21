# ClaudeによるPRレビュー

Ramifyでは、GitHub ActionsからClaudeを使ったPRレビューを実行できます。

## 初期設定

リポジトリのSettings > Secrets and variables > Actionsで、次のActions secretを登録します。

```text
ANTHROPIC_API_KEY
```

ワークフローは`.github/workflows/claude-review.yml`にあります。レビューにはPRへのコメント権限、リポジトリ内容の読み取り権限、Actions実行結果の読み取り権限、Claude Actionの認証に必要なOIDCトークン発行権限を付与しています。

## 自動レビュー

同一リポジトリのブランチから作成されたPRでは、次のタイミングでレビューが起動します。

- PRの作成・再オープン
- PRへの新しいコミットのpush
- DraftからReady for reviewへの変更

forkからのPRでは、秘密情報を扱うジョブを起動しません。`pull_request`ではfork由来のSecretsが利用できないうえ、workflow内でもhead repositoryを検査して同一リポジトリ以外を除外します。fork PRをレビューする場合は、内容を確認したうえで、Secretsを使わない別の環境で手動レビューしてください。

## 手動レビュー

Actions > Claude PR review > Run workflowを選び、`pr_number`にPR番号を入力します。手動実行もリポジトリのSecretsを使うため、レビュー対象とPR内容を確認できるメンバーだけが実行してください。

## レビュー内容

Claudeには、コードを変更せず、PRへレビュー結果だけを投稿するよう指示しています。指摘には次の情報を含めます。

- severity（critical / high / medium / low）
- ファイルと行のコンテキスト
- 問題の理由
- 具体的な修正案

Actionsの失敗時は、Secrets名、権限、ワークフロー実行ログを確認してから再実行してください。APIキーそのものをログやPRコメントに貼り付けないでください。
