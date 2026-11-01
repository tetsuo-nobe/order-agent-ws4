# tool（手順1: AWS SAM）

エージェント認証用の Cognito ユーザープールと、注文見積り書の作成・ダウンロード機能（Lambda）、
それをターゲットにした AgentCore Gateway を作成します。

## 構成

```
[AgentCore Runtime (エージェント)]
   │  MCP over HTTPS / SigV4（Gateway の inbound 認証 = AWS_IAM）
   ▼
[AgentCore Gateway: order-agent-ws4-quote-gateway]
   │  GATEWAY_IAM_ROLE（lambda:InvokeFunction）
   ▼
[Lambda: order-agent-ws4-create-quote] ──▶ [S3: 見積書PDF（30日で自動削除）]
                                              └─ 署名付きURL（既定1時間）でダウンロード

[Cognito User Pool: order-agent-ws4-users] … AgentCore Runtime の JWT 認証用（フロントでログイン）
```

- MCP 上のツール名は `quote-lambda-target___create_quote`（`<ターゲット名>___<ツール名>`）
- 入力: `product_id` / `customer_name` / `quantity`（1以上の整数）/ `currency`（USD・JPY）
- 出力: `quote_url`, `product_name`, `unit_price`, `quantity`, `total`, `currency` など。エラー時は `{"error": "..."}`
- 単価は指定通貨へ固定レート（1 USD = 150 JPY）で換算し、丸めた単価 × 数量で合計（税抜き）を算出
- PDF フォントは `src/fonts/NotoSansJP-VariableFont_wght.ttf`（ws3 からコピー）

## デプロイ

```powershell
cd tool
sam build
sam deploy
```

リージョンは `us-west-2`、スタック名は `order-agent-ws4-tool`（`samconfig.toml`）。

## 動作確認

```powershell
# ユニットテスト
pip install reportlab==4.4.0 boto3 pytest
python -m pytest -q

# Gateway 経由の実呼び出し（tools/list → tools/call → PDF ダウンロード）
python scripts\smoke_test_gateway.py <GatewayUrl> us-west-2
```

## Outputs（後続手順で使用）

| Output | 用途 |
|---|---|
| `GatewayUrl` | エージェントの環境変数 `GATEWAY_URL` |
| `GatewayArn` | Runtime 実行ロールに付与する `bedrock-agentcore:InvokeGateway` の Resource |
| `CognitoDiscoveryUrl` | agentcore.json の `customJwtAuthorizer.discoveryUrl` |
| `UserPoolClientId` | agentcore.json の `allowedClients` / フロントの Cognito Client ID |
| `UserPoolId` | フロントの Cognito User Pool ID |

確認コマンド:

```powershell
aws cloudformation describe-stacks --stack-name order-agent-ws4-tool --region us-west-2 --query "Stacks[0].Outputs" --output table
```

## 留意点

- 署名付き URL は Lambda 実行ロールの一時認証情報で署名するため、`PresignedUrlExpiresIn` を長くしても、認証情報の失効時刻（数時間程度）で無効になる場合があります。
- `sam validate --lint` は `AWS::BedrockAgentCore::*` で誤検知することがあります（cfn-lint のスキーマ未対応）。
- App Client は SRP 認証のみ許可しています（`ALLOW_USER_PASSWORD_AUTH` は無効）。
