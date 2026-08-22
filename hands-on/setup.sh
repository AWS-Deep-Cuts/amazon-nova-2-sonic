#!/bin/bash

# AWS Deep Cuts - Amazon Nova 2 Sonic セットアップ + ハンズオン実行
# CloudShell で実行してください。追加インストールは不要です。
#
# このスクリプトは以下を行います:
#   1. AWS 認証確認
#   2. Bedrock モデルアクセス確認
#   3. Step 1〜3 の Python スクリプトを順番に実行
#   4. 結果 HTML を生成
#
# 完了後、output/results.html をダウンロードしてブラウザで開くと
# 音声再生・トランスクリプト・学習ポイントを確認できます。

set -euo pipefail

AWS_REGION="${AWS_REGION:-ap-northeast-1}"
MODEL_ID="amazon.nova-2-sonic-v1:0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  AWS Deep Cuts - Amazon Nova 2 Sonic"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "リージョン: ${AWS_REGION}"
echo "モデル:     ${MODEL_ID}"
echo ""

# ─── Step 0: AWS 認証確認 ─────────────────────────────────────
echo "Step 0/5: AWS 認証を確認"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
echo "  Account: ${ACCOUNT_ID}"
echo ""

# ─── Step 1: Bedrock モデルアクセス確認 ───────────────────────
echo "Step 1/5: Bedrock モデルアクセスを確認"
MODEL_CHECK=$(aws bedrock get-foundation-model \
  --model-identifier "${MODEL_ID}" \
  --region "${AWS_REGION}" \
  --query "modelDetails.modelId" \
  --output text 2>/dev/null) || true

if [ "${MODEL_CHECK}" = "${MODEL_ID}" ]; then
  echo "  ${MODEL_ID}: アクセス可能"
else
  echo ""
  echo "  ⚠️  モデルにアクセスできませんでした。"
  echo "  以下を確認してください:"
  echo "    1. Bedrock コンソール → Model access で ${MODEL_ID} を有効化"
  echo "    2. リージョンが正しいか (現在: ${AWS_REGION})"
  echo "    3. IAM に bedrock:InvokeModelWithBidirectionalStream 権限があるか"
  echo ""
  echo "  対応リージョン: us-east-1, us-west-2, ap-northeast-1, eu-north-1"
  echo ""
  echo "  リージョンを変更する場合:"
  echo "    export AWS_REGION=us-east-1 && bash setup.sh"
  exit 1
fi
echo ""

# ─── Step 2: 基本の双方向ストリーミング ───────────────────────
echo "Step 2/5: 基本の双方向ストリーミング (01_basic_conversation.py)"
echo ""
cd "${SCRIPT_DIR}"
python3 01_basic_conversation.py
echo ""

# ─── Step 3: voiceId と感度の切り替え ─────────────────────────
echo "Step 3/5: voiceId と感度の切り替え (02_voice_and_sensitivity.py)"
echo ""
python3 02_voice_and_sensitivity.py
echo ""

# ─── Step 4: Cross-modal input + Tool use ─────────────────────
echo "Step 4/5: Cross-modal input + Tool use (03_cross_modal_and_tools.py)"
echo ""
python3 03_cross_modal_and_tools.py
echo ""

# ─── Step 5: 結果ページ生成 ───────────────────────────────────
echo "Step 5/5: 結果ページを生成"
python3 generate_results.py
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ハンズオン完了"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "結果を確認するには output/results.html をダウンロードして"
echo "ブラウザで開いてください。"
echo ""
echo "  CloudShell の場合:"
echo "    Actions → Download file → パスに以下を入力:"
echo "    $(pwd)/output/results.html"
echo ""
echo "音声ファイル (WAV) もブラウザ上で再生できます。"
echo ""
echo "クリーンアップ:"
echo "  bash cleanup.sh"
echo ""
