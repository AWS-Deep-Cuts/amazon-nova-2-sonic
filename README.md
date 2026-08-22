このリポジトリは AWS Deep Cuts の、Amazon Nova 2 Sonic に関するハンズオンコンテンツです。

<!-- TODO: 記事公開後にリンクを追加 -->
<!-- Amazon Nova 2 Sonicの解説記事(Qiita)は[こちら]() -->

# AWS Deep Cutsとは
AWS Deep Cutsは、AWS の最新のサービスやニッチな機能、または高度にアカデミックな知識を要求するサービスなど、多くの人が知らない 『隠れた名曲 = **Deep Cuts**』 を深くまで掘り下げる技術シリーズです。

このようなサービスはWeb情報も少なく、初学者は気軽にキャッチアップできないのが実情です。

そこで AWS Deep Cuts シリーズでは、**前提知識も含めた分かりやすいサービス解説** と **手順通りに進めれば誰でも再現できるハンズオン** を提供します！

## ハンズオンのゴール

このハンズオンでは、ローカル PC 上に Nova 2 Sonic のプレイグラウンドを構築し、**プロンプトを自由に書き換えながら** 以下の 7 つの観点を確認します。

1. 通常のプロンプトでは AI が自分から話しかけてこないこと
2. 特殊なプロンプト (Model-start-first) で AI から先に話しかけてくれること
3. 話者 (voiceId) を変更できること
4. 言語を変更できること（ポリグロットボイス）
5. ターンテイキングと割り込み (barge-in) が自然に動作すること
6. 話し方の抑揚・テンションが AI の応答スタイルにも影響すること
7. Tool use で外部情報（今日の天気）を取得できること
8. プロンプトで発話スピードを制御できること

## ハンズオン手順

以降の手順は、ローカル PC（Windows / macOS / Linux）で実施してください。

### 前提条件

- Python 3.9 以上
- AWS CLI 設定済み (`aws configure`)
- マイク付きの PC + Chrome / Edge ブラウザ

### １．セットアップ + サーバー起動

```bash
git clone https://github.com/AWS-Deep-Cuts/amazon-nova-2-sonic.git
cd amazon-nova-2-sonic/hands-on
python setup.py
```

> **Note**: macOS / Linux の場合は `python3 setup.py` を使用してください。

setup.py が認証確認・パッケージ確認を行い、WebSocket 中継サーバーを起動します。以下の表示が出れば準備完了です。

```
  WebSocket: ws://127.0.0.1:8765
  Security:  127.0.0.1 only (外部アクセス不可)

  index.html をブラウザで開いてください。
```

> **セキュリティ**: サーバーは `127.0.0.1` にのみバインドされます。外部からアクセスすることはできません。

### ２．ブラウザでプレイグラウンドを開く

`hands-on/index.html` をブラウザで直接開きます（ダブルクリックまたは以下）。

```bash
# macOS
open index.html

# Windows
start index.html

# Linux
xdg-open index.html
```

### ３．7 つの観点を確認する

以下の各観点について、プロンプトや設定を変更しながら動作を確認してください。

---

#### 観点 1: 通常プロンプトでは AI が自分から話しかけない

**確認手順:**
1. System Prompt をデフォルトのままにする:
   ```
   You are a friendly English conversation partner. Keep responses short (1-2 sentences). Respond in the same language as the user.
   ```
2. 「Start」を押してマイクを開始する
3. **何も話さずに 5〜10 秒待つ**
4. AI は沈黙したままであることを確認する

**理由**: Nova 2 Sonic は speech-to-speech モデルであり、ユーザーの音声入力を検知するまで応答を生成しません。

---

#### 観点 2: 特殊プロンプトで AI から先に話しかけさせる

**確認手順:**
1. System Prompt を以下に書き換える:
   ```
   You are a friendly English tutor. As soon as the session begins, greet the student by saying "Hello! Welcome to today's English lesson. How are you feeling today?" Do not wait for the user to speak first.
   ```
2. 「Start」を押す
3. **何も話さずに待つ** — AI が自発的に挨拶を開始することを確認する

**仕組み**: Nova 2 Sonic はシステムプロンプトで「最初に話せ」と指示されると、音声入力ストリームが開始された直後に発話を開始します。これが "Model-start-first" パターンです。

---

#### 観点 3: 話者 (voiceId) の変更

**確認手順:**
1. Prompt Config の `audioOutputConfiguration.voiceId` を `"matthew"` にして Start → 何か話す → Stop
2. `voiceId` を `"tiffany"` に変えて Start → 同じことを話す → Stop
3. `voiceId` を `"amy"` に変えて Start → 同じことを話す → Stop

**確認ポイント**: 同じプロンプト・同じ質問でも、voiceId によって声質・アクセントが明確に変わることを確認してください。

**制約**: voiceId はセッション開始時に決定され、セッション途中で変更できません（1 セッション = 1 voice）。

---

#### 観点 4: 言語の変更（ポリグロット）

**確認手順:**
1. Prompt Config の `voiceId` を `"matthew"` (ポリグロット) にする
2. System Prompt を以下に変更:
   ```
   You are a helpful assistant. Always respond in French.
   ```
3. Start → 英語で話しかける（例: "What's your favorite food?"）
4. AI が**フランス語で**応答することを確認する
5. Stop → System Prompt を `Always respond in Spanish.` に変えて再度 Start
6. AI がスペイン語で応答することを確認する

**ポイント**: matthew と tiffany はポリグロットボイスで、voiceId を変えずに 7 言語（英/仏/伊/独/西/葡/ヒンディー）を話せます。amy など非ポリグロットボイスでは、対応言語以外を指定すると英語にフォールバックします。

---

#### 観点 5: ターンテイキングと割り込み (barge-in)

**ターンテイキングの確認:**
1. Session Config の `endpointingSensitivity` を `"LOW"` に設定して Start
2. ゆっくり、途中で 2〜3 秒ポーズを入れながら話す（例: "I think... um... maybe... we should..."）
3. AI がポーズ中に割り込まず、発話完了を待つことを確認する
4. Stop → `endpointingSensitivity` を `"HIGH"` にして同じことを試す
5. AI が短いポーズで即座に応答を始めることを確認する

**barge-in（割り込み）の確認:**
1. `endpointingSensitivity` を `"MEDIUM"` にして Start
2. 何か質問して AI に長めの応答をさせる（例: "Tell me everything you know about Japan"）
3. **AI が話している最中に** 大きな声で割り込む（例: "Stop! I have a different question."）
4. AI が発話を中断し、あなたの新しい質問に応答することを確認する

**仕組み**: Nova 2 Sonic はビルトインの VAD (Voice Activity Detection) でターン検出を行います。barge-in 時はコンテキストを保持したまま現在の生成を中断し、新しいユーザー入力の処理を開始します。

---

#### 観点 6: 声の抑揚・テンションが応答に影響する

**確認手順:**
1. 同じ質問を**異なるテンション**で話す:
   - 1回目: 落ち着いた普通のトーンで "How are you today?"
   - 2回目: 非常に元気で高いテンションで "HOW ARE YOU TODAY!!"（大きな声で、高いテンションで）
   - 3回目: 疲れた小さな声で "how are you today..."（ぼそぼそと）
2. AI の応答のトーン・スピード・エネルギーが入力に応じて変化することを確認する

**仕組み**: Nova 2 Sonic は "Adaptive speech response" 機能を持ち、入力音声の prosody (韻律) に基づいて応答のデリバリーを動的に調整します。これは公式ドキュメントで明記されている機能です。

---

#### 観点 7: Tool use で天気情報を取得する

**確認手順:**
1. 「Tool use を有効にする」チェックボックスをオンにする
2. System Prompt を以下に変更:
   ```
   You are a helpful weather assistant. When the user asks about the weather, use the get_weather tool to fetch real data. Report the results naturally in speech.
   ```
3. Start → 「今日の東京の天気を教えて」と話しかける
4. ログに `Tool: get_weather` が表示され、AI が実際の天気情報を音声で報告することを確認する
5. 「大阪の天気は？」「福岡は？」など別の地域も試す

**仕組み**: Nova 2 Sonic が `toolUse` イベントを送信 → サーバーが気象庁 API を呼び出し → `toolResult` でモデルに結果を返す → モデルが結果を音声で報告する。

---

#### 観点 8: 発話スピードの制御

**確認手順:**
1. System Prompt を以下に変更して Start:
   ```
   You are a helpful assistant. Speak very slowly and clearly, as if explaining to a young child. Take your time with each word.
   ```
2. 何か質問して AI の応答スピードが遅いことを確認する
3. Stop → System Prompt を以下に変更して再度 Start:
   ```
   You are an excited sports commentator. Speak extremely fast and energetically, like you're calling a thrilling game-winning play!
   ```
4. 同じ質問をして、AI の応答スピードが明らかに速くなることを確認する

**ポイント**: Nova 2 Sonic はシステムプロンプトの指示に従って発話速度を調整できます。教育用途（ゆっくり明瞭に）やエンタメ用途（テンポよく）など、ユースケースに応じた制御が可能です。

---

### ４．後片付け

サーバーを Ctrl+C で停止します。

```bash
bash cleanup.sh
```

Nova 2 Sonic は Bedrock のオンデマンド API のため、AWS リソースの削除は不要です。

## アーキテクチャ

```
┌──────────────────┐    WebSocket     ┌──────────────────┐    Bedrock API    ┌────────────────┐
│  index.html      │ ←─────────────→  │  server.py       │ ←──────────────→  │  Nova 2 Sonic  │
│  (ブラウザ)       │  ws://127.0.0.1  │  (localhost)     │                   │                │
│  マイク入力/再生   │                  │  ツール実行       │                   │                │
└──────────────────┘                   └───────┬──────────┘                   └────────────────┘
                                               │
                                               ↓ HTTP
                                       ┌──────────────┐
                                       │ 気象庁 API    │
                                       └──────────────┘
```

- **セキュリティ**: server.py は `127.0.0.1` にのみバインド。外部ネットワークからアクセスできません。
- **認証**: AWS CLI のクレデンシャルを使用。ブラウザに認証情報は渡しません。
