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

Amazon Nova 2 Sonic は、音声の理解と生成を1つのモデルに統合した speech-to-speech 基盤モデルです。従来の「音声認識 → テキスト処理 → 音声合成」という3段パイプラインを単一の API 呼び出しで置き換え、ターン間レイテンシ約 100ms のリアルタイム音声対話を実現します。

この記事では Nova 2 Sonic の仕組みを解説し、CloudShell 上で段階的に動かすハンズオンを通じて、双方向ストリーミング・voiceId 切り替え・ターン検出制御・テキスト注入・ツール呼び出しといった主要機能と、8 分接続制限・55 秒タイムアウトなどの設計上の制約を一通り体験します。

# 1. Amazon Nova 2 Sonic とは

Amazon Nova 2 Sonic は、Amazon Bedrock 上で利用できる speech-to-speech 基盤モデルです。音声入力をリアルタイムで理解し、テキスト応答の生成と音声合成を同時に行います。

従来のアプローチとの違いを整理します。

| 項目 | 従来 (Transcribe + Claude + Polly) | Nova 2 Sonic |
| -- | -- | -- |
| アーキテクチャ | 3 サービスを連結 | 単一モデル |
| ターン間レイテンシ | 3〜7 秒 | ~100ms |
| 割り込み (barge-in) | 自前実装が必要 | ネイティブサポート |
| API 呼び出し | 3 回 | 1 回 |

主なスペックは次の通りです。

| 項目 | 値 |
| -- | -- |
| モデル ID | `amazon.nova-2-sonic-v1:0` |
| API | `InvokeModelWithBidirectionalStream` |
| 音声入力 | PCM 16kHz 16bit mono (base64) |
| 音声出力 | PCM 8/16/24kHz 16bit mono (base64) |
| コンテキストウィンドウ | 1M トークン |
| 最大出力 | 64K トークン |
| 接続制限 | 8 分 |
| 無音タイムアウト | 55 秒 |
| 利用可能リージョン | us-east-1, us-west-2, ap-northeast-1, eu-north-1 |

## 1.1 対応言語と voiceId

Nova 2 Sonic は 7 言語をサポートし、言語ごとに男性/女性の声が用意されています。

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

`matthew` と `tiffany` はポリグロットボイスで、全対応言語を同じ声で話せます。多言語アプリケーションでは voiceId を固定したまま言語だけ切り替えられるため便利です。

1 セッションにつき 1 つの voiceId しか使えない点には注意してください。複数のキャラクターを同時に出すには複数セッションが必要です。

## 1.2 双方向ストリーミングの仕組み

Nova 2 Sonic は HTTP のリクエスト-レスポンスではなく、1 つの接続上で入出力が同時に流れ続けるイベント駆動のストリーミング方式です。

```text
┌────────────────┐         ┌────────────────┐
│  クライアント    │ Stream  │  Nova 2 Sonic  │
│  (Python 等)   │ ←─────→ │  (Bedrock)     │
│                │         │                │
│ 入力イベント →  │         │  → 出力イベント │
│ (audio/text)   │         │  (audio/text)  │
└────────────────┘         └────────────────┘
```

イベントは以下の順序で送信します。

```text
sessionStart                ← 推論設定 + ターン検出設定
promptStart                 ← 音声出力設定 + ツール設定
contentStart(SYSTEM)        ← システムプロンプト開始
textInput                   ← プロンプト本文
contentEnd                  ← システムプロンプト終了
contentStart(AUDIO)         ← 音声入力ストリーム開始
audioInput × N              ← マイク音声の連続送信 (32ms 単位)
[textInput]                 ← Cross-modal テキスト注入 (任意)
contentEnd(AUDIO)           ← 音声入力ストリーム終了
promptEnd → sessionEnd      ← セッション終了
```

音声入力ストリームは「常時開いたまま」が原則です。閉じるとセッション終了に向かいます。

## 1.3 出力イベント

モデルからは以下のイベントが返ります。

| イベント | 内容 |
| -- | -- |
| `textOutput` (USER) | ユーザー発話の ASR テキスト |
| `textOutput` (ASSISTANT) | AI の応答テキスト |
| `audioOutput` | AI 音声チャンク (base64 PCM) |
| `toolUse` | ツール呼び出しリクエスト |

テキスト出力の `contentStart` には `generationStage` が付きます。`SPECULATIVE` は音声生成前の予測で変更される可能性があり、`FINAL` は音声生成後の確定テキストです。UI に表示するトランスクリプトには FINAL のみを使ってください。

# 2. このハンズオンで作るもの

このハンズオンでは AWS リソースの作成は行いません。Bedrock のオンデマンド API を直接呼び出し、Nova 2 Sonic の各機能を段階的に体験します。

4 つの Python スクリプトで以下を確認します。

```text
Step 1 (01_basic_conversation.py)
  → 双方向ストリーミングの基本、サイレンスポンプ、Cross-modal text input
  → AI の音声応答を WAV ファイルに保存

Step 2 (02_voice_and_sensitivity.py)
  → voiceId の聴き比べ (matthew / tiffany / amy)
  → ポリグロットボイスで英語・フランス語・スペイン語の応答を確認
  → endpointingSensitivity の解説

Step 3 (03_cross_modal_and_tools.py)
  → マルチターン会話 (テキスト注入で模擬)
  → Tool use (evaluate_english) の呼び出し観察

Step 4 (04_realtime_microphone.py) ※ ローカル PC のみ
  → マイク入力 + スピーカー出力のリアルタイム会話
  → barge-in と 8 分接続制限の体験
```

# 3. 前提条件

- AWS アカウントを持っていること
- CloudShell が使える、または Python 3.9 以上 + AWS CLI が設定済みの環境があること
- Bedrock コンソールで `amazon.nova-2-sonic-v1:0` のモデルアクセスが有効化されていること
- IAM に `bedrock:InvokeModelWithBidirectionalStream` 権限があること

# 4. ハンズオン

## 4.1 セットアップ

CloudShell を開き、以下を実行します。

```bash
git clone https://github.com/AWS-Deep-Cuts/amazon-nova-2-sonic.git
cd amazon-nova-2-sonic/hands-on
bash setup.sh
```

リージョンを変更する場合は環境変数を設定してから実行してください。

```bash
export AWS_REGION=ap-northeast-1
bash setup.sh
```

setup.sh が行うことは以下の 3 ステップです。

1. AWS 認証の確認 (`aws sts get-caller-identity`)
2. Python パッケージのインストール (`pip install boto3`)
3. Bedrock モデルアクセスの確認 (`aws bedrock get-foundation-model`)

正常に完了すると次のような出力が表示されます。

```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  AWS Deep Cuts - Amazon Nova 2 Sonic セットアップ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

リージョン: us-east-1
モデル:     amazon.nova-2-sonic-v1:0

Step 1/3: AWS 認証を確認
  Account: 123456789012

Step 2/3: Python 依存パッケージをインストール
  boto3: OK
  pyaudio: 未インストール (Step 4 のマイク入力は使えません — CloudShell では正常)

Step 3/3: Bedrock モデルアクセスを確認
  amazon.nova-2-sonic-v1:0: アクセス可能

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  セットアップ完了
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## 4.2 Step 1: 基本の双方向ストリーミング

```bash
python3 01_basic_conversation.py
```

このスクリプトは以下を行います。

1. Nova 2 Sonic にセッションを開始する
2. システムプロンプトで AI のペルソナを設定する
3. 音声入力ストリームを開き、サイレンスポンプで接続を維持する
4. Cross-modal text input でテキストを注入し、AI に話しかける
5. AI の音声応答を `output/step1_response.wav` に保存する

実行すると AI の応答テキストがコンソールに表示され、音声が WAV ファイルに書き出されます。WAV ファイルは CloudShell からダウンロードして再生できます。

**学習ポイント**:

- Nova 2 Sonic は speech-to-speech モデルなので、テキストだけ送っても動きません。音声入力ストリームを開くことが必須です。
- サイレンスポンプ: 55 秒間音声入力がないとタイムアウトします。無音データ (ゼロ埋め PCM) を定期送信して接続を維持します。
- Cross-modal text input: 音声ストリームを維持したまま、テキストを注入して AI に音声で応答させることができます。

## 4.3 Step 2: voiceId と感度の切り替え

```bash
python3 02_voice_and_sensitivity.py
```

このスクリプトは以下を行います。

1. 同じ質問を `matthew` / `tiffany` / `amy` の 3 種類の声で応答させ、WAV を保存する
2. `matthew` (ポリグロット) に英語・フランス語・スペイン語で話しかけ、言語切り替えを確認する
3. `endpointingSensitivity` (HIGH / MEDIUM / LOW) の動作を解説する

`output/` ディレクトリに複数の WAV ファイルが出力されます。ダウンロードして聴き比べてください。

**学習ポイント**:

- 1 セッション = 1 voiceId の制約があります。セッション途中で声を変えることはできません。
- ポリグロットボイス (matthew, tiffany) は voiceId を変えずに言語を切り替えられます。
- `endpointingSensitivity` はマイク入力時に効果を発揮します。LOW は初心者向け（長い沈黙を待つ）、HIGH は上級者向け（素早く応答）です。

## 4.4 Step 3: Cross-modal input + Tool use

```bash
python3 03_cross_modal_and_tools.py
```

このスクリプトは以下を行います。

1. 3 ターンの模擬会話（意図的に文法ミスを含む英語）をテキスト注入で送信する
2. AI が `evaluate_english` ツールを呼び出すかを観察する
3. ツール呼び出しのパラメータ（スコア・フィードバック）を表示する

ツールが呼び出された場合、コンソールにスコアとフィードバックが表示されます。`toolChoice: auto` のため、モデルが不要と判断した場合は呼び出されないこともあります。

**学習ポイント**:

- Tool use の流れ: `promptStart` で定義 → モデルが `toolUse` イベントを送信 → アプリが `toolResult` で結果を返す
- `toolChoice` の選択肢: `auto` (モデル判断)、`any` (必ずいずれか)、`tool` (特定ツール強制)
- Nova 2 Sonic のツールコールは非同期で、実行中も会話が継続できます。

## 4.5 Step 4: マイク入力リアルタイム会話 (ローカル PC)

このステップは CloudShell では実行できません。マイクとスピーカーが必要です。

```bash
# pyaudio のインストール
# macOS:   brew install portaudio && pip install pyaudio
# Ubuntu:  sudo apt install portaudio19-dev && pip install pyaudio
# Windows: pip install pyaudio

python3 04_realtime_microphone.py --voice tiffany --sensitivity LOW
```

マイクに向かって英語で話しかけると、AI がリアルタイムで音声応答します。Ctrl+C で終了します。

**学習ポイント**:

- barge-in: AI が話している途中に割り込むと、AI は自動的に発話を中断して聞き始めます。
- 8 分接続制限: 7 分経過時に警告が表示されます。本番では再接続ロジックが必要です。
- `endpointingSensitivity` の違いが体感できます。LOW ではゆっくり考えながら話しても AI が被ってきません。

# 5. クリーンアップ

```bash
bash cleanup.sh
```

Nova 2 Sonic は Bedrock のオンデマンド API のため、AWS リソースの削除は不要です。このスクリプトは `output/` ディレクトリの WAV ファイルを削除するだけです。

CloudShell を使った場合、pip パッケージはセッション終了時に自動で消えます。

# 6. 学んだこと

このハンズオンで体験した Nova 2 Sonic の特徴を整理します。

- **Speech-to-Speech 統合モデル**: ASR + LLM + TTS の 3 サービス統合が不要。1 つの API 呼び出しで完結する。
- **双方向ストリーミング**: リクエスト-レスポンスではなく常時接続。音声が両方向に同時に流れる。
- **サイレンスポンプの必要性**: 55 秒の無音タイムアウトを回避するため、無音フレームを定期送信する必要がある。
- **Cross-modal input**: 音声ストリームを維持したままテキストを注入でき、AI から能動的に話しかけるパターンが実現できる。
- **Tool use**: 会話中にツール（関数）を呼び出し、構造化されたデータを取得できる。非同期実行にも対応。
- **voiceId とポリグロット**: `matthew` / `tiffany` は 1 つの声で 7 言語に対応。1 セッション = 1 voiceId の制約あり。
- **endpointingSensitivity**: ユーザーの発話終了を検出するタイミングを LOW / MEDIUM / HIGH で制御できる。
- **8 分接続制限**: セッションは最大 8 分で切断される。本番では再接続 + 会話履歴引き継ぎの設計が必要。

Nova 2 Sonic の低レイテンシ音声対話は、edTech (AI 英語講師、リアルタイム発話評価、アダプティブ学習)、カスタマーサポート、テレフォニー統合など、リアルタイム音声が求められるビジネス領域に広い応用可能性を持っています。特に `endpointingSensitivity` による学習者レベル適応や、Tool use による構造化評価の取得は、教育サービスとの相性が良い設計パターンです。

# 参考リンク

- [Amazon Nova 2 Sonic ドキュメント](https://docs.aws.amazon.com/nova/latest/nova2-userguide/using-conversational-speech.html)
- [Input Events](https://docs.aws.amazon.com/nova/latest/nova2-userguide/sonic-input-events.html)
- [Output Events](https://docs.aws.amazon.com/nova/latest/nova2-userguide/sonic-output-events.html)
- [Cross-modal Input](https://docs.aws.amazon.com/nova/latest/nova2-userguide/sonic-cross-modal.html)
- [Tool Configuration](https://docs.aws.amazon.com/nova/latest/nova2-userguide/sonic-tool-configuration.html)
- [Language Support & Voices](https://docs.aws.amazon.com/nova/latest/nova2-userguide/sonic-language-support.html)
- [Code Examples](https://docs.aws.amazon.com/nova/latest/nova2-userguide/sonic-code-examples.html)
- [Amazon Bedrock Pricing](https://aws.amazon.com/bedrock/pricing/)
