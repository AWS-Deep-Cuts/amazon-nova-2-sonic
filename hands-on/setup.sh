#!/bin/bash

# AWS Deep Cuts - Amazon Nova 2 Sonic セットアップ + サーバー起動
#
# このスクリプトは以下を行います:
#   1. AWS 認証確認
#   2. Bedrock モデル疎通確認
#   3. Python 依存パッケージ確認/インストール
#   4. WebSocket 中継サーバーの起動
#
# 前提:
#   - Python 3.9+ がインストールされていること
#   - AWS CLI 認証が設定済みであること (aws configure)

set -euo pipefail

AWS_REGION="${AWS_REGION:-ap-northeast-1}"
MODEL_ID="amazon.nova-2-sonic-v1:0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Windows 環境では aws.exe を使う場合がある
if command -v aws &>/dev/null; then
  AWS_CMD="aws"
elif command -v aws.exe &>/dev/null; then
  AWS_CMD="aws.exe"
else
  echo "  ⚠️  AWS CLI が見つかりません。"
  echo "  https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
  exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  AWS Deep Cuts - Amazon Nova 2 Sonic"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Region: ${AWS_REGION}"
echo "  Model:  ${MODEL_ID}"
echo ""

# ─── Step 1: AWS 認証確認 ─────────────────────────────────────
echo "Step 1/4: AWS 認証を確認"
ACCOUNT_ID="$(${AWS_CMD} sts get-caller-identity --query Account --output text 2>/dev/null)" || {
  echo "  ⚠️  AWS 認証に失敗しました。"
  echo "  'aws configure' で認証情報を設定してください。"
  exit 1
}
echo "  Account: ${ACCOUNT_ID} ✓"
echo ""

# ─── Step 2: Bedrock モデル疎通確認 ───────────────────────────
echo "Step 2/4: Bedrock モデル疎通を確認"
MODEL_CHECK=$(${AWS_CMD} bedrock get-foundation-model \
  --model-identifier "${MODEL_ID}" \
  --region "${AWS_REGION}" \
  --query "modelDetails.modelId" \
  --output text 2>/dev/null) || true

if [ "${MODEL_CHECK}" = "${MODEL_ID}" ]; then
  echo "  ${MODEL_ID}: OK ✓"
else
  echo ""
  echo "  ⚠️  モデル情報を取得できません。"
  echo ""
  echo "  確認事項:"
  echo "    1. IAM に bedrock 関連権限があるか"
  echo "    2. リージョンが正しいか (現在: ${AWS_REGION})"
  echo "       対応: us-east-1, us-west-2, ap-northeast-1, eu-north-1"
  echo ""
  echo "  ※ 2025年10月以降、手動でのモデル有効化は不要です。"
  echo ""
  echo "  リージョンを変更する場合:"
  echo "    export AWS_REGION=us-east-1 && bash setup.sh"
  exit 1
fi
echo ""

# ─── Step 3: Python 依存パッケージ ────────────────────────────
echo "Step 3/4: Python パッケージを確認"
PYTHON_CMD=""
if command -v python3 &>/dev/null; then
  PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
  PYTHON_CMD="python"
else
  echo "  ⚠️  Python が見つかりません。Python 3.9 以上をインストールしてください。"
  exit 1
fi

# boto3 と websockets の確認・インストール
${PYTHON_CMD} -c "import boto3, websockets" 2>/dev/null || {
  echo "  必要なパッケージをインストールします..."
  ${PYTHON_CMD} -m pip install --quiet boto3 websockets
}
echo "  boto3, websockets: OK ✓"
echo ""

# ─── Step 4: サーバー起動 ─────────────────────────────────────
echo "Step 4/4: WebSocket 中継サーバーを起動"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  セットアップ完了"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  サーバーを起動します。"
echo "  起動したら index.html をブラウザで開いてください。"
echo ""
echo "  停止: Ctrl+C"
echo ""

cd "${SCRIPT_DIR}"
AWS_REGION="${AWS_REGION}" ${PYTHON_CMD} server.py
