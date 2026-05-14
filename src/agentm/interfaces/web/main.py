"""
M-Agent Web UI

一个简洁的单页应用，通过 SSE 流式显示执行过程。

启动：
  cd D:\agentm
  python -m uvicorn agentm.interfaces.web.main:app --reload --port 8767

访问：
  http://localhost:8767
"""

from __future__ import annotations

import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from loguru import logger
import uvicorn

from ..main_agent.coordinator import Coordinator, get_coordinator


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------

app = FastAPI(title="M-Agent", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# HTML UI
# ---------------------------------------------------------------------------

HTML = """
<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>M-Agent</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, sans-serif; background: #0f0f0f; color: #e0e0e0; height: 100vh; display: flex; flex-direction: column; }
  header { background: #1a1a1a; border-bottom: 1px solid #333; padding: 12px 20px; display: flex; align-items: center; gap: 12px; }
  header h1 { font-size: 16px; font-weight: 600; color: #fff; }
  .status { width: 8px; height: 8px; border-radius: 50%; background: #444; }
  .status.online { background: #4ade80; }
  main { flex: 1; display: flex; overflow: hidden; }
  .sidebar { width: 240px; background: #1a1a1a; border-right: 1px solid #333; padding: 16px; overflow-y: auto; }
  .sidebar h3 { font-size: 11px; text-transform: uppercase; color: #666; letter-spacing: 0.05em; margin-bottom: 12px; }
  .history-item { padding: 8px 10px; border-radius: 6px; margin-bottom: 4px; cursor: pointer; font-size: 13px; }
  .history-item:hover { background: #2a2a2a; }
  .chat-area { flex: 1; display: flex; flex-direction: column; }
  .output { flex: 1; overflow-y: auto; padding: 20px; font-family: 'SF Mono', 'Consolas', monospace; font-size: 13px; line-height: 1.6; }
  .output-line { white-space: pre-wrap; word-break: break-all; }
  .output-line.system { color: #6b7280; }
  .output-line.user { color: #60a5fa; }
  .output-line.agent { color: #a78bfa; }
  .output-line.error { color: #f87171; }
  .output-line.success { color: #4ade80; }
  .input-area { padding: 16px 20px; background: #1a1a1a; border-top: 1px solid #333; display: flex; gap: 8px; }
  input { flex: 1; background: #2a2a2a; border: 1px solid #333; border-radius: 8px; padding: 10px 14px; color: #fff; font-size: 14px; outline: none; }
  input:focus { border-color: #6b7280; }
  button { background: #6366f1; color: #fff; border: none; border-radius: 8px; padding: 10px 20px; font-size: 14px; cursor: pointer; }
  button:hover { background: #4f46e5; }
  button:disabled { background: #333; color: #666; cursor: not-allowed; }
</style>
</head>
<body>
<header>
  <div class="status online"></div>
  <h1>M-Agent</h1>
</header>
<main>
  <div class="sidebar">
    <h3>历史记录</h3>
    <div id="history"></div>
  </div>
  <div class="chat-area">
    <div class="output" id="output"></div>
    <div class="input-area">
      <input id="prompt" placeholder="输入你的任务..." onkeydown="if(event.key==='Enter')send()">
      <button id="sendBtn" onclick="send()">发送</button>
    </div>
  </div>
</main>
<script>
  let sessionId = null;
  const output = document.getElementById('output');
  const prompt = document.getElementById('prompt');
  const sendBtn = document.getElementById('sendBtn');

  function append(text, cls='') {
    const div = document.createElement('div');
    div.className = 'output-line ' + cls;
    div.textContent = text;
    output.appendChild(div);
    output.scrollTop = output.scrollHeight;
  }

  async function send() {
    const text = prompt.value.trim();
    if (!text) return;
    prompt.value = '';
    sendBtn.disabled = true;
    append('> ' + text, 'user');
    append('', 'system');

    try {
      const res = await fetch('/execute/stream', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({prompt: text, session_id: sessionId}),
      });
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const {done, value} = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, {stream: true});
        const lines = buffer.split('\\n');
        buffer = lines.pop();
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') continue;
            append(data, 'agent');
          }
        }
      }
      append('', 'system');
    } catch (e) {
      append('错误: ' + e.message, 'error');
    }
    sendBtn.disabled = false;
    prompt.focus();
  }
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def root():
    return HTML


# ---------------------------------------------------------------------------
# Execute Endpoint (SSE Stream)
# ---------------------------------------------------------------------------

class ExecuteRequest(BaseModel):
    prompt: str
    session_id: str | None = None


@app.post("/execute/stream")
async def execute_stream(req: ExecuteRequest):
    coord = get_coordinator()
    if req.session_id:
        coord.session_id = req.session_id

    async def event_generator():
        async for chunk in coord.run(req.prompt):
            if isinstance(chunk, str):
                yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

def main():
    uvicorn.run(
        "agentm.interfaces.web.main:app",
        host="0.0.0.0",
        port=8767,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
