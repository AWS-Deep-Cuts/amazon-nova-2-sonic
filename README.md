# AWS Deep Cuts: Amazon Nova 2 Sonic

このディレクトリは、Amazon Nova 2 Sonic を題材にした技術ブログ記事とハンズオン資材をまとめたものです。

Nova 2 Sonic の双方向音声ストリーミング API を段階的に体験し、speech-to-speech モデルの仕組み・主要機能・設計上の制約を理解します。CloudShell で clone して setup.sh を実行するだけで始められます。

## 構成

```text
Amazon-Nova-2-Sonic/
├── README.md                          # このファイル
├── article.md                         # Deep Cuts 解説記事
└── hands-on/
    ├── setup.sh                       # セットアップ (pip install + モデルアクセス確認)
    ├── 01_basic_conversation.py       # Step 1: 基本の双方向ストリーミング
    ├── 02_voice_and_sensitivity.py    # Step 2: voiceId・感度の切り替え
    ├── 03_cross_modal_and_tools.py    # Step 3: Cross-modal input + Tool use
    ├── 04_realtime_microphone.py      # Step 4: マイク入力のリアルタイム会話 (ローカル用)
    └── cleanup.sh                     # クリーンアップ (出力ファイル削除)
```

## ハンズオンで体験できる Nova 2 Sonic の機能

| Step | スクリプト | 体験する機能 |
|------|-----------|-------------|
| 1 | `01_basic_conversation.py` | 双方向ストリーミング、サイレンスポンプ、Cross-modal text input、WAV出力 |
| 2 | `02_voice_and_sensitivity.py` | voiceId 聴き比べ、ポリグロット多言語、endpointingSensitivity |
| 3 | `03_cross_modal_and_tools.py` | マルチターン会話、Tool use (発話評価)、toolChoice |
| 4 | `04_realtime_microphone.py` | マイク入力リアルタイム会話、barge-in、8分接続制限 |

## ハンズオンの流れ

1. [article.md](./article.md) を読み、Nova 2 Sonic の概要・制約を理解する
2. CloudShell を開く（またはローカルに clone）
3. `hands-on/setup.sh` でセットアップする
4. Step 1 → 2 → 3 を順に実行し、出力される WAV ファイルと学習ポイントを確認する
5. (ローカルPCのみ) Step 4 でマイクを使ったリアルタイム会話を体験する
6. `hands-on/cleanup.sh` で出力ファイルを削除する

## 前提条件

- AWS アカウント + CloudShell（または Python 3.9 以上 + AWS CLI 設定済みの環境）
- Bedrock コンソールで `amazon.nova-2-sonic-v1:0` のモデルアクセスが有効化されていること
- IAM に `bedrock:InvokeModelWithBidirectionalStream` 権限があること

## クイックスタート

```bash
# CloudShell で実行
git clone https://github.com/Kenta-Matsuda/AWS-Deep-Cuts.git
cd AWS-Deep-Cuts/Amazon-Nova-2-Sonic/hands-on
bash setup.sh
python3 01_basic_conversation.py
```

リージョンを変更する場合:

```bash
export AWS_REGION=ap-northeast-1
bash setup.sh
```

## コスト目安

Nova 2 Sonic はオンデマンド従量課金です。ハンズオン全体（Step 1〜3）で概算 $0.05 以下です。AWS リソースの作成は行わないため、ハンズオン終了後の追加課金やリソース削除は不要です。

## 注意事項

- Step 4 (マイク入力) は CloudShell では実行できません。ローカル PC で pyaudio をインストールして試してください。
- Nova 2 Sonic の接続は最大8分で切断されます。Step 4 で長時間会話する場合は再起動してください。
- output/ ディレクトリに WAV ファイルが出力されます。不要になったら `cleanup.sh` で削除してください。

## ライセンス

MIT License
