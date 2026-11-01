# 注文管理エージェント（order）

AgentCore CLI で作成したプロジェクトをベースにした、Strands Agents SDK（Python）のエージェントです。
AgentCore Runtime 上で動作し、Cognito のアクセストークン（JWT）で認証します。

## 構成

| ファイル | 内容 |
|---|---|
| `main.py` | エントリポイント。プロンプト検証、Agent 生成、ストリーミング応答 |
| `tools.py` | ローカルツール `get_product_info` / `convert_currency`（`@tool`） |
| `mcp_client/client.py` | AgentCore Gateway への MCP クライアント（IAM / SigV4） |
| `memory/session.py` | AgentCore Memory（短期記憶）のセッションマネージャー |
| `model/load.py` | Bedrock モデル設定 |
| `iam/invoke-gateway-policy.json` | 実行ロールに付与する `bedrock-agentcore:InvokeGateway` 権限 |

見積書の作成・ダウンロードは Gateway のツール `quote-lambda-target___create_quote` を呼び出します。

## リクエストと応答

- リクエスト: `{"prompt": "<ユーザーの入力>"}`（4000 文字以内）
- 応答: SSE。各イベントは Strands のモデルイベント `{"event": {...}}`。
  テキストは `event.contentBlockDelta.delta.text` に入り、ツール呼び出しは `event.contentBlockStart.start.toolUse` で通知されます。
  エラー時は `{"error": "..."}` を返します。
- 応答本文は Markdown です（フロントエンドで HTML に変換して表示）。
- 会話履歴は `runtimeSessionId` × JWT の `sub`（ユーザー）単位で AgentCore Memory に保存されます。

## 環境変数（agentcore.json の envVars）

| 変数 | 必須 | 説明 |
|---|---|---|
| `GATEWAY_URL` | はい | tool スタックの Outputs `GatewayUrl`。未設定時は見積書ツールなしで動作 |
| `MEMORY_ORDERMEMORY_ID` | 自動 | AgentCore CLI がデプロイ時に設定 |

## テスト

```powershell
uv run pytest -q
```
