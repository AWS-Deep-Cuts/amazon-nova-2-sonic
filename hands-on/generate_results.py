"""
results.html 生成ユーティリティ

各ステップの実行結果（WAVファイル、トランスクリプト、学習ポイント）を
ブラウザで確認できる HTML ファイルとして出力する。

CloudShell から HTML をダウンロードしてブラウザで開くことで、
音声再生・トランスクリプト閲覧・学習ポイント確認を GUI で行える。
"""

import base64
import os
import glob


OUTPUT_DIR = "output"


def generate_results_html():
    """output/ ディレクトリの WAV ファイルを埋め込んだ results.html を生成"""

    wav_files = sorted(glob.glob(os.path.join(OUTPUT_DIR, "*.wav")))

    # WAV を base64 埋め込みで再生可能にする
    audio_sections = []
    for wav_path in wav_files:
        filename = os.path.basename(wav_path)
        size_kb = os.path.getsize(wav_path) / 1024
        with open(wav_path, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode("ascii")
        audio_sections.append({
            "filename": filename,
            "size_kb": size_kb,
            "data_uri": f"data:audio/wav;base64,{audio_b64}",
        })

    # トランスクリプトファイルの読み込み
    transcript_files = sorted(glob.glob(os.path.join(OUTPUT_DIR, "*.txt")))
    transcripts = []
    for txt_path in transcript_files:
        filename = os.path.basename(txt_path)
        with open(txt_path, "r", encoding="utf-8") as f:
            content = f.read()
        transcripts.append({"filename": filename, "content": content})

    # HTML 生成
    audio_html = ""
    for item in audio_sections:
        audio_html += f"""
        <div class="audio-card">
          <div class="audio-title">{item['filename']} ({item['size_kb']:.1f} KB)</div>
          <audio controls preload="metadata">
            <source src="{item['data_uri']}" type="audio/wav">
          </audio>
        </div>"""

    transcript_html = ""
    for item in transcripts:
        lines = item["content"].replace("<", "&lt;").replace(">", "&gt;")
        transcript_html += f"""
        <div class="transcript-card">
          <div class="transcript-title">{item['filename']}</div>
          <pre class="transcript-content">{lines}</pre>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AWS Deep Cuts: Nova 2 Sonic — Results</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f3f6f8; color: #1f2937; }}
    header {{ background: #232f3e; color: #fff; padding: 24px 18px; text-align: center; }}
    header h1 {{ font-size: 1.3rem; margin-bottom: 4px; }}
    header p {{ font-size: 0.85rem; color: #adb5bd; }}
    main {{ max-width: 860px; margin: 0 auto; padding: 20px; }}
    h2 {{ font-size: 1.1rem; margin: 24px 0 12px; padding-bottom: 6px; border-bottom: 2px solid #ff9900; }}
    .audio-card {{ background: #fff; border-left: 4px solid #ff9900; border-radius: 6px; padding: 14px; margin-bottom: 12px; box-shadow: 0 2px 8px rgba(15,23,42,.06); }}
    .audio-title {{ font-weight: 600; margin-bottom: 8px; font-size: 0.9rem; }}
    audio {{ width: 100%; }}
    .transcript-card {{ background: #fff; border-left: 4px solid #2563eb; border-radius: 6px; padding: 14px; margin-bottom: 12px; box-shadow: 0 2px 8px rgba(15,23,42,.06); }}
    .transcript-title {{ font-weight: 600; margin-bottom: 8px; font-size: 0.9rem; color: #2563eb; }}
    .transcript-content {{ font-size: 0.8rem; white-space: pre-wrap; line-height: 1.6; color: #374151; }}
    .learning-points {{ background: #fff; border-left: 4px solid #16a34a; border-radius: 6px; padding: 16px; margin-bottom: 12px; }}
    .learning-points h3 {{ color: #16a34a; font-size: 0.95rem; margin-bottom: 10px; }}
    .learning-points ul {{ padding-left: 20px; font-size: 0.85rem; line-height: 1.8; }}
    .empty {{ color: #6b7280; font-style: italic; font-size: 0.85rem; }}
  </style>
</head>
<body>
  <header>
    <h1>AWS Deep Cuts: Amazon Nova 2 Sonic</h1>
    <p>ハンズオン実行結果 — 音声再生とトランスクリプト確認</p>
  </header>
  <main>
    <h2>音声出力 (WAV)</h2>
    {audio_html if audio_html else '<p class="empty">WAV ファイルがありません。ハンズオンスクリプトを実行してください。</p>'}

    <h2>トランスクリプト</h2>
    {transcript_html if transcript_html else '<p class="empty">トランスクリプトファイルがありません。</p>'}

    <h2>学習ポイント</h2>
    <div class="learning-points">
      <h3>Nova 2 Sonic の主要特性</h3>
      <ul>
        <li><strong>音声入力ストリーム必須</strong>: speech-to-speech モデルのため、テキストだけ送っても動かない。audio input stream を開くことが前提。</li>
        <li><strong>サイレンスポンプ</strong>: 55 秒間音声入力がないとタイムアウト。無音フレームを定期送信して接続を維持する。</li>
        <li><strong>Cross-modal text input</strong>: 音声ストリームを維持したまま、テキスト注入で AI に応答させられる。</li>
        <li><strong>1 セッション = 1 voiceId</strong>: セッション途中で声を変えられない。matthew / tiffany はポリグロット (7 言語対応)。</li>
        <li><strong>endpointingSensitivity</strong>: LOW (初心者) / MEDIUM / HIGH (上級者) でターン検出タイミングを制御。</li>
        <li><strong>Tool use</strong>: 会話中にツールを呼び出し、構造化データを取得可能。非同期実行にも対応。</li>
        <li><strong>SPECULATIVE vs FINAL</strong>: テキスト出力は予測版 (SPECULATIVE) と確定版 (FINAL) がある。UI には FINAL のみ使う。</li>
        <li><strong>8 分接続制限</strong>: セッションは最大 8 分。本番では再接続 + 会話履歴引き継ぎが必要。</li>
      </ul>
    </div>
  </main>
</body>
</html>"""

    output_path = os.path.join(OUTPUT_DIR, "results.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return output_path


if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = generate_results_html()
    print(f"  📄 {path} を生成しました")
    print(f"     ダウンロードしてブラウザで開いてください。")
