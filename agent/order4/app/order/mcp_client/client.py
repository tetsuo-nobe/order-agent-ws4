"""AgentCore Gateway へ接続する MCP クライアント。

Gateway の inbound 認証は AWS_IAM のため、Runtime 実行ロールの認証情報で
リクエストに SigV4 署名する。署名は mcp-proxy-for-aws の
aws_iam_streamablehttp_client が行う。
実行ロールには bedrock-agentcore:InvokeGateway 権限が必要
（agentcore.json の additionalPolicies で iam/invoke-gateway-policy.json を付与）。
"""

import logging
import os

from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient

logger = logging.getLogger(__name__)

# tool スタックの Outputs GatewayUrl（https://.../mcp）を環境変数で渡す
GATEWAY_URL = os.getenv("GATEWAY_URL", "")
# SigV4 署名に使うリージョン（未指定なら Runtime のリージョン）
GATEWAY_REGION = os.getenv("GATEWAY_REGION") or os.getenv("AWS_REGION", "us-west-2")
# AgentCore Gateway の SigV4 サービス名
GATEWAY_SIGV4_SERVICE = "bedrock-agentcore"


def get_gateway_mcp_client() -> MCPClient | None:
    """AgentCore Gateway に SigV4 で接続する MCPClient を返す。

    GATEWAY_URL が未設定の場合は None を返す（見積書ツールなしで動作する）。
    """
    if not GATEWAY_URL:
        logger.warning("GATEWAY_URL が未設定のため、AgentCore Gateway のツールは使用しません")
        return None

    return MCPClient(
        lambda: aws_iam_streamablehttp_client(
            endpoint=GATEWAY_URL,
            aws_service=GATEWAY_SIGV4_SERVICE,
            aws_region=GATEWAY_REGION,
            timeout=60,
        ),
        # Gateway に接続できなくてもエージェント自体は起動させる
        continue_on_error=True,
    )
