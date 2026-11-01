// Cognito 認証（aws-amplify の Auth ライブラリのみ使用。Amplify Gen2 のバックエンドは使わない）
import { Amplify } from "aws-amplify";
import { fetchAuthSession } from "aws-amplify/auth";
import { config } from "../config";

export function configureAuth(): void {
  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId: config.userPoolId,
        userPoolClientId: config.userPoolClientId,
        loginWith: { email: true },
      },
    },
  });
}

/**
 * AgentCore Runtime に渡すアクセストークンを取得する（期限切れなら自動更新）。
 * AgentCore の allowedClients はアクセストークンの client_id を検証するため、ID トークンではなくアクセストークンを使う。
 */
export async function getAccessToken(): Promise<string | undefined> {
  try {
    const session = await fetchAuthSession();
    return session.tokens?.accessToken?.toString();
  } catch {
    return undefined;
  }
}

/** Cognito のエラーをユーザー向けの日本語メッセージに変換する */
export function authErrorMessage(e: unknown): string {
  const name = e instanceof Error ? e.name : "";
  switch (name) {
    case "NotAuthorizedException":
      return "メールアドレスまたはパスワードが正しくありません。";
    case "UserNotFoundException":
      return "メールアドレスまたはパスワードが正しくありません。";
    case "UsernameExistsException":
      return "このメールアドレスは既に登録されています。";
    case "InvalidPasswordException":
      return "パスワードは8文字以上で、英小文字と数字を含めてください。";
    case "CodeMismatchException":
      return "確認コードが正しくありません。";
    case "ExpiredCodeException":
      return "確認コードの有効期限が切れています。コードを再送信してください。";
    case "LimitExceededException":
    case "TooManyRequestsException":
      return "試行回数の上限に達しました。しばらく待ってから再度お試しください。";
    case "EmptySignInUsername":
    case "EmptySignUpUsername":
      return "メールアドレスを入力してください。";
    case "EmptySignInPassword":
    case "EmptySignUpPassword":
      return "パスワードを入力してください。";
    default:
      return "認証に失敗しました。入力内容を確認してください。";
  }
}
