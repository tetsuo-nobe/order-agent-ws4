// AgentCore Runtime をブラウザから直接呼び出すクライアント。
// Cognito のアクセストークンを Bearer で渡し、SSE（Strands のストリーミングイベント）を逐次パースする。
import { config } from "../config";

export interface AgentCallbacks {
  /** テキストの差分（ストリーミング） */
  onText: (text: string) => void;
  /** ツール呼び出しの開始（ツール名） */
  onToolUse: (toolName: string) => void;
  /** エラー（ユーザー向けメッセージ） */
  onError: (message: string) => void;
}

// AgentCore Runtime の invocations エンドポイント
function invocationsUrl(): string {
  const arn = encodeURIComponent(config.agentRuntimeArn);
  return `https://bedrock-agentcore.${config.agentRegion}.amazonaws.com/runtimes/${arn}/invocations?qualifier=DEFAULT`;
}

// HTTP ステータスをユーザー向けメッセージに変換する
function httpErrorMessage(status: number): string {
  if (status === 401 || status === 403) {
    return "認証に失敗しました。ログアウトして再度ログインしてください。";
  }
  if (status === 429) {
    return "リクエストが集中しています。少し待ってから再度お試しください。";
  }
  return `エージェントの呼び出しに失敗しました（HTTP ${status}）。`;
}

// 1 件の SSE データ（JSON）を解釈してコールバックへ渡す
function handleEvent(data: unknown, cb: AgentCallbacks): void {
  if (typeof data !== "object" || data === null) return;
  const obj = data as Record<string, unknown>;

  if (typeof obj.error === "string") {
    cb.onError(obj.error);
    return;
  }

  const event = obj.event as Record<string, any> | undefined;
  if (!event) return;

  const text = event.contentBlockDelta?.delta?.text;
  if (typeof text === "string") {
    cb.onText(text);
    return;
  }

  const toolName = event.contentBlockStart?.start?.toolUse?.name;
  if (typeof toolName === "string") {
    cb.onToolUse(toolName);
  }
}

/**
 * エージェントを呼び出し、応答をストリーミングで処理する。
 * 完了（またはエラー）で Promise が解決する。
 */
export async function invokeAgent(
  accessToken: string,
  sessionId: string,
  prompt: string,
  cb: AgentCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(invocationsUrl(), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        Authorization: `Bearer ${accessToken}`,
        // AgentCore Runtime のセッションID（33 文字以上）。同じ ID の間は会話が継続する
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": sessionId,
      },
      body: JSON.stringify({ prompt }),
      signal,
    });
  } catch {
    if (signal?.aborted) return;
    cb.onError("通信エラーが発生しました。ネットワーク接続を確認してください。");
    return;
  }

  if (!response.ok) {
    console.error("AgentCore invoke failed", response.status, await response.text().catch(() => ""));
    cb.onError(httpErrorMessage(response.status));
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    cb.onError("応答を読み取れませんでした。");
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";

  const processLine = (line: string) => {
    if (!line.startsWith("data:")) return;
    const payload = line.slice(5).trim();
    if (!payload || payload === "[DONE]") return;
    try {
      handleEvent(JSON.parse(payload), cb);
    } catch {
      // JSON 以外のデータは無視する
    }
  };

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      // SSE は行単位。末尾の未完成の行はバッファに残す
      const lines = buffer.split(/\r?\n/);
      buffer = lines.pop() ?? "";
      lines.forEach(processLine);
    }
    buffer += decoder.decode();
    if (buffer) processLine(buffer);
  } catch {
    if (signal?.aborted) return;
    cb.onError("応答の受信中にエラーが発生しました。");
  }
}

/** AgentCore Runtime 用のセッションID（33 文字以上）を生成する */
export function newSessionId(): string {
  return (crypto.randomUUID() + crypto.randomUUID()).replace(/-/g, "");
}
