:::note info
AWS Deep Cuts は、AWS の中でも特に最新のサービスやニッチな機能など、多くの人が知らない「隠れた名曲 = Deep Cuts」を深くまで掘り下げる技術シリーズです。

このようなサービスは情報が少ないため、一部の有識者以外は触り方すら分からず、気軽にキャッチアップできないのが実情です。

そこで AWS Deep Cuts シリーズは「どんな人でも実際に触りながら理解できる」ことを目指し、できるだけ噛み砕いたサービス解説と簡単なハンズオンを提供します。
:::

:::note info
ハンズオン教材は GitHub でも公開しています。
https://github.com/AWS-Deep-Cuts/amazon-nova-2-sonic
:::

# はじめに

Amazon Nova 2 Sonic は、音声の理解と生成を1つのモデルに統合した speech-to-speech 基盤モデルです。従来の「音声認識 → テキスト処理 → 音声合成」のパイプラインを単一 API で置き換え、ターン間レイテンシ約 100ms のリアルタイム音声対話を実現します。

この記事では Nova 2 Sonic の仕組みを解説し、**ローカル PC に構築するプレイグラウンド**を通じて、プロンプトを書き換えながら 7 つの機能・特性を体験するハンズオンを提供します。

# 1. Amazon Nova 2 Sonic とは

## 1.1 概要

Amazon Nova 2 Sonic は Amazon Bedrock 上で利用できる speech-to-speech 基盤モデルです。音声入力をリアルタイムで理解し、テキスト応答の生成と音声合成を同時に行います。

| 項目 | 従来 (Transcribe + LLM + Polly) | Nova 2 Sonic |
| -- | -- | -- |
| アーキテクチャ | 3 サービスを連結 | 単一モデル |
| ターン間レイテンシ | 3〜7 秒 | ~100ms |
| 割り込み (barge-in) | 自前実装が必要 | ネイティブサポート |
| 入力の韻律を保持 | 不可能（テキスト化で失われる） | 入力の prosody に応じて応答を調整 |

## 1.2 主要スペック

| 項目 | 値 |
| -- | -- |
| モデル ID | `amazon.nova-2-sonic-v1:0` |
| API | `InvokeModelWithBidirectionalStream` |
| 音声入力 | PCM 16kHz 16bit mono |
| 音声出力 | PCM 24kHz 16bit mono |
| コンテキストウィンドウ | 1M トークン |
| 接続制限 | 8 分 |
| 無音タイムアウト | 55 秒 |
| 利用可能リージョン | us-east-1, us-west-2, ap-northeast-1, eu-north-1 |

## 1.3 voiceId と多言語対応

| 言語 | 女性 | 男性 | ポリグロット |
| -- | -- | -- | -- |
| English (US) | tiffany | matthew | Yes |
| English (UK) | amy | — | No |
| English (AU) | olivia | — | No |
| English (IN) | kiara | arjun | No |
| French | ambre | florian | No |
| Italian | beatrice | lorenzo | No |
| German | tina | lennart | No |
| Spanish (US) | lupe | carlos | No |
| Portuguese | carolina | leo | No |
| Hindi | kiara | arjun | No |

`matthew` と `tiffany` はポリグロットボイスで、全対応言語を同じ声で話せます。

# 2. このハンズオンで作るもの

ローカル PC 上に Nova 2 Sonic のプレイグラウンドを構築します。AWS リソースの作成は不要です。

```text
┌──────────────┐    WebSocket     ┌──────────────┐    Bedrock API    ┌────────────┐
│  index.html  │ ←─────────────→  │  server.py   │ ←──────────────→  │ Nova Sonic │
│  (ブラウザ)   │  ws://127.0.0.1  │  (localhost)  │                   │            │
└──────────────┘                   └──────┬───────┘                   └────────────┘
                                          │ HTTP
                                   ┌──────────────┐
                                   │ 気象庁 API    │
                                   └──────────────┘
```

プレイグラウンドでは、プロンプトを自由に書き換えて以下の 7 観点を確認します。

1. 通常プロンプトでは AI が自分から話しかけない
2. 特殊プロンプトで AI から先に話しかけさせる (Model-start-first)
3. 話者 (voiceId) を変更する
4. 言語を変更する（ポリグロット）
5. ターンテイキングと割り込み (barge-in)
6. 声の抑揚・テンションが応答に影響する (Adaptive speech response)
7. Tool use で外部情報を取得する

# 3. 前提条件

- Python 3.9 以上がインストールされていること
- AWS CLI で認証情報が設定済みであること (`aws configure`)
- Bedrock コンソール (ap-northeast-1) で `amazon.nova-2-sonic-v1:0` のモデルアクセスが有効であること
- マイク付きの PC と Chrome / Edge ブラウザがあること

# 4. ハンズオン

## 4.1 セットアップ

```bash
git clone https://github.com/AWS-Deep-Cuts/amazon-nova-2-sonic.git
cd amazon-nova-2-sonic/hands-on
bash setup.sh
```

setup.sh は以下を順に実行します。

1. AWS 認証の確認
2. Bedrock モデルアクセスの確認
3. Python パッケージの確認 (`boto3`, `websockets`)
4. WebSocket 中継サーバーの起動

サーバーが起動したら `index.html` をブラウザで開きます。

```bash
# macOS
open index.html

# Windows
start index.html
```

## 4.2 観点 1: 通常プロンプトでは AI が話しかけない

System Prompt をデフォルトのまま「Start」を押し、何も話さずに 5〜10 秒待ちます。AI は沈黙したままです。

Nova 2 Sonic は speech-to-speech モデルであり、ユーザーの音声入力（または Cross-modal text input）を検知するまで応答を生成しません。これは Bedrock の Playground でテキストモデルに空のリクエストを送らないのと同じ原理です。

## 4.3 観点 2: Model-start-first パターン

System Prompt を以下に書き換えて Start します。

```
You are a friendly English tutor. As soon as the session begins, greet the student by saying "Hello! Welcome to today's English lesson. How are you feeling today?" Do not wait for the user to speak first.
```

何も話さなくても、AI が自発的に挨拶を始めます。

Nova 2 Sonic はシステムプロンプトに「最初に話せ」と指示すると、音声ストリーム開始直後に発話を開始します。公式ドキュメントでは Cross-modal text input のユースケースとして "Model-start-first" が明記されています。

## 4.4 観点 3: 話者の変更

Voice ドロップダウンで `matthew` → `tiffany` → `amy` を切り替え、同じ質問を投げます。voiceId ごとに声質とアクセントが変わることを確認してください。

制約として、1 セッション = 1 voiceId です。セッション途中で声を変えることはできません。Stop → Voice 変更 → Start で新しいセッションを開始する必要があります。

## 4.5 観点 4: 言語の変更

Voice を `matthew`（ポリグロット）にし、System Prompt を `Always respond in French.` に変更して Start します。英語で話しかけても AI がフランス語で応答します。

`Always respond in Spanish.` や `Always respond in German.` も試してください。matthew / tiffany は voiceId を変えずに 7 言語を話せます。

非ポリグロットボイス（例: `amy`）で `Always respond in French.` を指定すると、英語にフォールバックする動作も確認できます。

## 4.6 観点 5: ターンテイキングと割り込み

**ターンテイキング**: Sensitivity を `LOW` にして、ゆっくり「I think... um... maybe...」のようにポーズを入れながら話します。AI はポーズ中に割り込みません。`HIGH` に変えて同じことをすると、短いポーズで即応答が始まります。

**Barge-in（割り込み）**: AI に長い応答をさせ（例: "Tell me everything about Japan"）、AI が話している最中に大きな声で割り込みます（例: "Stop!"）。AI は即座に発話を中断し、新しい入力の処理を開始します。

Nova 2 Sonic はビルトインの VAD (Voice Activity Detection) でターン検出を行い、barge-in 時もコンテキストを保持します。「さっき何を話していたっけ？」と聞くと、中断前の内容を覚えていることが確認できます。

## 4.7 観点 6: 声の抑揚が応答に影響する

同じ質問 "How are you today?" を 3 種類のトーンで話します。

1. 普通の落ち着いたトーン
2. 非常にハイテンション・大きな声
3. 疲れた小さな声・ぼそぼそ

AI の応答のエネルギー・スピード・トーンが入力に応じて変化します。

これは公式に "Adaptive speech response that dynamically adjusts delivery based on the prosody of the input speech" と記載されている機能です。従来の Transcribe + LLM + Polly パイプラインでは、テキスト化の時点で韻律情報が失われるため不可能でした。

## 4.8 観点 7: Tool use で天気を取得する

「Tool use を有効にする」にチェックを入れ、System Prompt を以下にします。

```
You are a helpful weather assistant. When the user asks about the weather, use the get_weather tool to fetch real data. Report the results naturally in speech.
```

「今日の東京の天気を教えて」と話しかけます。ログに `🔧 Tool: get_weather` が表示され、AI が気象庁 API から取得した実際の天気情報を音声で報告します。

内部的には、Nova 2 Sonic が `toolUse` イベントを送信 → server.py が気象庁 API を呼び出し → `toolResult` でモデルに返却 → モデルが結果を音声化、という流れです。

# 5. クリーンアップ

サーバーを Ctrl+C で停止し、以下を実行します。

```bash
bash cleanup.sh
```

Nova 2 Sonic は Bedrock のオンデマンド API のため、AWS リソースの削除は不要です。

# 6. 学んだこと

このハンズオンで体験した Nova 2 Sonic の特性を整理します。

- **Speech-to-Speech 統合**: ASR + LLM + TTS を 1 モデルに統合。韻律情報を保持したまま応答を生成できる。
- **Model-start-first**: プロンプト設計で AI から能動的に話しかけるパターンを実現できる。
- **ポリグロットボイス**: matthew / tiffany は voiceId 固定で 7 言語に対応。多言語アプリに最適。
- **Adaptive speech response**: ユーザーの話し方のトーン・エネルギーに応じて応答を動的に調整する。
- **ネイティブ barge-in**: 割り込みを自然に処理し、コンテキストを保持する。
- **endpointingSensitivity**: ターン検出感度を LOW/MEDIUM/HIGH で制御。初心者向け・上級者向けの設計に使える。
- **Tool use**: 会話中に外部 API を非同期で呼び出し、結果を音声で報告できる。

これらの特性を組み合わせることで、edTech（AI 英語講師・アダプティブ学習）、カスタマーサポート、テレフォニー統合など、リアルタイム音声対話が求められるサービスの基盤を構築できます。

# 参考リンク

- [Amazon Nova 2 Sonic ドキュメント](https://docs.aws.amazon.com/nova/latest/nova2-userguide/using-conversational-speech.html)
- [Input Events](https://docs.aws.amazon.com/nova/latest/nova2-userguide/sonic-input-events.html)
- [Output Events](https://docs.aws.amazon.com/nova/latest/nova2-userguide/sonic-output-events.html)
- [Cross-modal Input](https://docs.aws.amazon.com/nova/latest/nova2-userguide/sonic-cross-modal.html)
- [Barge-in](https://docs.aws.amazon.com/nova/latest/nova2-userguide/sonic-barge-in.html)
- [Tool Configuration](https://docs.aws.amazon.com/nova/latest/nova2-userguide/sonic-tool-configuration.html)
- [Language Support & Voices](https://docs.aws.amazon.com/nova/latest/nova2-userguide/sonic-language-support.html)
- [Code Examples](https://docs.aws.amazon.com/nova/latest/nova2-userguide/sonic-code-examples.html)
- [Amazon Bedrock Pricing](https://aws.amazon.com/bedrock/pricing/)
