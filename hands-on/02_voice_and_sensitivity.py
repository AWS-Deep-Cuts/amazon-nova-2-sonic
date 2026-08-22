"""
AWS Deep Cuts: Amazon Nova 2 Sonic — Step 2
voiceId と endpointingSensitivity の切り替え体験

このスクリプトで体験できること:
  - 異なる voiceId で同じテキストを話させ、声質の違いを聴き比べる
  - endpointingSensitivity の3段階 (HIGH/MEDIUM/LOW) の動作を理解する
  - ポリグロットボイス (matthew/tiffany) の多言語対応を確認する
  - 1セッション = 1voiceId の制約を理解する

実行方法:
  python3 02_voice_and_sensitivity.py
"""

import json
import uuid
import base64
import wave
import os
import sys

import boto3

REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
MODEL_ID = "amazon.nova-2-sonic-v1:0"
OUTPUT_DIR = "output"

os.makedirs(OUTPUT_DIR, exist_ok=True)


def save_pcm_as_wav(pcm_data: bytes, filename: str, sample_rate: int = 24000):
    filepath = os.path.join(OUTPUT_DIR, filename)
    with wave.open(filepath, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return filepath


def run_single_session(voice_id: str, sensitivity: str, text: str, label: str):
    """1つのセッションでテキストを注入し、音声応答を取得"""

    client = boto3.client("bedrock-runtime", region_name=REGION)
    prompt_name = str(uuid.uuid4())
    system_content_name = str(uuid.uuid4())
    audio_content_name = str(uuid.uuid4())

    silence_frame = base64.b64encode(b"\x00" * 1024).decode("ascii")

    events = []

    # SessionStart
    events.append({
        "event": {
            "sessionStart": {
                "inferenceConfiguration": {"maxTokens": 512, "topP": 0.9, "temperature": 0.7},
                "turnDetectionConfiguration": {"endpointingSensitivity": sensitivity},
            }
        }
    })

    # PromptStart
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
                    "voiceId": voice_id,
                    "encoding": "base64",
                    "audioType": "SPEECH",
                },
            }
        }
    })

    # System Prompt
    events.append({
        "event": {
            "contentStart": {
                "promptName": prompt_name,
                "contentName": system_content_name,
                "type": "TEXT",
                "interactive": False,
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
                "content": "You are a helpful assistant. Respond briefly in 1-2 sentences. Speak the language that the user speaks.",
            }
        }
    })
    events.append({
        "event": {"contentEnd": {"promptName": prompt_name, "contentName": system_content_name}}
    })

    # Audio Input ストリーム開始 + サイレンス
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

    for _ in range(5):
        events.append({
            "event": {
                "audioInput": {
                    "promptName": prompt_name,
                    "contentName": audio_content_name,
                    "content": silence_frame,
                }
            }
        })

    # Cross-modal text input
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
                "content": text,
            }
        }
    })
    events.append({
        "event": {"contentEnd": {"promptName": prompt_name, "contentName": text_content_name}}
    })

    # サイレンスポンプ（応答を待つ）
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

    # 終了シーケンス
    events.append({
        "event": {"contentEnd": {"promptName": prompt_name, "contentName": audio_content_name}}
    })
    events.append({"event": {"promptEnd": {"promptName": prompt_name}}})
    events.append({"event": {"sessionEnd": {}}})

    def input_stream():
        for event in events:
            yield {"chunk": {"bytes": json.dumps(event).encode("utf-8")}}

    # 実行
    print(f"  {label}")
    print(f"    voiceId: {voice_id}, sensitivity: {sensitivity}")
    print(f"    入力: \"{text}\"")
    sys.stdout.write("    応答: ")
    sys.stdout.flush()

    response = client.invoke_model_with_bidirectional_stream(
        modelId=MODEL_ID,
        body=input_stream(),
    )

    audio_chunks = []
    response_text = ""

    for event in response.get("body", []):
        if "chunk" in event and "bytes" in event["chunk"]:
            data = json.loads(event["chunk"]["bytes"].decode("utf-8"))

            if "event" in data and "textOutput" in data["event"]:
                text_out = data["event"]["textOutput"]
                role = text_out.get("role", "")
                content = text_out.get("content", "")
                if role == "ASSISTANT" and content.strip():
                    response_text += content

            elif "event" in data and "audioOutput" in data["event"]:
                audio_b64 = data["event"]["audioOutput"].get("content", "")
                if audio_b64:
                    audio_chunks.append(base64.b64decode(audio_b64))

    print(response_text or "(テキスト出力なし)")

    # WAV保存
    if audio_chunks:
        all_audio = b"".join(audio_chunks)
        safe_label = label.replace(" ", "_").replace("/", "_").lower()
        wav_path = save_pcm_as_wav(all_audio, f"step2_{safe_label}.wav")
        duration = len(all_audio) / (24000 * 2)
        print(f"    📁 {wav_path} ({duration:.1f}秒)")
    else:
        print("    ⚠️  音声出力なし")
    print("")


def main():
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  Step 2: voiceId と endpointingSensitivity の切り替え")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("")

    # ─── パート A: voiceId の聴き比べ ─────────────────────────
    print("── Part A: voiceId の聴き比べ ──────────────────────")
    print("   同じ質問を異なる声で応答させます。")
    print("")

    voices = [
        ("matthew", "米国男性 — ポリグロット (全7言語対応)"),
        ("tiffany", "米国女性 — ポリグロット (全7言語対応)"),
        ("amy", "英国女性 — British English"),
    ]

    for voice_id, desc in voices:
        run_single_session(
            voice_id=voice_id,
            sensitivity="MEDIUM",
            text="Tell me one interesting fact about the English language.",
            label=f"{voice_id} ({desc})",
        )

    # ─── パート B: ポリグロットの多言語対応 ────────────────────
    print("── Part B: ポリグロットの多言語対応 ─────────────────")
    print("   matthew (ポリグロット) に異なる言語で話しかけます。")
    print("   同じ声のまま言語が切り替わることを確認してください。")
    print("")

    multilingual = [
        ("Hello! How are you today?", "English"),
        ("Bonjour! Comment allez-vous?", "French"),
        ("Hola! Como estas hoy?", "Spanish"),
    ]

    for text, lang in multilingual:
        run_single_session(
            voice_id="matthew",
            sensitivity="MEDIUM",
            text=text,
            label=f"matthew × {lang}",
        )

    # ─── パート C: endpointingSensitivity の解説 ──────────────
    print("── Part C: endpointingSensitivity ───────────────────")
    print("")
    print("   endpointingSensitivity は「ユーザーが話し終わった」と")
    print("   判定するまでの待ち時間を制御します:")
    print("")
    print("   ┌─────────┬────────────────────────────────────────┐")
    print("   │  HIGH   │ 短い沈黙で即応答 (~1.5秒)              │")
    print("   │         │ → 上級者のテンポの良い会話向け          │")
    print("   ├─────────┼────────────────────────────────────────┤")
    print("   │  MEDIUM │ バランス型 (デフォルト推奨)              │")
    print("   ├─────────┼────────────────────────────────────────┤")
    print("   │  LOW    │ 長い沈黙も待つ (~2秒)                  │")
    print("   │         │ → 初心者が考えながら話す場面向け        │")
    print("   └─────────┴────────────────────────────────────────┘")
    print("")
    print("   ※ このパラメータはマイク入力時に効果を発揮します。")
    print("     テキスト入力では違いが出ないため、Step 4 (マイク入力)")
    print("     で実際に体感してください。")
    print("")

    # ─── まとめ ───────────────────────────────────────────────
    print("─── 学習ポイント ───────────────────────────────────")
    print("")
    print("  1. 1セッション = 1 voiceId の制約")
    print("     セッション途中で声を変えることはできません。")
    print("     複数キャラクターには複数セッションが必要です。")
    print("")
    print("  2. ポリグロットボイス (matthew, tiffany) は")
    print("     7言語全てに対応。言語ごとにvoiceIdを変える必要なし。")
    print("")
    print("  3. endpointingSensitivity は教育用途で重要:")
    print("     初心者 → LOW (考える時間を確保)")
    print("     上級者 → HIGH (自然な会話テンポ)")
    print("")
    print("  4. edTech応用: 学習者のレベル判定結果に基づいて")
    print("     sensitivity を動的に切り替えるアダプティブ設計が可能。")
    print("")


if __name__ == "__main__":
    main()

    # results.html を生成（ブラウザで WAV 再生可能）
    from generate_results import generate_results_html
    html_path = generate_results_html()
    print(f"  📄 結果ページを生成しました: {html_path}")
    print(f"     ダウンロードしてブラウザで開くと音声を再生できます。")
