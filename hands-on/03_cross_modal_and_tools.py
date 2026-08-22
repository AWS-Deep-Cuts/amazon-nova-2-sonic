"""
AWS Deep Cuts: Amazon Nova 2 Sonic — Step 3
Cross-modal Text Input + Tool Use (関数呼び出し)

このスクリプトで体験できること:
  - Cross-modal text input で複数ターンの会話を駆動する
  - Tool use (関数呼び出し) の定義と応答処理
  - 非同期ツールコールの仕組み
  - toolChoice パラメータ (auto/any/tool) の違い
  - edTech応用: 構造化された発話評価の取得

実行方法:
  python3 03_cross_modal_and_tools.py
"""

import json
import uuid
import base64
import wave
import os
import sys
import time

import boto3

REGION = os.environ.get("AWS_REGION", "us-east-1")
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


# ─── Tool 定義 ─────────────────────────────────────────────────
# Nova 2 Sonic に「発話評価」ツールを教える。
# モデルは会話の中で必要と判断したタイミングでこのツールを呼び出す。

EVALUATE_TOOL = {
    "toolSpec": {
        "name": "evaluate_english",
        "description": (
            "Evaluate the student's English proficiency based on the conversation so far. "
            "Call this tool after the student has spoken at least 2 sentences. "
            "Provide scores and specific improvement suggestions."
        ),
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "grammar_score": {
                        "type": "number",
                        "description": "Grammar accuracy score from 1-10",
                    },
                    "vocabulary_score": {
                        "type": "number",
                        "description": "Vocabulary range and appropriateness from 1-10",
                    },
                    "overall_level": {
                        "type": "string",
                        "description": "CEFR level estimate: A1, A2, B1, B2, C1, or C2",
                    },
                    "feedback": {
                        "type": "string",
                        "description": "Brief feedback in English (1-2 sentences)",
                    },
                },
                "required": ["grammar_score", "vocabulary_score", "overall_level", "feedback"],
            }
        },
    }
}


def run_tool_use_session():
    """Tool use を含むマルチターン会話を実行"""

    client = boto3.client("bedrock-runtime", region_name=REGION)
    prompt_name = str(uuid.uuid4())
    audio_content_name = str(uuid.uuid4())
    silence_frame = base64.b64encode(b"\x00" * 1024).decode("ascii")

    events = []

    # ─── セッション初期化 ─────────────────────────────────────

    # SessionStart
    events.append({
        "event": {
            "sessionStart": {
                "inferenceConfiguration": {"maxTokens": 1024, "topP": 0.9, "temperature": 0.7},
                "turnDetectionConfiguration": {"endpointingSensitivity": "MEDIUM"},
            }
        }
    })

    # PromptStart (ツール設定を含む)
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
                    "voiceId": "tiffany",
                    "encoding": "base64",
                    "audioType": "SPEECH",
                },
                # ─── Tool Configuration ───
                "toolUseOutputConfiguration": {"mediaType": "application/json"},
                "toolConfiguration": {
                    "tools": [EVALUATE_TOOL],
                    "toolChoice": {"auto": {}},  # モデルが必要と判断した時に呼び出す
                },
            }
        }
    })

    # System Prompt (評価ツールの使用を促す)
    system_content_name = str(uuid.uuid4())
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
                "content": (
                    "You are an English tutor having a conversation with a Japanese student. "
                    "Ask questions and respond naturally. After the student speaks 2-3 times, "
                    "use the evaluate_english tool to assess their proficiency level. "
                    "Keep your responses short (1-2 sentences)."
                ),
            }
        }
    })
    events.append({
        "event": {"contentEnd": {"promptName": prompt_name, "contentName": system_content_name}}
    })

    # Audio Input ストリーム開始
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

    # サイレンスポンプ
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

    # ─── マルチターン会話（テキスト注入で模擬） ───────────────
    # 実際のedTechアプリでは、ここがマイク音声入力に置き換わる。
    # ハンズオンではテキスト注入で生徒の発話を模擬する。

    student_messages = [
        "Hello! I am study English for three years. I want to improve my speaking.",
        "Yesterday I go to the park with my friends. We play soccer and have lunch.",
        "I think English is very difficult but I enjoy learning new words every day.",
    ]

    for msg in student_messages:
        # サイレンスポンプ（AIの応答を待つ）
        for _ in range(30):
            events.append({
                "event": {
                    "audioInput": {
                        "promptName": prompt_name,
                        "contentName": audio_content_name,
                        "content": silence_frame,
                    }
                }
            })

        # 生徒の発話（Cross-modal text input）
        text_name = str(uuid.uuid4())
        events.append({
            "event": {
                "contentStart": {
                    "promptName": prompt_name,
                    "contentName": text_name,
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
                    "contentName": text_name,
                    "content": msg,
                }
            }
        })
        events.append({
            "event": {"contentEnd": {"promptName": prompt_name, "contentName": text_name}}
        })

    # 最後のサイレンスポンプ（ツール呼び出しを待つ）
    for _ in range(60):
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

    # ─── 入力ジェネレーター ────────────────────────────────────

    # Tool use の場合、toolResult を動的に返す必要がある。
    # ただし同期ストリームでは応答途中にイベントを追加できないため、
    # ここでは events リストの末尾に toolResult を追加するパターンは使えない。
    # 実際のアプリケーションでは非同期ジェネレーター or キュー方式を使う。
    #
    # このハンズオンでは、toolResult が返せない場合のモデルの動作も観察する。
    # → モデルはtoolResultを待ってから次の応答を生成する。

    def input_stream():
        for event in events:
            yield {"chunk": {"bytes": json.dumps(event).encode("utf-8")}}

    # ─── 実行 ─────────────────────────────────────────────────

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  Step 3: Cross-modal Text Input + Tool Use")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("")
    print("  生徒の発話をテキスト注入で模擬し、3ターン会話後に")
    print("  AIが evaluate_english ツールを呼び出すかを観察します。")
    print("")
    print("  生徒の模擬発話（意図的に文法ミスを含む）:")
    for i, msg in enumerate(student_messages, 1):
        print(f"    {i}. \"{msg}\"")
    print("")
    print("Nova 2 Sonic に接続中...")
    print("")

    response = client.invoke_model_with_bidirectional_stream(
        modelId=MODEL_ID,
        body=input_stream(),
    )

    # レスポンス処理
    audio_chunks = []
    tool_calls = []
    turn_count = 0

    for event in response.get("body", []):
        if "chunk" in event and "bytes" in event["chunk"]:
            data = json.loads(event["chunk"]["bytes"].decode("utf-8"))

            # テキスト出力
            if "event" in data and "textOutput" in data["event"]:
                text_out = data["event"]["textOutput"]
                role = text_out.get("role", "")
                content = text_out.get("content", "")
                if content.strip():
                    if role == "USER":
                        print(f"  🎤 Student: {content}")
                    else:
                        print(f"  🤖 Tutor:   {content}")

            # 音声出力
            elif "event" in data and "audioOutput" in data["event"]:
                audio_b64 = data["event"]["audioOutput"].get("content", "")
                if audio_b64:
                    audio_chunks.append(base64.b64decode(audio_b64))

            # ─── Tool Use イベント ───
            elif "event" in data and "toolUse" in data["event"]:
                tool_use = data["event"]["toolUse"]
                tool_name = tool_use.get("toolName", "")
                tool_content = tool_use.get("content", "{}")
                tool_calls.append({"name": tool_name, "params": tool_content})
                print("")
                print(f"  🔧 Tool呼び出し検出: {tool_name}")
                try:
                    params = json.loads(tool_content)
                    print(f"     パラメータ: {json.dumps(params, indent=6, ensure_ascii=False)}")
                except:
                    print(f"     Raw: {tool_content}")
                print("")

    print("")

    # WAV保存
    if audio_chunks:
        all_audio = b"".join(audio_chunks)
        wav_path = save_pcm_as_wav(all_audio, "step3_tool_use.wav")
        duration = len(all_audio) / (24000 * 2)
        print(f"  📁 音声保存: {wav_path} ({duration:.1f}秒)")
    print("")

    # Tool呼び出し結果のまとめ
    if tool_calls:
        print("─── Tool Use 結果 ─────────────────────────────────")
        print("")
        for i, tc in enumerate(tool_calls, 1):
            print(f"  ツール #{i}: {tc['name']}")
            try:
                params = json.loads(tc["params"])
                for key, val in params.items():
                    print(f"    {key}: {val}")
            except:
                print(f"    (パース不可)")
            print("")
    else:
        print("  ℹ️  今回はツールが呼び出されませんでした。")
        print("     (toolChoice: auto のため、モデルが不要と判断した可能性があります)")
        print("     実際のアプリでは toolChoice: {tool: {name: 'evaluate_english'}}")
        print("     で強制呼び出しすることも可能です。")
        print("")

    # ─── 学習ポイント ─────────────────────────────────────────
    print("─── 学習ポイント ───────────────────────────────────")
    print("")
    print("  1. Tool use の流れ:")
    print("     promptStart で toolConfiguration を定義")
    print("     → モデルが必要と判断すると toolUse イベントを送信")
    print("     → アプリが toolResult イベントで結果を返す")
    print("     → モデルが結果を組み込んで応答を生成")
    print("")
    print("  2. toolChoice の3つの選択肢:")
    print("     auto  — モデルが判断 (推奨、最も自然)")
    print("     any   — 必ずいずれかのツールを呼び出す")
    print("     tool  — 特定のツールを強制呼び出し")
    print("")
    print("  3. 非同期ツールコール:")
    print("     Nova 2 Sonic はツール実行中も会話を継続できる。")
    print("     「分析中です、少々お待ちください」と言いながら")
    print("     バックグラウンドでツールを実行する設計が可能。")
    print("")
    print("  4. edTech応用:")
    print("     - リアルタイム発話評価（CEFR レベル判定）")
    print("     - 学習履歴DB への自動記録")
    print("     - 弱点に基づくアダプティブ出題")
    print("     - 外部API連携（辞書検索、例文生成）")
    print("")


if __name__ == "__main__":
    run_tool_use_session()
