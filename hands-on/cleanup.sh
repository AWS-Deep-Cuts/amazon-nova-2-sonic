#!/bin/bash

# AWS Deep Cuts - Amazon Nova 2 Sonic クリーンアップ
#
# Nova 2 Sonic は Bedrock のオンデマンド API のため AWS リソースの削除は不要です。
# このスクリプトはインストールしたパッケージの案内のみ行います。

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  AWS Deep Cuts - Nova 2 Sonic クリーンアップ"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  ✅ Nova 2 Sonic は Bedrock オンデマンド API のため、"
echo "     AWS リソースの削除は不要です。"
echo ""
echo "  ✅ 課金は API 呼び出し時の音声入出力量のみです。"
echo "     追加の固定費は発生しません。"
echo ""
echo "  📋 インストールしたパッケージを削除する場合:"
echo "     pip uninstall -y boto3 websockets"
echo ""
echo "  📋 リポジトリを削除する場合:"
echo "     cd ../.. && rm -rf amazon-nova-2-sonic"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  完了"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
