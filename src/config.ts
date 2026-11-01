// ビルド時に埋め込まれる接続先設定（VITE_* 環境変数）
// いずれも秘密情報ではない（Runtime ARN、Cognito の ID）。
export const config = {
  agentRuntimeArn: import.meta.env.VITE_AGENT_RUNTIME_ARN ?? "",
  agentRegion: import.meta.env.VITE_AGENT_REGION ?? "us-west-2",
  userPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID ?? "",
  userPoolClientId: import.meta.env.VITE_COGNITO_CLIENT_ID ?? "",
};

// 未設定の項目名を返す（画面にエラー表示するため）
export function missingConfigKeys(): string[] {
  const entries: [string, string][] = [
    ["VITE_AGENT_RUNTIME_ARN", config.agentRuntimeArn],
    ["VITE_COGNITO_USER_POOL_ID", config.userPoolId],
    ["VITE_COGNITO_CLIENT_ID", config.userPoolClientId],
  ];
  return entries.filter(([, v]) => !v).map(([k]) => k);
}
