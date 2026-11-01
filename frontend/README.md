# 注文管理アシスタント フロントエンド（order-agent-ws4）

React + Vite の SPA です。Cognito でログインし、ブラウザから AgentCore Runtime を直接呼び出して、
エージェントの応答をストリーミング表示します。応答の Markdown は HTML として表示します。
ホスティングは AWS Amplify Hosting（Gen2 のバックエンドは使用しない）です。

```
[ブラウザ (React SPA / Amplify Hosting)]
   │ ① Cognito User Pool に SRP でログイン → アクセストークン
   │ ② POST /runtimes/{ARN}/invocations（Authorization: Bearer <accessToken>）
   ▼
[AgentCore Runtime (Strands Agent)] ── SSE でストリーミング応答
```

## 構成

| パス | 内容 |
|---|---|
| `src/lib/auth.ts` | Cognito 設定・アクセストークン取得（aws-amplify の Auth ライブラリ） |
| `src/lib/agentClient.ts` | AgentCore Runtime 呼び出しと SSE のパース |
| `src/components/AuthScreen.tsx` | ログイン・アカウント作成・メール確認 |
| `src/components/Chat.tsx` | チャット画面（ストリーミング表示、ツール実行状況の表示） |
| `src/components/Markdown.tsx` | Markdown → HTML（GFM 表対応、サニタイズ、リンクは別タブ） |
| `../amplify.yml` | Amplify Hosting のビルド設定（リポジトリ直下、モノリポ形式 `appRoot: frontend`） |
| `infra/amplify-hosting.yaml` | Amplify Hosting を作成する CloudFormation テンプレート（`AMPLIFY_MONOREPO_APP_ROOT=frontend` を設定） |

## ローカル開発

```powershell
Copy-Item .env.example .env.local   # 値を設定する
npm install
npm run dev                          # http://localhost:5173
```

| 環境変数 | 値 |
|---|---|
| `VITE_AGENT_RUNTIME_ARN` | AgentCore Runtime ARN（`agentcore status`） |
| `VITE_AGENT_REGION` | `us-west-2` |
| `VITE_COGNITO_USER_POOL_ID` | tool スタックの Outputs `UserPoolId` |
| `VITE_COGNITO_CLIENT_ID` | tool スタックの Outputs `UserPoolClientId` |

## Amplify Hosting へのデプロイ（CloudFormation）

```powershell
aws cloudformation deploy `
  --stack-name order-agent-ws4-frontend `
  --template-file infra/amplify-hosting.yaml `
  --region us-west-2 `
  --parameter-overrides `
    GitHubAccessToken=<GitHub の個人アクセストークン> `
    AgentRuntimeArn=<Runtime ARN> `
    CognitoUserPoolId=<UserPoolId> `
    CognitoClientId=<UserPoolClientId>

# 初回ビルドを開始（以降は main への push で自動ビルド）
aws amplify start-job --app-id <AmplifyAppId> --branch-name main --job-type RELEASE --region us-west-2
```

- コマンドはリポジトリ直下から実行する場合、`--template-file frontend/infra/amplify-hosting.yaml` とします。
- モノリポのため、`amplify.yml` の `appRoot` と環境変数 `AMPLIFY_MONOREPO_APP_ROOT` は同じ値（`frontend`）にする必要があります。
- 既存スタックの更新時は、`--parameter-overrides` で省略したパラメータ（GitHub トークンなど）は前回の値が使われます。
- GitHub トークンには、リポジトリへのアクセスと Webhook 作成の権限が必要です。
- 接続先はビルド時に JS に埋め込まれます。値を変えたら Amplify で再ビルドしてください。
