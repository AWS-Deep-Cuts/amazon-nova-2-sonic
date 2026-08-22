#!/bin/bash

# AWS Deep Cuts - Amazon Nova 2 Sonic セットアップ
# CloudShell または Python3 + AWS CLI が使える環境で実行してください。

set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
MODEL_ID="amazon.nova-2-sonic-v1:0"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  AWS Deep Cuts - Amazon Nova 2 Sonic セットアップ"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "リージョン: ${AWS_REGION}"
echo "モデル:     ${MODEL_ID}"
echo ""

# Step 1: AWS 認証確認
echo "Step 1/3: AWS 認証を確認"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
echo "  Account: ${ACCOUNT_ID}"
echo ""

# Step 2: Python 依存パッケージのインストール
echo "Step 2/3: Python 依存パッケージをインストール"
pip install --quiet --upgrade boto3 pyaudio 2>/dev/null || \
pip install --quiet --upgrade boto3 2>/dev/null || \
pip3 install --quiet --upgrade boto3 2>/dev/null

# pyaudio はマイク入力用（Step 4 で使う）。インストールできなくても Step 1〜3 は動く。
if python3 -c "import pyaudio" 2>/dev/null; then
  echo "  boto3: OK"
  echo "  pyaudio: OK (マイク入力が使えます)"
else
  echo "  boto3: OK"
  echo "  pyaudio: 未インストール (Step 4 のマイク入力は使えません — CloudShell では正常)"
fi
echo ""

# Step 3: Bedrock モデルアクセス確認
echo "Step 3/3: Bedrock モデルアクセスを確認"
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

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  セットアップ完了"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "ハンズオンを以下の順番で実行してください:"
echo ""
echo "  Step 1: 基本の双方向ストリーミング (テキスト入力 → 音声出力)"
echo "    python3 01_basic_conversation.py"
echo ""
echo "  Step 2: voiceId・感度の切り替え体験"
echo "    python3 02_voice_and_sensitivity.py"
echo ""
echo "  Step 3: Cross-modal text input + Tool use"
echo "    python3 03_cross_modal_and_tools.py"
echo ""
echo "  Step 4: マイク入力によるリアルタイム音声会話 (pyaudio必須)"
echo "    python3 04_realtime_microphone.py"
echo ""
echo "※ Step 4 はマイクが必要なためCloudShellでは実行できません。"
echo "  ローカルPCで試す場合に使ってください。"
echo ""
