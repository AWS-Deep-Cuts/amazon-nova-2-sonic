# AWS Deep Cuts: Amazon Nova 2 Sonic

このディレクトリは、Amazon Nova 2 Sonic を題材にした技術ブログ記事とハンズオン資材をまとめたものです。

Nova 2 Sonic の双方向音声ストリーミング API を CloudShell 上で段階的に動かし、speech-to-speech モデルの仕組み・主要機能・設計上の制約を一通り体験します。

## 構成

```text
Amazon-Nova-2-Sonic/
├── README.md
├── article.md
└── hands-on/
    ├── setup.sh                       # セットアップ (モデルアクセス確認のみ)
    ├── 01_basic_conversation.py       # 基本の双方向ストリーミング
    ├── 02_voice_and_sensitivity.py    # voiceId・感度の切り替え
    ├── 03_cross_modal_and_tools.py    # Cross-modal input + Tool use
    ├── 04_realtime_microphone.py      # マイク入力のリアルタイム会話 (ローカル用)
    ├── generate_results.py            # 結果 HTML 生成 (各スクリプトが自動呼び出し)
    └── cleanup.sh                     # 出力ファイル削除
```

## ハンズオンの流れ

1. [article.md](./article.md) を読み、Nova 2 Sonic の概要・アーキテクチャ・制約を確認する
2. Bedrock コンソールで `amazon.nova-2-sonic-v1:0` のモデルアクセスを有効化する
3. CloudShell を開き、リポジトリを clone する
4. `hands-on/setup.sh` を実行する（認証確認 → ハンズオン実行 → 結果HTML生成まで自動）
5. スクリプトが出力したパスに従い `output/results.html` をダウンロードしてブラウザで開く
6. ブラウザ上で音声再生・トランスクリプト・学習ポイントを確認する
7. 確認後、`hands-on/cleanup.sh` で出力ファイルを削除する

## 注意事項

- Nova 2 Sonic は Bedrock のオンデマンド API のため、AWS リソースの作成・削除は不要です。ハンズオン中の API 呼び出し分のみ課金されます。
- ハンズオン全体 (Step 1〜3) で概算 $0.05 以下です。
- Step 4 (マイク入力) は CloudShell では実行できません。ローカル PC で pyaudio をインストールして試してください。
- Nova 2 Sonic の接続は最大 8 分で切断されます。長時間の利用にはセッション再接続が必要です。

## ライセンス

MIT License
