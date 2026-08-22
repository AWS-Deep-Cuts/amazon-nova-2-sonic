# Amazon Nova 2 Sonic

このリポジトリは AWS Deep Cuts の、Amazon Nova 2 Sonic に関するハンズオンコンテンツです。

<!-- TODO: 記事公開後にリンクを追加 -->
<!-- Amazon Nova 2 Sonicの解説記事(Qiita)は[こちら]() -->

---

**AWS Deep Cuts**は、AWS の最新のサービスやニッチな機能、または高度にアカデミックな知識を要求するサービスなど、多くの人が知らない 『隠れた名曲 = **Deep Cuts**』 を深くまで掘り下げる技術シリーズです。

このようなサービスはWeb情報も少なく、初学者は気軽にキャッチアップできないのが実情です。

そこで AWS Deep Cuts シリーズでは、**前提知識も含めた分かりやすいサービス解説** と **手順通りに進めれば誰でも再現できるハンズオン** を提供します！

## ハンズオンのゴール

このハンズオンでは、Amazon Nova 2 Sonic の双方向音声ストリーミング API を CloudShell から実行し、以下を体験します。

- テキスト入力で AI に話しかけ、音声応答を WAV ファイルとして取得する
- voiceId (matthew / tiffany / amy) を切り替えて声質の違いを聴き比べる
- ポリグロットボイスで英語・フランス語・スペイン語の応答を確認する
- Tool use（関数呼び出し）で AI に構造化された発話評価を行わせる

生成された `output/results.html` をブラウザで開くと、音声再生・トランスクリプト・学習ポイントをまとめて確認できます。

## ハンズオン手順

以降の手順は、ハンズオン用に用意した AWS アカウントで実施してください。

### １．事前準備

Bedrock コンソール（ap-northeast-1）を開き、**Model access** で `Amazon Nova 2 Sonic` を有効化してください。

### ２．ハンズオンの実行

CloudShell で以下のコマンドを実行してください。

```bash
# このリポジトリをクローン
git clone https://github.com/AWS-Deep-Cuts/amazon-nova-2-sonic.git
cd amazon-nova-2-sonic/hands-on

# セットアップ + ハンズオン実行
bash ./setup.sh
```

setup.sh は以下を順番に実行します（追加のパッケージインストールは不要です）。

1. AWS 認証の確認
2. Bedrock モデルアクセスの確認
3. **Step 1**: 基本の双方向ストリーミング — テキスト注入で AI と会話し、WAV を保存
4. **Step 2**: voiceId の聴き比べ — 3 種類の声 × 3 言語で応答を比較
5. **Step 3**: Cross-modal input + Tool use — マルチターン会話で発話評価ツールを呼び出し
6. 結果 HTML の生成

### ３．結果の確認

setup.sh が完了すると、`output/results.html` のダウンロードパスが表示されます。

CloudShell の場合:
1. **Actions** → **Download file** をクリック
2. 表示されたパス（例: `/home/cloudshell-user/amazon-nova-2-sonic/hands-on/output/results.html`）を入力
3. ダウンロードした HTML をブラウザで開く

ブラウザ上で以下を確認できます:
- 各 Step で生成された音声 (WAV) の再生
- AI の応答トランスクリプト
- Nova 2 Sonic の学習ポイントまとめ

### ４．後片付け

Nova 2 Sonic は Bedrock のオンデマンド API のため、AWS リソースの削除は不要です。出力ファイルのみ削除します。

```bash
bash ./cleanup.sh
```

ローカル環境の場合:

```bash
cd ../..
rm -rf amazon-nova-2-sonic
```
