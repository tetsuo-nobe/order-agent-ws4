# 注文管理エージェント（order-agent-ws4）

Web のチャットで、製品情報の照会、通貨換算（USD / JPY）、注文見積り書（PDF）の作成とダウンロードができる
AI エージェントです。tool / agent / frontend を 1 つのリポジトリで管理するモノリポ構成です。

```
[ブラウザ (React SPA / Amplify Hosting)]
   │ ① Cognito でログイン → アクセストークン
   │ ② Bearer トークンで直接呼び出し（SSE ストリーミング）
   ▼
[AgentCore Runtime (Strands Agents, Python)]  … JWT 認証（Cognito）
   │  get_product_info / convert_currency … ローカルツール（@tool）
   │  create_quote … AgentCore Gateway 経由（IAM / SigV4）
   ▼
[AgentCore Gateway (MCP)] ──▶ [Lambda (PDF 生成)] ──▶ [S3（署名付きURLでダウンロード）]
```

## フォルダ構成

| フォルダ | 内容 | デプロイ |
|---|---|---|
| `tool/` | Cognito ユーザープール、見積書 PDF の Lambda、S3、AgentCore Gateway | AWS SAM（`sam build` → `sam deploy`） |
| `agent/order4/` | AgentCore CLI プロジェクト（エージェントのコードは `app/order/`） | `agentcore deploy` |
| `frontend/` | React + Vite のチャット UI | Amplify Hosting（`frontend/infra/amplify-hosting.yaml`） |
| `amplify.yml` | Amplify Hosting のビルド設定（モノリポ形式、`appRoot: frontend`） | — |

各フォルダの README に詳しい手順があります。

## デプロイの順番

1. `tool/` を SAM でデプロイ（Outputs を後続で使用）
2. `agent/order4/` を `agentcore deploy`（`agentcore.json` に tool の Outputs を設定済み）
3. `frontend/` を CloudFormation で Amplify Hosting にデプロイ（以降は `main` への push で自動ビルド）

リージョンはすべて `us-west-2` です。
