"""
AWS Deep Cuts: Amazon Nova 2 Sonic — WebSocket 中継サーバー

ブラウザ (index.html) と Bedrock Nova 2 Sonic の間を中継する。
セキュリティ: 127.0.0.1 にのみバインドし、外部からのアクセスを遮断する。

起動方法:
  python3 server.py

依存パッケージ:
  pip install boto3 websockets
"""

import asyncio
import json
import uuid
import base64
import os
import signal
import sys
from typing import Optional

import boto3
import websockets
from websockets.server import serve

# ─── 設定 ────────────────────────────────────────────────────────
HOST = "127.0.0.1"  # localhost のみ — セキュリティのため外部バインドしない
PORT = int(os.environ.get("PORT", "8765"))
REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
MODEL_ID = "amazon.nova-2-sonic-v1:0"

# ─── ツール読み込み ──────────────────────────────────────────────
from tools.weather_mcp import get_weather, WEATHER_TOOL_SPEC


# ─── Bedrock セッション ──────────────────────────────────────────
class SonicSession:
    """1つのブラウザ接続に対応する Nova 2 Sonic セッション"""

    def __init__(self, ws, config: dict):
        self.ws = ws
        self.config = config
        self.prompt_name = str(uuid.uuid4())
        self.audio_content_name = str(uuid.uuid4())
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.is_active = False
        self.client = boto3.client("bedrock-runtime", region_name=REGION)

    async def start(self):
        self.is_active = True

        system_prompt = self.config.get("systemPrompt", "You are a helpful assistant.")
        voice_id = self.config.get("voiceId", "matthew")
        sensitivity = self.config.get("sensitivity", "MEDIUM")
        enable_tools = self.config.get("enableTools", False)

        # 1. SessionStart
        await self._enqueue({
            "event": {
                "sessionStart": {
                    "inferenceConfiguration": {"maxTokens": 1024, "topP": 0.9, "temperature": 0.7},
                    "turnDetectionConfiguration": {"endpointingSensitivity": sensitivity},
                }
            }
        })

        # 2. PromptStart
        prompt_start: dict = {
            "event": {
                "promptStart": {
                    "promptName": self.prompt_name,
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
        }

        if enable_tools:
            prompt_start["event"]["promptStart"]["toolUseOutputConfiguration"] = {
                "mediaType": "application/json"
            }
            prompt_start["event"]["promptStart"]["toolConfiguration"] = {
                "tools": [WEATHER_TOOL_SPEC],
                "toolChoice": {"auto": {}},
            }

        await self._enqueue(prompt_start)

        # 3. System Prompt
        sys_cn = str(uuid.uuid4())
        await self._enqueue({
            "event": {
                "contentStart": {
                    "promptName": self.prompt_name,
                    "contentName": sys_cn,
                    "type": "TEXT",
                    "interactive": False,
                    "role": "SYSTEM",
                    "textInputConfiguration": {"mediaType": "text/plain"},
                }
            }
        })
        await self._enqueue({
            "event": {
                "textInput": {
                    "promptName": self.prompt_name,
                    "contentName": sys_cn,
                    "content": system_prompt,
                }
            }
        })
        await self._enqueue({
            "event": {"contentEnd": {"promptName": self.prompt_name, "contentName": sys_cn}}
        })

        # 4. Audio Input ストリーム開始
        await self._enqueue({
            "event": {
                "contentStart": {
                    "promptName": self.prompt_name,
                    "contentName": self.audio_content_name,
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

        # Bedrock ストリーム開始
        asyncio.create_task(self._run_stream())

    async def send_audio(self, base64_data: str):
        """ブラウザから受信した音声チャンクを Nova Sonic に転送"""
        if not self.is_active:
            return
        await self._enqueue({
            "event": {
                "audioInput": {
                    "promptName": self.prompt_name,
                    "contentName": self.audio_content_name,
                    "content": base64_data,
                }
            }
        })

    async def inject_text(self, text: str):
        """Cross-modal text input"""
        if not self.is_active:
            return
        cn = str(uuid.uuid4())
        await self._enqueue({
            "event": {
                "contentStart": {
                    "promptName": self.prompt_name,
                    "contentName": cn,
                    "type": "TEXT",
                    "interactive": True,
                    "role": "USER",
                    "textInputConfiguration": {"mediaType": "text/plain"},
                }
            }
        })
        await self._enqueue({
            "event": {
                "textInput": {
                    "promptName": self.prompt_name,
                    "contentName": cn,
                    "content": text,
                }
            }
        })
        await self._enqueue({
            "event": {"contentEnd": {"promptName": self.prompt_name, "contentName": cn}}
        })

    async def close(self):
        if not self.is_active:
            return
        self.is_active = False
        await self._enqueue({
            "event": {"contentEnd": {"promptName": self.prompt_name, "contentName": self.audio_content_name}}
        })
        await self._enqueue({"event": {"promptEnd": {"promptName": self.prompt_name}}})
        await self._enqueue({"event": {"sessionEnd": {}}})
        await self._enqueue(None)  # ジェネレーター終了シグナル

    async def _enqueue(self, event):
        await self.event_queue.put(event)

    async def _input_generator(self):
        while True:
            item = await self.event_queue.get()
            if item is None:
                return
            yield {"chunk": {"bytes": json.dumps(item).encode("utf-8")}}

    async def _run_stream(self):
        """Bedrock との双方向ストリームを管理"""
        try:
            response = self.client.invoke_model_with_bidirectional_stream(
                modelId=MODEL_ID,
                body=self._sync_input_generator(),
            )

            for event in response.get("body", []):
                if not self.is_active:
                    break
                if "chunk" in event and "bytes" in event["chunk"]:
                    await self._handle_output(event["chunk"]["bytes"])

        except Exception as e:
            if self.is_active:
                await self._send_ws({"type": "error", "message": str(e)})
        finally:
            self.is_active = False
            await self._send_ws({"type": "state", "state": "ended"})

    def _sync_input_generator(self):
        """同期ジェネレーター（boto3用）— asyncio キューからイベントを取り出す"""
        loop = asyncio.get_event_loop()
        while True:
            future = asyncio.run_coroutine_threadsafe(self.event_queue.get(), loop)
            item = future.result()
            if item is None:
                return
            yield {"chunk": {"bytes": json.dumps(item).encode("utf-8")}}

    async def _handle_output(self, raw_bytes: bytes):
        """Bedrock からの出力イベントを処理"""
        data = json.loads(raw_bytes.decode("utf-8"))

        if "event" not in data:
            return

        evt = data["event"]

        # テキスト出力
        if "textOutput" in evt:
            content = evt["textOutput"].get("content", "")
            role = evt["textOutput"].get("role", "ASSISTANT")
            if content.strip():
                await self._send_ws({"type": "transcript", "role": role, "content": content})

        # 音声出力
        elif "audioOutput" in evt:
            audio = evt["audioOutput"].get("content", "")
            if audio:
                await self._send_ws({"type": "audio", "data": audio})

        # Tool use
        elif "toolUse" in evt:
            tool_name = evt["toolUse"].get("toolName", "")
            tool_use_id = evt["toolUse"].get("toolUseId", "")
            tool_content = evt["toolUse"].get("content", "{}")

            await self._send_ws({
                "type": "toolCall",
                "toolName": tool_name,
                "params": tool_content,
            })

            # ツール実行
            result = await self._execute_tool(tool_name, tool_content)

            # ToolResult を返す
            await self._enqueue({
                "event": {
                    "toolResult": {
                        "promptName": self.prompt_name,
                        "contentName": str(uuid.uuid4()),
                        "content": json.dumps(result),
                    }
                }
            })

    async def _execute_tool(self, tool_name: str, params_json: str) -> dict:
        """ツールを実行して結果を返す"""
        try:
            params = json.loads(params_json)
        except json.JSONDecodeError:
            return {"error": "Invalid JSON parameters"}

        if tool_name == "get_weather":
            return await get_weather(params)
        else:
            return {"error": f"Unknown tool: {tool_name}"}

    async def _send_ws(self, msg: dict):
        try:
            await self.ws.send(json.dumps(msg))
        except websockets.exceptions.ConnectionClosed:
            pass


# ─── WebSocket ハンドラー ─────────────────────────────────────────
async def handle_connection(ws):
    print(f"[WS] Client connected")
    session: Optional[SonicSession] = None

    try:
        async for raw in ws:
            msg = json.loads(raw)
            msg_type = msg.get("type", "")

            if msg_type == "start":
                # 新しいセッション開始
                if session:
                    await session.close()
                session = SonicSession(ws, msg.get("config", {}))
                await session.start()
                await ws.send(json.dumps({"type": "state", "state": "active"}))

            elif msg_type == "audio" and session:
                await session.send_audio(msg.get("data", ""))

            elif msg_type == "textInject" and session:
                await session.inject_text(msg.get("content", ""))

            elif msg_type == "stop":
                if session:
                    await session.close()
                    session = None

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        if session:
            await session.close()
        print(f"[WS] Client disconnected")


# ─── サーバー起動 ─────────────────────────────────────────────────
async def main():
    print("")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  AWS Deep Cuts: Amazon Nova 2 Sonic")
    print("  WebSocket Relay Server")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  WebSocket: ws://{HOST}:{PORT}")
    print(f"  Region:    {REGION}")
    print(f"  Model:     {MODEL_ID}")
    print(f"  Security:  127.0.0.1 only (外部アクセス不可)")
    print("")
    print("  index.html をブラウザで開いてください。")
    print("  Ctrl+C で停止します。")
    print("")

    async with serve(handle_connection, HOST, PORT):
        await asyncio.Future()  # 永続待機


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Server] Stopped")
