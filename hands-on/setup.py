#!/usr/bin/env python3
"""AWS Deep Cuts - Amazon Nova 2 Sonic セットアップ + サーバー起動

このスクリプトは以下を行います:
  1. AWS 認証確認
  2. Bedrock モデル疎通確認
  3. Python 依存パッケージ確認/インストール
  4. WebSocket 中継サーバーの起動

前提:
  - Python 3.9+ がインストールされていること
  - AWS CLI 認証が設定済みであること (aws configure)
"""

import os
import sys
import subprocess
import importlib
from pathlib import Path

# Windows コンソールの文字化け対策
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    os.environ.setdefault("PYTHONUTF8", "1")

AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
MODEL_ID = "amazon.nova-2-sonic-v1:0"
SCRIPT_DIR = Path(__file__).resolve().parent


def print_header():
    print()
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  AWS Deep Cuts - Amazon Nova 2 Sonic")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()
    print(f"  Region: {AWS_REGION}")
    print(f"  Model:  {MODEL_ID}")
    print()


def check_and_install_packages():
    """Step 3: 必要パッケージの確認・インストール"""
    required = ["boto3", "websockets"]
    missing = []
    for pkg in required:
        try:
            importlib.import_module(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"  インストール中: {', '.join(missing)}...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet"] + missing,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # 再度インポートテスト
        for pkg in missing:
            importlib.import_module(pkg)

    print("  boto3, websockets: OK ✓")


def check_auth():
    """Step 1: AWS 認証確認"""
    import boto3
    try:
        sts = boto3.client("sts")
        identity = sts.get_caller_identity()
        account_id = identity["Account"]
        print(f"  Account: {account_id} ✓")
        return True
    except Exception as e:
        print()
        print("  ⚠️  AWS 認証に失敗しました。")
        print("  'aws configure' で認証情報を設定してください。")
        print()
        print(f"  エラー: {e}")
        return False


def check_model():
    """Step 2: Bedrock モデル疎通確認"""
    import boto3
    try:
        client = boto3.client("bedrock", region_name=AWS_REGION)
        resp = client.get_foundation_model(modelIdentifier=MODEL_ID)
        model_id = resp["modelDetails"]["modelId"]
        if model_id == MODEL_ID:
            print(f"  {MODEL_ID}: OK ✓")
            return True
    except Exception as e:
        pass

    print()
    print("  ⚠️  モデル情報を取得できません。")
    print()
    print("  確認事項:")
    print("    1. IAM に bedrock 関連権限があるか")
    print(f"    2. リージョンが正しいか (現在: {AWS_REGION})")
    print("       対応: us-east-1, us-west-2, ap-northeast-1, eu-north-1")
    print()
    print("  ※ 2025年10月以降、手動でのモデル有効化は不要です。")
    print()
    print("  リージョンを変更する場合:")
    if sys.platform == "win32":
        print('    $env:AWS_REGION="us-east-1"; python setup.py')
    else:
        print("    export AWS_REGION=us-east-1 && python3 setup.py")
    return False


def main():
    print_header()

    # Step 3 を先に (boto3 が必要なため)
    print("Step 1/4: Python パッケージを確認")
    try:
        check_and_install_packages()
    except Exception as e:
        print(f"  ⚠️  パッケージのインストールに失敗しました: {e}")
        print(f"  手動で実行してください: {sys.executable} -m pip install boto3 websockets")
        sys.exit(1)
    print()

    # Step 1: 認証
    print("Step 2/4: AWS 認証を確認")
    if not check_auth():
        sys.exit(1)
    print()

    # Step 2: モデル疎通
    print("Step 3/4: Bedrock モデル疎通を確認")
    if not check_model():
        sys.exit(1)
    print()

    # Step 4: サーバー起動
    print("Step 4/4: WebSocket 中継サーバーを起動")
    print()
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  セットアップ完了")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()
    print("  サーバーを起動します。")
    print("  起動したら index.html をブラウザで開いてください。")
    print()
    print("  停止: Ctrl+C")
    print()

    os.chdir(SCRIPT_DIR)
    os.environ["AWS_REGION"] = AWS_REGION
    try:
        proc = subprocess.Popen([sys.executable, str(SCRIPT_DIR / "server.py")])
        proc.wait()
    except KeyboardInterrupt:
        # Ctrl+C を子プロセスに伝播（子プロセスも SIGINT を受ける）
        proc.terminate()
        proc.wait(timeout=5)
        print("\n[setup] Server stopped")


if __name__ == "__main__":
    main()
