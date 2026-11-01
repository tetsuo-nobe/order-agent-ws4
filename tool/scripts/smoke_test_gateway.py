"""AgentCore Gateway 経由で create_quote を呼び出す動作確認スクリプト（SigV4 / IAM 認証）

使い方:
    python scripts/smoke_test_gateway.py <GatewayUrl> [region]
"""

import json
import sys
import urllib.request

from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.session import get_session


def call(url, region, payload):
    """MCP JSON-RPC リクエストを SigV4 署名して送信する"""
    body = json.dumps(payload)
    creds = get_session().get_credentials().get_frozen_credentials()
    req = AWSRequest(method="POST", url=url, data=body,
                     headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
    SigV4Auth(creds, "bedrock-agentcore", region).add_auth(req)
    http_req = urllib.request.Request(url, data=body.encode(), headers=dict(req.headers), method="POST")
    with urllib.request.urlopen(http_req, timeout=60) as res:
        return json.loads(res.read().decode())


def main():
    url = sys.argv[1]
    region = sys.argv[2] if len(sys.argv) > 2 else "us-west-2"

    tools = call(url, region, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    names = [t["name"] for t in tools["result"]["tools"]]
    print("ツール一覧:", names)

    result = call(url, region, {
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {
            "name": "quote-lambda-target___create_quote",
            "arguments": {"product_id": "PROD-001", "customer_name": "テスト太郎", "quantity": 10, "currency": "JPY"},
        },
    })
    quote = json.loads(result["result"]["content"][0]["text"])
    url_to_download = quote.pop("quote_url", None)
    print("見積結果:", json.dumps(quote, ensure_ascii=False))
    if not url_to_download:
        sys.exit("見積書URLが返されませんでした")

    # 署名付きURLから実際にダウンロードできるか確認
    with urllib.request.urlopen(url_to_download, timeout=60) as res:
        data = res.read()
        print("ダウンロード:", res.status, res.headers.get("Content-Type"), f"{len(data)} bytes",
              "PDF" if data.startswith(b"%PDF") else "PDFではありません")


if __name__ == "__main__":
    main()
