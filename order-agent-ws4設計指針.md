
## 目的

* order-agent-ws3と同等の機能をもつ注文管理エージェントをAWS環境で作成する。
* order-agent-ws3を参考にして実装する

1. Webでチャットインターフェースで会話する
    - エージェントからのメッセージはストリーミング出力とする
    - エージェントからのメッセージは最終的にHTMLとして表示する
2. 製品情報を問い合わせできる
3. 通貨換算できる(USDとJPY間) 
4. 注文見積り書を作成・ダウンロードできる
    - フォントファイルは、下記をコピーして使用する
        - order-agent-ws3\tool\src\fonts\NotoSansJP-VariableFont_wght.ttf

## 適用する技術

* 適用するAWSサービスや機能、構成は 下記とする。
* 下記は order-agent-ws3と異なる面もあるが、order-agent-ws3と同じ面もある。

1. エージェントは Strands Agents SDK の Python で実装
2. エージェントは Bedrock AgentCore Runtimeでホスティング
3. エージェントは、Cognitoユーザープールが発行したJWTトークンによる認証が必要
4. 注文見積り書を作成・ダウンロード機能は AWS Lambda関数で実装し、AgentCore Gateway のターゲットとする
5. エージェントは注文見積り書を作成・ダウンロード機能はAgentCore Gatewayのツールとして呼び出す。このときの認証はIAMにする
6. 製品情報を問い合わせと通貨換算は、Strands Agents SDK の@toolによりPython関数として実装
し、エージェントと共にデプロイする
7. フロントエンドは、React を使用する。Next.js は使用しない。
8. フロントエンドは AWS Amplify ホスティングでデプロイする。(Amplify Gen2は使用せず、Amplify ホスティングのみ使用する)

## 実装とデプロイの担当と順番について

* 実装やデプロイの全体的な進捗管理はKiroが行います。必要に応じて開発者が担当のタスクの実行タイミングはその旨を開発者へ伝えてください。

1. Kiroがエージェントの認証に使用するCognitoユーザープールと注文見積り書を作成・ダウンロード機能のLambda関数と、それをターゲットにしたAgentCore Gatewayのゲートウェイを AWS SAM で作成する  
2. 開発者がAgentCore CLI を使い、プロジェクトを手動で作成する
3. Kiroが2で作成したプロジェクトをベースに 必要なコードを実装する
4. 開発者が手動でAgentCore Rumtimeへデプロイする
5. Kiroがフロントエンドを実装して指定されたGitHubリポジトリに保存する
6. KiroがCloudFormationでGitHubリポジトリのフロントエンドをAmplify ホスティングとしてデプロイする

## フォルダ構成

* 現状のワークスペースフォルダの下にorder-agent-ws4 フォルダを作成する。
* その下に下記のフォルダを構成する
    - tool フォルダ: 手順 1 で使用する
    - agent フォルダ: 手順 2と3と4で使用する
    - frontend フォルダ: 手順5と6で使用する
* Git リポジトリに保存するときは上記全て含むモノリポとする。