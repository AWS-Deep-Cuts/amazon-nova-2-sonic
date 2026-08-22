"""
AWS Deep Cuts: Amazon Nova 2 Sonic — Step 4
マイク入力によるリアルタイム音声会話 (ローカルPC用)

このスクリプトで体験できること:
  - 実際のマイク入力による双方向リアルタイム会話
  - barge-in (割り込み) の動作
  - 8分接続制限の体験
  - サイレンスポンプが実際に動作する様子
  - endpointingSensitivity の体感的な違い

⚠️  注意: このスクリプトは pyaudio が必要です。
   CloudShell ではマイクが使えないため実行できません。
   ローカルPC (macOS/Linux/Windows) で試してください。

   インストール:
     macOS:   brew install portaudio && pip install pyaudio
     Ubuntu:  sudo apt-get install portaudio19-dev && pip install pyaudio
     Windows: pip install pyaudio

実行方法:
  python3 04_realtime_microphone.py [--voice matthew] [--sensitivity MEDIUM]
"""

import json
import uuid
import base64
import os
import sys
import time
import struct
import threading
import argparse

import boto3

# pyaudio がない場合のフォールバック
try:
    import pyaudio
    HAS_PYAUDIO = True
except ImportError:
    HAS_PYAUDIO = False

REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = "amazon.nova-2-sonic-v1:0"

# オーディオ設定
INPUT_SAMPLE_RATE = 16000   # Nova Sonic が期待する入力
INPUT_CHANNELS = 1
INPUT_FORMAT_SIZE = 2       # 16bit = 2 bytes
CHUNK_SAMPLES = 512         # ~32ms at 16kHz

OUTPUT_SAMPLE_RATE = 24000  # Nova Sonic の出力
OUTPUT_CHANNELS = 1


def main():
    parser = argparse.ArgumentParser(description="Nova 2 Sonic リアルタイム音声会話")
    parser.add_argument("--voice", default="matthew", help="voiceId (matthew/tiffany/amy等)")
    parser.add_argument("--sensitivity", default="MEDIUM", choices=["HIGH", "MEDIUM", "LOW"])
    args = parser.parse_args()

    if not HAS_PYAUDIO:
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("  Step 4: マイク入力によるリアルタイム会話")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("")
        print("  ⚠️  pyaudio がインストールされていません。")
        print("")
        print("  このスクリプトはマイクとスピーカーを使う")
        print("  リアルタイム音声会話のデモです。")
        print("  CloudShell では実行できません。")
        print("")
        print("  ローカルPCでのインストール方法:")
        print("    macOS:   brew install portaudio && pip install pyaudio")
        print("    Ubuntu:  sudo apt install portaudio19-dev && pip install pyaudio")
        print("    Windows: pip install pyaudio")
        print("")
        print("  代わりに Step 1〜3 で Nova 2 Sonic の主要機能を")
        print("  テキストベースで体験できます。")
        print("")
        sys.exit(0)

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  Step 4: マイク入力によるリアルタイム会話")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  Voice:       {args.voice}")
    print(f"  Sensitivity: {args.sensitivity}")
    print(f"  Region:      {REGION}")
    print("")
    print("  Ctrl+C で終了")
    print("")

    client = boto3.client("bedrock-runtime", region_name=REGION)
    prompt_name = str(uuid.uuid4())
    audio_content_name = str(uuid.uuid4())

    # ─── イベントキュー（スレッド間通信） ─────────────────────
    from queue import Queue
    event_queue: Queue = Queue()
    is_active = True
    session_start_time = time.time()

    def enqueue_event(event: dict):
        event_queue.put(event)

    def input_stream():
        while True:
            item = event_queue.get()
            if item is None:
                return
            yield {"chunk": {"bytes": json.dumps(item).encode("utf-8")}}

    # ─── 初期イベントをキューに投入 ───────────────────────────

    # SessionStart
    enqueue_event({
        "event": {
            "sessionStart": {
                "inferenceConfiguration": {"maxTokens": 1024, "topP": 0.9, "temperature": 0.7},
                "turnDetectionConfiguration": {"endpointingSensitivity": args.sensitivity},
            }
        }
    })

    # PromptStart
    enqueue_event({
        "event": {
            "promptStart": {
                "promptName": prompt_name,
                "textOutputConfiguration": {"mediaType": "text/plain"},
                "audioOutputConfiguration": {
                    "mediaType": "audio/lpcm",
                    "sampleRateHertz": OUTPUT_SAMPLE_RATE,
                    "sampleSizeBits": 16,
                    "channelCount": 1,
                    "voiceId": args.voice,
                    "encoding": "base64",
                    "audioType": "SPEECH",
                },
            }
        }
    })

    # System Prompt
    system_cn = str(uuid.uuid4())
    enqueue_event({
        "event": {
            "contentStart": {
                "promptName": prompt_name,
                "contentName": system_cn,
                "type": "TEXT",
                "interactive": False,
                "role": "SYSTEM",
                "textInputConfiguration": {"mediaType": "text/plain"},
            }
        }
    })
    enqueue_event({
        "event": {
            "textInput": {
                "promptName": prompt_name,
                "contentName": system_cn,
                "content": (
                    "You are a friendly English conversation partner. "
                    "Keep responses short (1-2 sentences). "
                    "Start by greeting the user."
                ),
            }
        }
    })
    enqueue_event({
        "event": {"contentEnd": {"promptName": prompt_name, "contentName": system_cn}}
    })

    # Audio Input ストリーム開始
    enqueue_event({
        "event": {
            "contentStart": {
                "promptName": prompt_name,
                "contentName": audio_content_name,
                "type": "AUDIO",
                "interactive": True,
                "role": "USER",
                "audioInputConfiguration": {
                    "mediaType": "audio/lpcm",
                    "sampleRateHertz": INPUT_SAMPLE_RATE,
                    "sampleSizeBits": 16,
                    "channelCount": 1,
                    "audioType": "SPEECH",
                    "encoding": "base64",
                },
            }
        }
    })

    # AIに挨拶させる (Model-start-first)
    trigger_cn = str(uuid.uuid4())
    enqueue_event({
        "event": {
            "contentStart": {
                "promptName": prompt_name,
                "contentName": trigger_cn,
                "type": "TEXT",
                "interactive": True,
                "role": "USER",
                "textInputConfiguration": {"mediaType": "text/plain"},
            }
        }
    })
    enqueue_event({
        "event": {
            "textInput": {
                "promptName": prompt_name,
                "contentName": trigger_cn,
                "content": "Hello!",
            }
        }
    })
    enqueue_event({
        "event": {"contentEnd": {"promptName": prompt_name, "contentName": trigger_cn}}
    })

    # ─── マイク入力スレッド ───────────────────────────────────

    pa = pyaudio.PyAudio()
    mic_stream = pa.open(
        format=pyaudio.paInt16,
        channels=INPUT_CHANNELS,
        rate=INPUT_SAMPLE_RATE,
        input=True,
        frames_per_buffer=CHUNK_SAMPLES,
    )

    def mic_thread():
        """マイクから音声を読み取り、Nova Sonic に送信"""
        silence = base64.b64encode(b"\x00" * (CHUNK_SAMPLES * 2)).decode("ascii")
        last_audio_time = time.time()

        while is_active:
            try:
                pcm_data = mic_stream.read(CHUNK_SAMPLES, exception_on_overflow=False)
                audio_b64 = base64.b64encode(pcm_data).decode("ascii")
                enqueue_event({
                    "event": {
                        "audioInput": {
                            "promptName": prompt_name,
                            "contentName": audio_content_name,
                            "content": audio_b64,
                        }
                    }
                })
                last_audio_time = time.time()
            except Exception:
                # オーバーフロー等 — サイレンスを送信
                enqueue_event({
                    "event": {
                        "audioInput": {
                            "promptName": prompt_name,
                            "contentName": audio_content_name,
                            "content": silence,
                        }
                    }
                })
                time.sleep(0.032)

    # ─── スピーカー出力 ───────────────────────────────────────

    speaker_stream = pa.open(
        format=pyaudio.paInt16,
        channels=OUTPUT_CHANNELS,
        rate=OUTPUT_SAMPLE_RATE,
        output=True,
        frames_per_buffer=1024,
    )

    # ─── API呼び出し + レスポンス処理 (メインスレッド) ─────────

    mic_t = threading.Thread(target=mic_thread, daemon=True)
    mic_t.start()
    print("  🎤 マイク起動 — 話しかけてください!")
    print("")

    try:
        response = client.invoke_model_with_bidirectional_stream(
            modelId=MODEL_ID,
            body=input_stream(),
        )

        for event in response.get("body", []):
            if not is_active:
                break

            # 8分制限チェック
            elapsed = time.time() - session_start_time
            if elapsed > 7 * 60 and elapsed < 7 * 60 + 1:
                print("\n  ⚠️  あと1分で8分接続制限に達します")

            if "chunk" in event and "bytes" in event["chunk"]:
                data = json.loads(event["chunk"]["bytes"].decode("utf-8"))

                if "event" in data and "textOutput" in data["event"]:
                    text_out = data["event"]["textOutput"]
                    role = text_out.get("role", "")
                    content = text_out.get("content", "")
                    if content.strip():
                        label = "🎤 You" if role == "USER" else "🤖 AI"
                        print(f"  {label}: {content}")

                elif "event" in data and "audioOutput" in data["event"]:
                    audio_b64 = data["event"]["audioOutput"].get("content", "")
                    if audio_b64:
                        pcm = base64.b64decode(audio_b64)
                        speaker_stream.write(pcm)

    except KeyboardInterrupt:
        print("\n\n  セッション終了 (Ctrl+C)")
    finally:
        is_active = False
        # 終了シーケンス
        enqueue_event({
            "event": {"contentEnd": {"promptName": prompt_name, "contentName": audio_content_name}}
        })
        enqueue_event({"event": {"promptEnd": {"promptName": prompt_name}}})
        enqueue_event({"event": {"sessionEnd": {}}})
        enqueue_event(None)  # ジェネレーター終了

        mic_stream.stop_stream()
        mic_stream.close()
        speaker_stream.stop_stream()
        speaker_stream.close()
        pa.terminate()

        elapsed = time.time() - session_start_time
        print(f"\n  セッション時間: {elapsed:.0f} 秒")
        print("")


if __name__ == "__main__":
    main()
