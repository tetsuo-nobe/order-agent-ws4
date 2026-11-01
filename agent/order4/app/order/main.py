"""注文管理エージェント（AgentCore Runtime エントリポイント）

- ローカルツール: get_product_info / convert_currency（tools.py, Strands @tool）
- Gateway ツール: 見積書の作成・ダウンロード（AgentCore Gateway 経由, IAM/SigV4）
- 会話履歴: AgentCore Memory（短期記憶）にセッション単位で保存
- 応答: Strands のストリーミングイベントを SSE でそのまま返す
  （フロントエンドは contentBlockDelta のテキストを逐次表示し、最終的に Markdown を HTML として表示する）
"""

import base64
import json
from collections import OrderedDict

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.agent.conversation_manager.null_conversation_manager import NullConversationManager

from mcp_client.client import get_gateway_mcp_client
from memory.session import get_memory_session_manager
from model.load import load_model
from tools import convert_currency, get_product_info

app = BedrockAgentCoreApp()
log = app.logger

# 1 回の入力で受け付ける最大文字数
MAX_PROMPT_LENGTH = 4000
# プロセス内にキャッシュする Agent の最大数（セッション × ユーザー単位）
MAX_CACHED_AGENTS = 100

SYSTEM_PROMPT = """
あなたは注文管理アシスタントです。丁寧で分かりやすい日本語で対応してください。

## 役割
- 製品カタログの照会（製品ID・製品名・単価・通貨）
- 通貨換算（USD と JPY の間のみ。固定レート 1 USD = 150 JPY）
- 注文見積り書（PDF）の作成とダウンロードURLの提示

## ツールの使い方
- 製品情報は必ず get_product_info で確認し、推測で答えないでください。
- 通貨換算は必ず convert_currency を使ってください。
- 見積書の作成には名前が「create_quote」で終わるツールを使います。
  製品ID・顧客名・数量・通貨（USD または JPY）がすべて揃うまでは呼び出さず、不足している項目をユーザーに確認してください。
  製品名で指定された場合は get_product_info で製品IDを確認してから呼び出してください。
- ツールが error を返した場合は、その内容を分かりやすく伝え、必要な情報を確認してください。

## 回答の形式
- 回答は Markdown で記述してください（画面上で HTML として表示されます）。
- 複数の製品や見積内容は表で示してください。
- 金額には通貨記号を付けてください（例: $29.99、¥4,500）。合計金額は税抜きであることを明記してください。
- 見積書を作成したら、返された quote_url を [見積書をダウンロード](URL) の形式のリンクで示し、
  リンクの有効期限（url_expires_in_seconds）も伝えてください。URL を省略・改変しないでください。
"""

# ローカルツール
LOCAL_TOOLS = [get_product_info, convert_currency]

# AgentCore Gateway（見積書ツール）の MCP クライアント。
# Strands の ToolProvider として Agent に渡すと、接続のライフサイクルは Strands が管理する。
_gateway_client = get_gateway_mcp_client()
TOOLS = LOCAL_TOOLS + ([_gateway_client] if _gateway_client else [])

# セッション × ユーザー単位の Agent キャッシュ（LRU）
_agent_cache: "OrderedDict[str, Agent]" = OrderedDict()


def _get_or_create_agent(session_id: str, actor_id: str) -> Agent:
    """セッションとユーザーに対応する Agent を返す（無ければ作成）"""
    key = f"{session_id}/{actor_id}"
    agent = _agent_cache.get(key)
    if agent is not None:
        _agent_cache.move_to_end(key)
        return agent

    agent = Agent(
        model=load_model(),
        # 会話履歴は AgentCore Memory が保持する
        session_manager=get_memory_session_manager(session_id, actor_id),
        conversation_manager=NullConversationManager(),
        system_prompt=SYSTEM_PROMPT,
        tools=TOOLS,
        # ストリーミングはエントリポイントで返すため、標準出力へのコールバック出力は無効化
        callback_handler=None,
    )
    _agent_cache[key] = agent
    while len(_agent_cache) > MAX_CACHED_AGENTS:
        _agent_cache.popitem(last=False)
    return agent


def _get_header(headers: dict | None, name: str) -> str | None:
    """ヘッダーを大文字小文字を区別せずに取得する"""
    if not headers:
        return None
    lower = name.lower()
    for key, value in headers.items():
        if key.lower() == lower:
            return value
    return None


def _actor_id_from_jwt(context) -> str:
    """Authorization ヘッダーの JWT から sub（Cognito ユーザーID）を取り出す。

    JWT の署名・有効期限・client_id は AgentCore Runtime の JWT オーソライザーが
    検証済みのため、ここではペイロードのデコードのみ行う。
    agentcore.json の requestHeaderAllowlist に Authorization を指定する必要がある。
    """
    auth = _get_header(getattr(context, "request_headers", None), "Authorization")
    if auth and auth.lower().startswith("bearer "):
        try:
            payload_b64 = auth.split(" ", 1)[1].split(".")[1]
            payload_b64 += "=" * (-len(payload_b64) % 4)
            claims = json.loads(base64.urlsafe_b64decode(payload_b64))
            sub = claims.get("sub")
            if isinstance(sub, str) and sub:
                return sub
        except (IndexError, ValueError):
            log.warning("JWT のデコードに失敗しました")
    return "anonymous"


def _extract_prompt(payload) -> str:
    """ペイロードから prompt 文字列を取り出して検証する"""
    if not isinstance(payload, dict):
        raise ValueError("リクエストは JSON オブジェクトで送信してください")
    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt を文字列で指定してください")
    if len(prompt) > MAX_PROMPT_LENGTH:
        raise ValueError(f"入力は {MAX_PROMPT_LENGTH} 文字以内にしてください")
    return prompt.strip()


@app.entrypoint
async def invoke(payload, context):
    """エージェントを呼び出し、ストリーミングイベントを返す"""
    try:
        prompt = _extract_prompt(payload)
    except ValueError as e:
        yield {"error": str(e)}
        return

    session_id = getattr(context, "session_id", None) or "default-session"
    actor_id = _actor_id_from_jwt(context)
    log.info("エージェントを呼び出します session=%s", session_id)

    agent = _get_or_create_agent(session_id, actor_id)

    try:
        async for event in agent.stream_async(prompt):
            # モデルのストリーミングイベント（{"event": {...}}）のみを返す
            if not isinstance(event, dict) or "event" not in event:
                continue
            cbs = event["event"].get("contentBlockStart")
            if cbs is not None and not cbs.get("start"):
                continue
            yield event
    except Exception:
        log.exception("エージェントの実行中にエラーが発生しました")
        yield {"error": "エージェントの処理中にエラーが発生しました。時間をおいて再度お試しください。"}


if __name__ == "__main__":
    app.run()
