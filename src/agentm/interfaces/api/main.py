"""
FastAPI 接口：M-Agent HTTP API

启动：
  cd D:\agentm
  python -m uvicorn agentm.interfaces.api.main:app --reload --port 8766

测试：
  curl -X POST http://127.0.0.1:8766/execute \
    -H "Content-Type: application/json" \
    -d "{\"prompt\": \"帮我写一个快排\"}"
"""

from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from loguru import logger
import uvicorn

from agentm.main_agent.coordinator import Coordinator, get_coordinator
from agentm.main_agent.state_manager import get_state_manager


# === Request/Response Models ===

class ExecuteRequest(BaseModel):
    prompt: str = Field(..., description="用户指令")
    session_id: str | None = Field(None, description="会话ID，不提供则自动生成")
    stream: bool = Field(True, description="是否流式输出")


class ExecuteResponse(BaseModel):
    session_id: str
    task_id: str
    status: str
    result: str | None = None
    error: str | None = None


class StateResponse(BaseModel):
    session_id: str
    total_tasks: int
    completed: int
    failed: int


class HealthResponse(BaseModel):
    status: str
    version: str


# === Lifespan ===

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("M-Agent API 启动")
    yield
    logger.info("M-Agent API 关闭")


# === FastAPI App ===

app = FastAPI(
    title="M-Agent API",
    description="本地思考 · 自进化 · 数字分身",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === Routes ===

@app.get("/health", response_model=HealthResponse)
async def health():
    """健康检查"""
    return HealthResponse(status="ok", version="0.1.0")


@app.get("/", response_class=HTMLResponse)
async def root():
    """网页界面"""
    return _HTML_UI


# ---------------------------------------------------------------------------
# Inline Web UI HTML
# ---------------------------------------------------------------------------

_HTML_UI = """
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
    <h3>History</h3>
    <div id="history"></div>
  </div>
  <div class="chat-area">
    <div class="output" id="output"></div>
    <div class="input-area">
      <input id="prompt" placeholder="Enter your task..." onkeydown="if(event.key==='Enter')send()">
      <button id="sendBtn" onclick="send()">Send</button>
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
      append('Error: ' + e.message, 'error');
    }
    sendBtn.disabled = false;
    prompt.focus();
  }
</script>
</body>
</html>
"""


@app.post("/execute", response_model=ExecuteResponse)
async def execute(req: ExecuteRequest):
    """
    同步执行（非流式）
    适用于程序调用
    """
    coord = get_coordinator()
    if req.session_id:
        coord.session_id = req.session_id

    chunks = []
    task_id = None

    async for chunk in coord.run(req.prompt):
        chunks.append(chunk)
        # 从第一个chunk提取task_id
        if task_id is None and "[Coordinator] 任务ID:" in chunk:
            task_id = chunk.split("任务ID:")[1].split("\n")[0].strip()

    result_text = "".join(chunks)

    return ExecuteResponse(
        session_id=coord.session_id,
        task_id=task_id or "unknown",
        status="completed",
        result=result_text,
    )


@app.post("/execute/stream")
async def execute_stream(req: ExecuteRequest):
    """
    流式执行
    适用于浏览器/终端实时看到思考过程

    curl 示例：
      curl -N -X POST http://127.0.0.1:8766/execute/stream \
        -H "Content-Type: application/json" \
        -d "{\"prompt\": \"帮我写一个快排\"}"
    """
    coord = get_coordinator()
    if req.session_id:
        coord.session_id = req.session_id

    async def event_generator():
        async for chunk in coord.run(req.prompt):
            # SSE 格式
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


@app.get("/state/{session_id}", response_model=StateResponse)
async def get_state(session_id: str):
    """查询会话状态"""
    sm = get_state_manager()
    state = sm.load_state()

    if state is None or state.session_id != session_id:
        raise HTTPException(status_code=404, detail="Session not found")

    return StateResponse(
        session_id=state.session_id,
        total_tasks=len(state.tasks),
        completed=len(state.completed_task_ids),
        failed=len(state.failed_task_ids),
    )


@app.delete("/state/{session_id}")
async def clear_state(session_id: str):
    """清除会话状态"""
    sm = get_state_manager()
    state = sm.load_state()

    if state is None or state.session_id != session_id:
        raise HTTPException(status_code=404, detail="Session not found")

    sm.clear()
    return {"status": "cleared", "session_id": session_id}


# === Entry Point ===

def main():
    uvicorn.run(
        "agentm.interfaces.api.main:app",
        host="0.0.0.0",
        port=8766,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
