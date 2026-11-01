import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { signOut } from "aws-amplify/auth";
import { invokeAgent, newSessionId } from "../lib/agentClient";
import { getAccessToken } from "../lib/auth";
import { Markdown } from "./Markdown";

interface Message {
  id: string;
  role: "user" | "agent" | "tool" | "error";
  content: string;
}

// ツール名を表示用ラベルへ変換する（Gateway のツールは "<ターゲット名>___<ツール名>"）
const TOOL_LABELS: Record<string, string> = {
  get_product_info: "製品情報を確認しています",
  convert_currency: "通貨を換算しています",
  create_quote: "見積書を作成しています",
};
function toolLabel(name: string): string {
  const shortName = name.includes("___") ? name.split("___").pop()! : name;
  return TOOL_LABELS[shortName] ?? `ツール（${shortName}）を実行しています`;
}

const EXAMPLES = [
  "製品の一覧を教えて",
  "500ドルを日本円に換算して",
  "ウィジェットAを10個、顧客名はテスト太郎、日本円で見積書を作って",
];

export function Chat({ userEmail, onSignedOut }: { userEmail: string; onSignedOut: () => void }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const sessionIdRef = useRef(newSessionId());
  const abortRef = useRef<AbortController | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // 新しいメッセージが来たら最下部へスクロール
  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [messages]);

  // 画面を離れるときは通信を中断
  useEffect(() => () => abortRef.current?.abort(), []);

  const push = (role: Message["role"], content: string): string => {
    const id = crypto.randomUUID();
    setMessages((prev) => [...prev, { id, role, content }]);
    return id;
  };

  const send = async (text: string) => {
    const prompt = text.trim();
    if (!prompt || sending) return;

    setInput("");
    setSending(true);
    push("user", prompt);

    const token = await getAccessToken();
    if (!token) {
      push("error", "ログインの有効期限が切れました。再度ログインしてください。");
      setSending(false);
      return;
    }

    // ツール呼び出しの前後でテキストの吹き出しを分ける
    let currentAgentId: string | null = null;
    const controller = new AbortController();
    abortRef.current = controller;

    await invokeAgent(
      token,
      sessionIdRef.current,
      prompt,
      {
        onText: (chunk) => {
          if (!currentAgentId) {
            currentAgentId = push("agent", chunk);
            return;
          }
          const id = currentAgentId;
          setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, content: m.content + chunk } : m)));
        },
        onToolUse: (name) => {
          currentAgentId = null;
          push("tool", toolLabel(name));
        },
        onError: (message) => {
          currentAgentId = null;
          push("error", message);
        },
      },
      controller.signal,
    );

    abortRef.current = null;
    setSending(false);
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    send(input);
  };

  // Enter で送信、Shift+Enter で改行（IME 変換中は送信しない）
  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      send(input);
    }
  };

  const newConversation = () => {
    abortRef.current?.abort();
    sessionIdRef.current = newSessionId();
    setMessages([]);
    setSending(false);
  };

  const handleSignOut = async () => {
    abortRef.current?.abort();
    await signOut().catch(() => undefined);
    onSignedOut();
  };

  return (
    <div className="chat">
      <header className="chat-header">
        <h1>注文管理アシスタント</h1>
        <div className="header-actions">
          <span className="user-email">{userEmail}</span>
          <button type="button" className="secondary" onClick={newConversation}>
            新しい会話
          </button>
          <button type="button" className="secondary" onClick={handleSignOut}>
            ログアウト
          </button>
        </div>
      </header>

      <div className="messages" ref={listRef} role="log" aria-live="polite" aria-label="会話">
        {messages.length === 0 && (
          <div className="welcome">
            <p>製品情報の確認、通貨換算（USD / JPY）、注文見積り書の作成をお手伝いします。</p>
            <div className="examples">
              {EXAMPLES.map((ex) => (
                <button type="button" key={ex} className="example" onClick={() => send(ex)} disabled={sending}>
                  {ex}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m) => {
          if (m.role === "agent") {
            return (
              <div key={m.id} className="message agent markdown-body">
                <Markdown text={m.content} />
              </div>
            );
          }
          return (
            <div key={m.id} className={`message ${m.role}`} role={m.role === "error" ? "alert" : undefined}>
              {m.content}
            </div>
          );
        })}

        {sending && (
          <div className="typing" aria-label="応答を生成しています">
            <span />
            <span />
            <span />
          </div>
        )}
      </div>

      <form className="input-row" onSubmit={handleSubmit}>
        <label htmlFor="prompt" className="visually-hidden">
          メッセージ
        </label>
        <textarea
          id="prompt"
          rows={2}
          maxLength={4000}
          placeholder="メッセージを入力（Enter で送信、Shift+Enter で改行）"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={sending}
        />
        <button type="submit" disabled={sending || !input.trim()}>
          送信
        </button>
      </form>
    </div>
  );
}
