#!/bin/bash

# AWS Deep Cuts - Amazon Nova 2 Sonic クリーンアップ
#
# Nova 2 Sonic は Bedrock のオンデマンド API なので、
# AWS リソースの作成・削除は不要です。
# このスクリプトは pip パッケージと出力ファイルを削除します。

set -euo pipefail

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  AWS Deep Cuts - Nova 2 Sonic クリーンアップ"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 出力ディレクトリの削除
if [ -d "output" ]; then
  echo "Step 1/2: ハンズオン出力ファイルを削除"
  rm -rf output/
  echo "  output/ を削除しました"
else
  echo "Step 1/2: 出力ファイルなし (スキップ)"
fi
echo ""

# pip パッケージは CloudShell の場合セッション終了で消えるため、
# 明示的な削除は任意。
echo "Step 2/2: 確認事項"
echo ""
echo "  ✅ Nova 2 Sonic は Bedrock オンデマンド API のため、"
echo "     AWS リソースの削除は不要です。"
echo ""
echo "  ✅ 課金は API 呼び出し時の音声入出力量のみです。"
echo "     追加の固定費は発生しません。"
echo ""
echo "  📋 CloudShell を使った場合:"
echo "     セッション終了時に pip パッケージは自動で消えます。"
echo ""
echo "  📋 ローカル PC を使った場合:"
echo "     不要であれば以下でパッケージを削除できます:"
echo "       pip uninstall -y boto3 pyaudio"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  クリーンアップ完了"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
