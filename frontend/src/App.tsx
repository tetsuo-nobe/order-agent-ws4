import { useEffect, useState } from "react";
import { fetchUserAttributes, getCurrentUser } from "aws-amplify/auth";
import { AuthScreen } from "./components/AuthScreen";
import { Chat } from "./components/Chat";
import { missingConfigKeys } from "./config";

type AuthState = { status: "loading" } | { status: "signedOut" } | { status: "signedIn"; email: string };

export function App() {
  const [auth, setAuth] = useState<AuthState>({ status: "loading" });
  const missing = missingConfigKeys();

  // ログイン済みかを確認する
  const refresh = async () => {
    try {
      await getCurrentUser();
      const attrs = await fetchUserAttributes().catch(() => ({}) as Record<string, string>);
      setAuth({ status: "signedIn", email: attrs.email ?? "" });
    } catch {
      setAuth({ status: "signedOut" });
    }
  };

  useEffect(() => {
    if (missing.length === 0) refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (missing.length > 0) {
    return (
      <main className="auth">
        <h1>設定エラー</h1>
        <p role="alert">次の環境変数が設定されていません: {missing.join(", ")}</p>
      </main>
    );
  }

  if (auth.status === "loading") {
    return <p className="loading">読み込み中...</p>;
  }

  if (auth.status === "signedOut") {
    return <AuthScreen onAuthenticated={refresh} />;
  }

  return <Chat userEmail={auth.email} onSignedOut={() => setAuth({ status: "signedOut" })} />;
}
