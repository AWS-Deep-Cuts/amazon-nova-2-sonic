:::note info
AWS Deep Cuts は、AWS の中でも特に最新のサービスやニッチな機能など、多くの人が知らない「隠れた名曲 = Deep Cuts」を深くまで掘り下げる技術シリーズです。

このようなサービスは情報が少ないため、一部の有識者以外は触り方すら分からず、気軽にキャッチアップできないのが実情です。

そこで AWS Deep Cuts シリーズは「どんな人でも実際に触りながら理解できる」ことを目指し、できるだけ噛み砕いたサービス解説と簡単なハンズオンを提供します。
:::

:::note info
ハンズオン教材は GitHub でも公開しています。
https://github.com/Kenta-Matsuda/AWS-Deep-Cuts
:::

# はじめに

Amazon Nova 2 Sonic は、音声の理解と生成を1つのモデルに統合した speech-to-speech 基盤モデルです。従来の「音声認識 → テキスト処理 → 音声合成」という3段パイプラインを単一のAPI呼び出しで置き換え、ターン間レイテンシ約100msのリアルタイム音声対話を実現します。

この記事では Nova 2 Sonic の仕組みを解説し、CloudShell 上で段階的に動かすハンズオンを通じて、双方向ストリーミング・voiceId切り替え・ターン検出制御・テキスト注入・ツール呼び出しといった主要機能と、8分接続制限・55秒タイムアウトなどの設計上の制約を一通り体験します。

**edTech への応用可能性**: Nova 2 Sonic の低レイテンシ音声対話は、AI英語講師・リアルタイム発話評価・アダプティブ学習などの教育サービス基盤として大きな可能性を持ちます。本記事ではそうした応用を見据えながら、まずモデルの基本動作を正確に理解することに集中します。

# 1. Amazon Nova 2 Sonic とは

## 1.1 ポジショニング

| 従来のアプローチ | Nova 2 Sonic |
|---|---|
| Transcribe → Claude → Polly の3サービス | 単一モデルで ASR + 応答生成 + TTS |
| ターン間レイテンシ 3〜7秒 | ターン間レイテンシ ~100ms |
| 各サービスの設定・統合が必要 | 1つの API 呼び出し |
| 割り込み（barge-in）は自前実装 | ネイティブ barge-in サポート |

## 1.2 主要スペック

| 項目 | 値 |
|---|---|
| モデル ID | `amazon.nova-2-sonic-v1:0` |
| API | `InvokeModelWithBidirectionalStream` |
| 音声入力 | PCM 16kHz 16bit mono (base64) |
| 音声出力 | PCM 8/16/24kHz 16bit mono (base64) |
| コンテキストウィンドウ | 1M トークン |
| 最大出力 | 64K トークン |
| 接続制限 | **8分**（以降は再接続が必要） |
| 無音タイムアウト | **55秒**（音声入力がないと切断） |
| 利用可能リージョン | us-east-1, us-west-2, ap-northeast-1, eu-north-1 |

## 1.3 対応言語と voiceId

| 言語 | 女性 | 男性 | ポリグロット |
|---|---|---|---|
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

`matthew` と `tiffany` はポリグロットボイスで、7言語全てを同じ声で話せます。

**制約**: 1セッション = 1 voiceId。セッション途中で声を変えることはできません。

# 2. アーキテクチャ — 双方向ストリーミング

## 2.1 全体像

```
┌────────────────┐         ┌────────────────┐
│  クライアント    │ Stream  │  Nova 2 Sonic  │
│  (Python等)    │ ←─────→ │  (Bedrock)     │
│                │         │                │
│ 入力イベント →  │         │  → 出力イベント │
│ (audio/text)   │         │  (audio/text)  │
└────────────────┘         └────────────────┘
```

従来の HTTP リクエスト-レスポンスではなく、1つの接続上で入出力が同時に流れ続けます。

## 2.2 イベントシーケンス

```
sessionStart                 ← 推論設定 + ターン検出設定
promptStart                  ← 音声出力設定 + ツール設定
contentStart(SYSTEM) + textInput + contentEnd  ← システムプロンプト
contentStart(AUDIO)          ← 音声入力ストリーム開始
audioInput × N               ← マイク音声の連続送信 (32ms 単位)
[textInput]                  ← Cross-modal テキスト注入 (任意)
contentEnd(AUDIO)            ← 音声入力ストリーム終了
promptEnd → sessionEnd       ← セッション終了
```

**重要**: 音声入力ストリームは「常時開いたまま」が原則。閉じるとセッション終了に向かいます。

## 2.3 出力イベント

| イベント | 内容 |
|---|---|
| `textOutput` (USER) | ユーザー発話の ASR テキスト |
| `textOutput` (ASSISTANT) | AI の応答テキスト |
| `audioOutput` | AI 音声チャンク (base64 PCM) |
| `toolUse` | ツール呼び出しリクエスト |

### SPECULATIVE vs FINAL

テキスト出力の `contentStart` には `generationStage` が付きます:

- **SPECULATIVE**: 音声生成前のテキスト予測。変更される可能性あり。
- **FINAL**: 音声生成後の確定テキスト。

UIに表示するトランスクリプトには FINAL のみを使うべきです。

# 3. 主要機能の詳細

## 3.1 サイレンスポンプ — 55秒タイムアウト対策

Nova 2 Sonic は音声入力が55秒間途切れるとセッションを切断します。ユーザーが黙っている間も接続を維持するには、定期的に無音フレームを送信します。

```python
# 16kHz 16bit mono の 32ms 分 = 1024 bytes のゼロ埋め
silence_frame = base64.b64encode(b"\x00" * 1024).decode("ascii")

# 150ms間隔で送信
while is_active:
    enqueue_event({"event": {"audioInput": {..., "content": silence_frame}}})
    time.sleep(0.15)
```

## 3.2 Cross-modal Text Input

音声ストリームを維持したまま、テキストを注入して AI に応答させる公式機能です。

**ユースケース**:
- AI から先に話しかける（Model-start-first パターン）
- 会話の話題を誘導する
- DTMF（電話のキー入力）をテキスト変換して送信する

```python
# テキスト注入の3イベント
contentStart(TEXT, interactive=True, role="USER")
textInput(content="Tell me about your weekend")
contentEnd
```

**制約**: 音声ストリームが切れた状態でテキストを送ると55秒タイムアウトで切断されます。Cross-modal input は「音声セッションの補助」であり、純粋な TTS の代替にはなりません。

## 3.3 endpointingSensitivity — ターン検出制御

`sessionStart` で設定する `endpointingSensitivity` は、ユーザーが話し終わったと判定するまでの待ち時間を制御します:

| 値 | 動作 | 適したシーン |
|---|---|---|
| HIGH | 短い沈黙で即応答 (~1.5秒) | テンポの良い会話 |
| MEDIUM | バランス型 | 一般的な対話 (推奨) |
| LOW | 長い沈黙も待つ (~2秒) | 考えながら話す場面 |

## 3.4 Tool Use (関数呼び出し)

Nova 2 Sonic は会話中にツールを呼び出せます。`promptStart` でツールを定義し、モデルが必要と判断すると `toolUse` イベントを送信します。

```python
# ツール定義 (promptStart 内)
"toolConfiguration": {
    "tools": [{
        "toolSpec": {
            "name": "evaluate_english",
            "description": "Evaluate student's English proficiency",
            "inputSchema": {"json": {...}}
        }
    }],
    "toolChoice": {"auto": {}}  # auto / any / tool
}
```

**非同期ツールコール**: ツール実行中も会話が継続できるため、「分析中です」と言いながらバックグラウンドで処理する設計が可能です。

## 3.5 Barge-in (割り込み)

ユーザーが AI の発話中に話し始めると、Nova 2 Sonic は自動的に音声生成を中断し、ユーザーの発話を聞き始めます。クライアント側では未再生の音声キューをクリアする処理が必要です。

# 4. 設計上の制約と対処法

| 制約 | 対処法 |
|---|---|
| 8分接続制限 | セッション再接続 + 会話履歴の引き継ぎ |
| 55秒無音タイムアウト | サイレンスポンプ (150ms間隔で無音送信) |
| 1セッション = 1 voiceId | 複数キャラクターには複数セッション |
| SSML 非対応 | プロンプト指示で発話速度・語彙レベルを制御 |
| 純粋な TTS として使えない | 音声ストリーム維持が必須。TTS には Polly を使う |

# 5. ハンズオン手順

## 5.1 セットアップ

```bash
# CloudShell を開いて実行
git clone https://github.com/Kenta-Matsuda/AWS-Deep-Cuts.git
cd AWS-Deep-Cuts/Amazon-Nova-2-Sonic/hands-on
bash setup.sh
```

setup.sh が行うこと:
1. AWS 認証の確認
2. `pip install boto3` (pyaudio はオプション)
3. Bedrock モデルアクセスの確認

## 5.2 Step 1: 基本の双方向ストリーミング

```bash
python3 01_basic_conversation.py
```

テキスト入力（Cross-modal）で AI に話しかけ、音声応答を WAV ファイルに保存します。

**確認ポイント**:
- 音声入力ストリームを開くことが必須であること
- サイレンスポンプの役割
- 出力の `textOutput` と `audioOutput` の関係

## 5.3 Step 2: voiceId と感度の切り替え

```bash
python3 02_voice_and_sensitivity.py
```

3種類の voiceId (matthew/tiffany/amy) で同じ質問に答えさせ、WAV を聴き比べます。さらに matthew のポリグロット機能で英語・フランス語・スペイン語の応答を確認します。

**確認ポイント**:
- 声質の違い (matthew=米国男性、tiffany=米国女性、amy=英国女性)
- ポリグロットボイスは voiceId を変えずに言語を切り替えられること
- endpointingSensitivity は音声入力時に効果を発揮すること

## 5.4 Step 3: Cross-modal input + Tool use

```bash
python3 03_cross_modal_and_tools.py
```

3ターンの模擬会話（意図的に文法ミスを含む英語）をテキスト注入で送信し、AI が `evaluate_english` ツールを呼び出すかを観察します。

**確認ポイント**:
- toolConfiguration の定義方法
- toolUse イベントの構造
- toolChoice (auto/any/tool) の使い分け

## 5.5 Step 4: マイク入力リアルタイム会話 (ローカルPC)

```bash
# pyaudio が必要（CloudShell では実行不可）
pip install pyaudio
python3 04_realtime_microphone.py --voice tiffany --sensitivity LOW
```

マイクとスピーカーを使った本格的なリアルタイム会話を体験します。

**確認ポイント**:
- barge-in (AI が話している途中に割り込む) の動作
- endpointingSensitivity の体感的な違い
- 8分接続制限の警告

## 5.6 クリーンアップ

```bash
bash cleanup.sh
```

Nova 2 Sonic は Bedrock のオンデマンド API のため AWS リソースの削除は不要です。出力 WAV ファイルのみ削除します。

# 6. コストと料金

| 項目 | 料金 |
|---|---|
| 音声入力 | $0.003 / 1,000 speech tokens |
| 音声出力 | $0.012 / 1,000 speech tokens |
| テキスト入出力 | 別途テキストトークン料金 |

ハンズオン全体 (Step 1〜3) で概算 **$0.05 以下**。固定費なし。

# 7. edTech への応用展望

Nova 2 Sonic の特性は教育テクノロジーと特に相性が良いです:

| 機能 | edTech 応用 |
|---|---|
| ~100ms レイテンシ | 人間同士の会話に近いAI英語講師 |
| endpointingSensitivity | 学習者レベルに応じたアダプティブ応答 |
| Tool use | リアルタイム発話評価・CEFR レベル判定 |
| Cross-modal input | レッスン進行制御・話題誘導 |
| ポリグロット | 1つのプラットフォームで多言語学習 |
| プロンプト制御 | 語彙レベル・発話速度を難易度に連動 |

**設計パターン例**:

```
[学習者のマイク] → Nova 2 Sonic (AI講師セッション)
                      ↓ toolUse: evaluate_english
                 [評価結果] → DynamoDB (学習履歴)
                      ↓
                 [次のレッスン設計] → sensitivity/prompt を動的調整
```

ただし本番化には以下の追加設計が必要です:
- 8分制限のセッション再接続 + 会話コンテキスト引き継ぎ
- WebSocket 中継サーバー (ブラウザから Bedrock に直接接続はできない)
- 認証・レート制限・コスト管理

# 8. まとめ

| 理解すべきこと | このハンズオンでの体験 |
|---|---|
| 双方向ストリーミングの仕組み | Step 1: イベントシーケンスを手で組み立てる |
| voiceId とポリグロット | Step 2: 3声×3言語の WAV を聴き比べ |
| Cross-modal input の使い方 | Step 1-3: テキスト注入で会話を駆動 |
| Tool use の設計パターン | Step 3: 発話評価ツールの呼び出し |
| 55秒タイムアウトの回避 | Step 1: サイレンスポンプの実装 |
| 8分制限の存在 | Step 4: 長時間会話での切断体験 |
| SSML非対応の代替策 | Step 2: プロンプトによる発話制御 |

# 参考リンク

- [Amazon Nova 2 Sonic ドキュメント](https://docs.aws.amazon.com/nova/latest/nova2-userguide/using-conversational-speech.html)
- [Input Events](https://docs.aws.amazon.com/nova/latest/nova2-userguide/sonic-input-events.html)
- [Output Events](https://docs.aws.amazon.com/nova/latest/nova2-userguide/sonic-output-events.html)
- [Cross-modal Input](https://docs.aws.amazon.com/nova/latest/nova2-userguide/sonic-cross-modal.html)
- [Tool Configuration](https://docs.aws.amazon.com/nova/latest/nova2-userguide/sonic-tool-configuration.html)
- [Language Support & Voices](https://docs.aws.amazon.com/nova/latest/nova2-userguide/sonic-language-support.html)
- [Code Examples](https://docs.aws.amazon.com/nova/latest/nova2-userguide/sonic-code-examples.html)
- [Amazon Bedrock Pricing](https://aws.amazon.com/bedrock/pricing/)
