import { useState, type FormEvent } from "react";
import { confirmSignUp, resendSignUpCode, signIn, signUp } from "aws-amplify/auth";
import { authErrorMessage } from "../lib/auth";

type Mode = "signIn" | "signUp" | "confirm";

// ログイン・アカウント作成・メール確認の画面
export function AuthScreen({ onAuthenticated }: { onAuthenticated: () => void }) {
  const [mode, setMode] = useState<Mode>("signIn");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [busy, setBusy] = useState(false);

  const run = async (fn: () => Promise<void>) => {
    setError("");
    setInfo("");
    setBusy(true);
    try {
      await fn();
    } catch (e) {
      console.error(e);
      setError(authErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  // ログイン（SRP 認証）
  const doSignIn = async () => {
    const result = await signIn({ username: email, password });
    if (result.isSignedIn) {
      onAuthenticated();
      return;
    }
    if (result.nextStep.signInStep === "CONFIRM_SIGN_UP") {
      // メール未確認のユーザー
      await resendSignUpCode({ username: email });
      setMode("confirm");
      setInfo("メールアドレスの確認が完了していません。届いた確認コードを入力してください。");
      return;
    }
    throw new Error("ログインを完了できませんでした。");
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (mode === "signIn") {
      run(doSignIn);
    } else if (mode === "signUp") {
      run(async () => {
        await signUp({ username: email, password, options: { userAttributes: { email } } });
        setMode("confirm");
        setInfo(`${email} に確認コードを送信しました。`);
      });
    } else {
      run(async () => {
        await confirmSignUp({ username: email, confirmationCode: code.trim() });
        await doSignIn();
      });
    }
  };

  const switchMode = (next: Mode) => {
    setMode(next);
    setError("");
    setInfo("");
  };

  return (
    <main className="auth">
      <h1>注文管理アシスタント</h1>
      <p className="auth-sub">
        {mode === "signIn" && "ログイン"}
        {mode === "signUp" && "アカウント作成"}
        {mode === "confirm" && "メールアドレスの確認"}
      </p>

      <form onSubmit={handleSubmit}>
        {mode !== "confirm" && (
          <>
            <label htmlFor="email">メールアドレス</label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <label htmlFor="password">パスワード</label>
            <input
              id="password"
              type="password"
              autoComplete={mode === "signUp" ? "new-password" : "current-password"}
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              aria-describedby={mode === "signUp" ? "password-hint" : undefined}
            />
            {mode === "signUp" && (
              <p id="password-hint" className="hint">
                8文字以上で、英小文字と数字を含めてください。
              </p>
            )}
          </>
        )}

        {mode === "confirm" && (
          <>
            <label htmlFor="code">確認コード</label>
            <input
              id="code"
              inputMode="numeric"
              autoComplete="one-time-code"
              required
              value={code}
              onChange={(e) => setCode(e.target.value)}
            />
          </>
        )}

        <button type="submit" disabled={busy}>
          {mode === "signIn" && "ログイン"}
          {mode === "signUp" && "登録する"}
          {mode === "confirm" && "確認してはじめる"}
        </button>
      </form>

      {info && (
        <p className="info" role="status">
          {info}
        </p>
      )}
      {error && (
        <p className="auth-error" role="alert">
          {error}
        </p>
      )}

      <div className="auth-links">
        {mode === "signIn" && (
          <button type="button" className="link" onClick={() => switchMode("signUp")}>
            アカウントを作成
          </button>
        )}
        {mode === "signUp" && (
          <button type="button" className="link" onClick={() => switchMode("signIn")}>
            ログインに戻る
          </button>
        )}
        {mode === "confirm" && (
          <>
            <button
              type="button"
              className="link"
              disabled={busy}
              onClick={() =>
                run(async () => {
                  await resendSignUpCode({ username: email });
                  setInfo("確認コードを再送信しました。");
                })
              }
            >
              確認コードを再送信
            </button>
            <button type="button" className="link" onClick={() => switchMode("signIn")}>
              ログインに戻る
            </button>
          </>
        )}
      </div>
    </main>
  );
}
