"""
AWS Deep Cuts: Amazon Nova 2 Sonic — Step 1
基本の双方向ストリーミング (テキスト入力 → 音声応答)

このスクリプトで体験できること:
  - InvokeModelWithBidirectionalStream API の基本的な使い方
  - イベントシーケンス: sessionStart → promptStart → systemPrompt → audioInput → sessionEnd
  - テキスト入力（Cross-modal）を使ってAIに話しかける
  - AIの音声応答を WAV ファイルに保存して確認する
  - 55秒無音タイムアウトとサイレンスポンプの仕組み

実行方法:
  python3 01_basic_conversation.py
"""

import json
import uuid
import base64
import wave
import os
import sys

# boto3 は同期クライアントのみ使用（CloudShell互換）
import boto3

REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
MODEL_ID = "amazon.nova-2-sonic-v1:0"
OUTPUT_DIR = "output"

# 出力ディレクトリ作成
os.makedirs(OUTPUT_DIR, exist_ok=True)


def create_event_bytes(event: dict) -> bytes:
    """イベントオブジェクトを API に送信するバイト列に変換"""
    return json.dumps(event).encode("utf-8")


def save_pcm_as_wav(pcm_data: bytes, filename: str, sample_rate: int = 24000):
    """PCM 16bit mono データを WAV ファイルとして保存"""
    filepath = os.path.join(OUTPUT_DIR, filename)
    with wave.open(filepath, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16bit = 2 bytes
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return filepath


def run_conversation():
    """Nova 2 Sonic との基本的な会話を実行"""

    client = boto3.client("bedrock-runtime", region_name=REGION)

    # 一意な識別子
    prompt_name = str(uuid.uuid4())
    system_content_name = str(uuid.uuid4())
    audio_content_name = str(uuid.uuid4())

    # ─── 送信するイベントを順番に組み立てる ───────────────────

    events = []

    # 1. SessionStart — 推論設定とターン検出
    events.append({
        "event": {
            "sessionStart": {
                "inferenceConfiguration": {
                    "maxTokens": 1024,
                    "topP": 0.9,
                    "temperature": 0.7,
                },
                "turnDetectionConfiguration": {
                    "endpointingSensitivity": "MEDIUM",
                },
            }
        }
    })

    # 2. PromptStart — 音声出力の設定
    events.append({
        "event": {
            "promptStart": {
                "promptName": prompt_name,
                "textOutputConfiguration": {"mediaType": "text/plain"},
                "audioOutputConfiguration": {
                    "mediaType": "audio/lpcm",
                    "sampleRateHertz": 24000,
                    "sampleSizeBits": 16,
                    "channelCount": 1,
                    "voiceId": "matthew",  # 米国男性（ポリグロット）
                    "encoding": "base64",
                    "audioType": "SPEECH",
                },
            }
        }
    })

    # 3. System Prompt — AIのペルソナを設定
    events.append({
        "event": {
            "contentStart": {
                "promptName": prompt_name,
                "contentName": system_content_name,
                "type": "TEXT",
                "interactive": False,  # システムプロンプトは非インタラクティブ
                "role": "SYSTEM",
                "textInputConfiguration": {"mediaType": "text/plain"},
            }
        }
    })
    events.append({
        "event": {
            "textInput": {
                "promptName": prompt_name,
                "contentName": system_content_name,
                "content": (
                    "You are a friendly English conversation partner. "
                    "Keep responses short (1-2 sentences). "
                    "Speak naturally and ask follow-up questions."
                ),
            }
        }
    })
    events.append({
        "event": {
            "contentEnd": {
                "promptName": prompt_name,
                "contentName": system_content_name,
            }
        }
    })

    # 4. Audio Input ストリーム開始
    #    Nova 2 Sonic は speech-to-speech モデルなので、
    #    音声入力ストリームを開くことが必須。
    events.append({
        "event": {
            "contentStart": {
                "promptName": prompt_name,
                "contentName": audio_content_name,
                "type": "AUDIO",
                "interactive": True,
                "role": "USER",
                "audioInputConfiguration": {
                    "mediaType": "audio/lpcm",
                    "sampleRateHertz": 16000,
                    "sampleSizeBits": 16,
                    "channelCount": 1,
                    "audioType": "SPEECH",
                    "encoding": "base64",
                },
            }
        }
    })

    # 5. サイレンスポンプ — 無音フレームを送信してタイムアウトを防ぐ
    #    1024 bytes = 16kHz 16bit mono の 32ms 分
    silence_frame = base64.b64encode(b"\x00" * 1024).decode("ascii")
    for _ in range(5):  # 初期の無音を送って接続を安定させる
        events.append({
            "event": {
                "audioInput": {
                    "promptName": prompt_name,
                    "contentName": audio_content_name,
                    "content": silence_frame,
                }
            }
        })

    # 6. Cross-modal Text Input — テキストでAIに話しかける
    #    音声ストリームを維持したまま、テキストを注入する。
    #    これにより「AIが先に話し始める」パターンを実現。
    text_content_name = str(uuid.uuid4())
    events.append({
        "event": {
            "contentStart": {
                "promptName": prompt_name,
                "contentName": text_content_name,
                "type": "TEXT",
                "interactive": True,
                "role": "USER",
                "textInputConfiguration": {"mediaType": "text/plain"},
            }
        }
    })
    events.append({
        "event": {
            "textInput": {
                "promptName": prompt_name,
                "contentName": text_content_name,
                "content": "Hello! I'd like to practice English conversation. What should we talk about?",
            }
        }
    })
    events.append({
        "event": {
            "contentEnd": {
                "promptName": prompt_name,
                "contentName": text_content_name,
            }
        }
    })

    # 追加のサイレンスポンプ（応答を待つ間の接続維持）
    for _ in range(50):
        events.append({
            "event": {
                "audioInput": {
                    "promptName": prompt_name,
                    "contentName": audio_content_name,
                    "content": silence_frame,
                }
            }
        })

    # 7. セッション終了シーケンス
    events.append({
        "event": {
            "contentEnd": {
                "promptName": prompt_name,
                "contentName": audio_content_name,
            }
        }
    })
    events.append({"event": {"promptEnd": {"promptName": prompt_name}}})
    events.append({"event": {"sessionEnd": {}}})

    # ─── 入力ジェネレーター ────────────────────────────────────

    def input_stream():
        for event in events:
            yield {"chunk": {"bytes": create_event_bytes(event)}}

    # ─── API 呼び出しとレスポンス処理 ─────────────────────────

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  Step 1: 基本の双方向ストリーミング")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  Region: {REGION}")
    print(f"  Model:  {MODEL_ID}")
    print(f"  Voice:  matthew (US English, masculine)")
    print("")
    print("Nova 2 Sonic に接続中...")
    print("")

    response = client.invoke_model_with_bidirectional_stream(
        modelId=MODEL_ID,
        body=input_stream(),
    )

    # レスポンス処理
    audio_chunks = []
    transcripts = []

    for event in response.get("body", []):
        if "chunk" in event and "bytes" in event["chunk"]:
            data = json.loads(event["chunk"]["bytes"].decode("utf-8"))

            # テキスト出力 (ASR / AI応答)
            if "event" in data and "textOutput" in data["event"]:
                text_out = data["event"]["textOutput"]
                role = text_out.get("role", "UNKNOWN")
                content = text_out.get("content", "")
                if content.strip():
                    transcripts.append((role, content))
                    label = "🎤 You" if role == "USER" else "🤖 AI"
                    print(f"  {label}: {content}")

            # 音声出力
            elif "event" in data and "audioOutput" in data["event"]:
                audio_b64 = data["event"]["audioOutput"].get("content", "")
                if audio_b64:
                    audio_chunks.append(base64.b64decode(audio_b64))
                    sys.stdout.write("♪")
                    sys.stdout.flush()

            # contentStart (デバッグ用)
            elif "event" in data and "contentStart" in data["event"]:
                cs = data["event"]["contentStart"]
                stage = ""
                if cs.get("additionalModelFields"):
                    try:
                        fields = json.loads(cs["additionalModelFields"])
                        stage = f" [{fields.get('generationStage', '')}]"
                    except:
                        pass

    print("")
    print("")

    # 音声を WAV ファイルに保存
    if audio_chunks:
        all_audio = b"".join(audio_chunks)
        wav_path = save_pcm_as_wav(all_audio, "step1_response.wav")
        duration = len(all_audio) / (24000 * 2)  # 24kHz, 16bit
        print(f"  📁 音声を保存しました: {wav_path}")
        print(f"     長さ: {duration:.1f} 秒")
        print(f"     フォーマット: PCM 24kHz 16bit mono")
    else:
        print("  ⚠️  音声出力がありませんでした。")

    # トランスクリプトをファイルに保存
    if transcripts:
        txt_path = os.path.join(OUTPUT_DIR, "step1_transcript.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            for role, content in transcripts:
                label = "You" if role == "USER" else "AI"
                f.write(f"[{label}] {content}\n")
        print(f"  📁 トランスクリプト: {txt_path}")

    print("")
    print("─── 学習ポイント ───────────────────────────────────")
    print("")
    print("  1. Nova 2 Sonic は speech-to-speech モデルなので、")
    print("     音声入力ストリーム (audioInput) を開くことが必須です。")
    print("     純粋なテキスト→音声変換 (TTS) としては使えません。")
    print("")
    print("  2. サイレンスポンプ: 55秒間音声入力がないとタイムアウトします。")
    print("     無音データ (ゼロ埋め PCM) を定期送信して接続を維持します。")
    print("")
    print("  3. Cross-modal text input: 音声ストリームを維持したまま")
    print("     テキストを注入し、AIに音声で応答させることができます。")
    print("")
    print("  4. generationStage: テキスト出力には SPECULATIVE (予測) と")
    print("     FINAL (確定) があります。UIには FINAL のみ使うべきです。")
    print("")


if __name__ == "__main__":
    run_conversation()

    # results.html を生成（ブラウザで WAV 再生可能）
    from generate_results import generate_results_html
    html_path = generate_results_html()
    print(f"  📄 結果ページを生成しました: {html_path}")
    print(f"     ダウンロードしてブラウザで開くと音声を再生できます。")
