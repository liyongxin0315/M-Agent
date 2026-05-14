"""
FastAPI 接口：M-Agent HTTP API

启动：
  cd D:/agentm
  python -m uvicorn agentm.interfaces.api.main:app --reload --port 8766

日志：
  所有请求记录到 D:/agentm/logs/api_requests.log
"""

from __future__ import annotations

import uuid
import time
import json
import asyncio
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager
from functools import wraps

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from loguru import logger
import uvicorn

from agentm.main_agent.coordinator import Coordinator, get_coordinator
from agentm.main_agent.state_manager import get_state_manager


# === 日志配置 ===

LOG_DIR = Path(r"D:\agentm\logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "api_requests.log"

# 移除默认 handler，添加文件 handler
logger.remove()
logger.add(
    LOG_FILE,
    rotation="10 MB",
    retention="7 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    encoding="utf-8",
)
# 同时输出到 stderr
logger.add(
    lambda msg: print(msg, end=""),
    level="INFO",
    format="<green>{time:HH:mm:ss}</green> | {level} | <blue>{message}</blue>",
)


# === Request Model ===

class ExecuteRequest(BaseModel):
    prompt: str = Field(..., description="用户指令")
    session_id: str | None = Field(None, description="会话ID")
    stream: bool = Field(True, description="是否流式")


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


# === 请求日志中间件 ===

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录所有请求到日志文件"""
    req_id = str(uuid.uuid4())[:8]
    start = time.time()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 跳过 favicon
    if request.url.path == "/favicon.ico":
        return await call_next(request)

    # 读取 body（如果是 POST）
    body = ""
    if request.method == "POST":
        body_bytes = await request.body()
        body = body_bytes.decode("utf-8", errors="replace")
        # 截断过长 body
        if len(body) > 200:
            body = body[:200] + "..."

    logger.info(
        f"[{req_id}] {request.method} {request.url.path} | "
        f"IP:{request.client.host if request.client else '?'} | "
        f"BODY:{body}"
    )

    response = await call_next(request)
    elapsed = (time.time() - start) * 1000

    logger.info(f"[{req_id}] → {response.status_code} ({elapsed:.0f}ms)")

    return response


# === Routes ===

@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", version="0.1.0")


@app.get("/", response_class=HTMLResponse)
async def root():
    return _HTML_UI


@app.post("/execute", response_model=ExecuteResponse)
async def execute(req: ExecuteRequest):
    coord = get_coordinator()
    if req.session_id:
        coord.session_id = req.session_id

    chunks = []
    task_id = None
    async for chunk in coord.run(req.prompt):
        chunks.append(chunk)
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
    coord = get_coordinator()
    if req.session_id:
        coord.session_id = req.session_id

    async def event_generator():
        try:
            async for chunk in coord.run(req.prompt):
                # SSE-safe: 换行转为\\n
                safe = chunk.replace("\\", "\\\\").replace("\n", "\\n")
                yield f"data: {safe}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: [ERROR]{str(e)}\n\n"

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
    sm = get_state_manager()
    sm.clear()
    return {"status": "cleared", "session_id": session_id}


# === Web UI (美化版) ===

_HTML_UI = """
<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>M-Agent</title>
<style>
  :root {
    --bg: #0f1117;
    --sidebar-bg: #161b22;
    --input-bg: #1c2128;
    --border: #30363d;
    --text: #e6edf3;
    --text-dim: #8b949e;
    --accent: #6366f1;
    --accent-hover: #4f46e5;
    --user-bubble: #3b4cc0;
    --agent-bubble: #21262d;
    --user-text: #ffffff;
    --agent-text: #e6edf3;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { height: 100%; }

  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: var(--bg);
    color: var(--text);
    height: 100%;
    display: flex;
    flex-direction: column;
  }

  /* Header */
  .header {
    background: var(--sidebar-bg);
    border-bottom: 1px solid var(--border);
    padding: 10px 20px;
    display: flex;
    align-items: center;
    gap: 10px;
    flex-shrink: 0;
  }
  .header h1 { font-size: 15px; font-weight: 600; color: #fff; }
  .dot { width: 8px; height: 8px; border-radius: 50%; background: #4ade80; flex-shrink: 0; }
  .header-actions { margin-left: auto; display: flex; gap: 8px; }
  .btn-clear {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text-dim);
    padding: 4px 12px;
    border-radius: 6px;
    font-size: 12px;
    cursor: pointer;
  }
  .btn-clear:hover { background: var(--border); color: var(--text); }

  /* Main layout */
  .main { flex: 1; display: flex; overflow: hidden; }

  /* Sidebar */
  .sidebar {
    width: 220px;
    background: var(--sidebar-bg);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
  }
  .sidebar-header {
    padding: 14px 16px 8px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-dim);
  }
  .history-list { flex: 1; overflow-y: auto; padding: 0 8px 8px; }
  .history-item {
    padding: 8px 10px;
    border-radius: 6px;
    font-size: 13px;
    color: var(--text-dim);
    cursor: pointer;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    margin-bottom: 2px;
  }
  .history-item:hover { background: #21262d; color: var(--text); }
  .history-empty { padding: 16px; font-size: 12px; color: var(--text-dim); text-align: center; }

  /* Chat area */
  .chat-area { flex: 1; display: flex; flex-direction: column; overflow: hidden; }

  /* Messages */
  .messages { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 16px; }

  .msg { display: flex; gap: 10px; max-width: 80%; }
  .msg.user { align-self: flex-end; flex-direction: row-reverse; }
  .msg.agent { align-self: flex-start; }

  .avatar {
    width: 28px; height: 28px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 12px; font-weight: 700; flex-shrink: 0;
  }
  .msg.user .avatar { background: var(--accent); color: #fff; }
  .msg.agent .avatar { background: var(--border); color: var(--text-dim); }

  .bubble {
    background: var(--agent-bubble);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 10px 14px;
    font-size: 14px;
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-word;
    color: var(--agent-text);
  }
  .msg.user .bubble { background: var(--user-bubble); border-color: var(--user-bubble); color: var(--user-text); }

  /* Loading */
  .loading {
    display: flex; gap: 10px; align-items: center;
    color: var(--text-dim); font-size: 13px;
    padding: 4px 0;
  }
  .spinner {
    width: 14px; height: 14px; border: 2px solid var(--border);
    border-top-color: var(--accent); border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* Input area */
  .input-area {
    padding: 12px 20px 16px;
    background: var(--sidebar-bg);
    border-top: 1px solid var(--border);
    display: flex;
    gap: 10px;
    flex-shrink: 0;
  }
  .input-area input {
    flex: 1;
    background: var(--input-bg);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 10px 14px;
    color: var(--text);
    font-size: 14px;
    outline: none;
    transition: border-color 0.15s;
  }
  .input-area input:focus { border-color: var(--accent); }
  .input-area input::placeholder { color: var(--text-dim); }
  .btn-send {
    background: var(--accent);
    color: #fff;
    border: none;
    border-radius: 10px;
    padding: 10px 20px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.15s;
    flex-shrink: 0;
  }
  .btn-send:hover { background: var(--accent-hover); }
  .btn-send:disabled { background: var(--border); cursor: not-allowed; }

  /* Welcome */
  .welcome { text-align: center; padding: 60px 20px; color: var(--text-dim); }
  .welcome h2 { font-size: 20px; font-weight: 600; color: var(--text); margin-bottom: 8px; }
  .welcome p { font-size: 14px; }
</style>
</head>
<body>

<div class="header">
  <div class="dot"></div>
  <h1>M-Agent</h1>
  <div class="header-actions">
    <button class="btn-clear" onclick="clearHistory()">New Chat</button>
  </div>
</div>

<div class="main">
  <div class="sidebar">
    <div class="sidebar-header">History</div>
    <div class="history-list" id="historyList">
      <div class="history-empty">No history yet</div>
    </div>
  </div>
  <div class="chat-area">
    <div class="messages" id="messages">
      <div class="welcome">
        <h2>你好，我是 M-Agent</h2>
        <p>我能帮你写代码、审查代码、修复bug，也可以聊聊</p>
      </div>
    </div>
    <div class="input-area">
      <input id="prompt" placeholder="输入你的任务..." onkeydown="if(event.key==='Enter' && !event.shiftKey)send()">
      <button class="btn-send" id="sendBtn" onclick="send()">发送</button>
    </div>
  </div>
</div>

<script>
  const SESSION_KEY = 'magent_session';
  const HISTORY_KEY = 'magent_history';
  let currentSession = localStorage.getItem(SESSION_KEY) || null;
  let loading = false;

  const messages = document.getElementById('messages');
  const promptEl = document.getElementById('prompt');
  const sendBtn = document.getElementById('sendBtn');

  // Load history
  function loadHistory() {
    const list = document.getElementById('historyList');
    const all = JSON.parse(localStorage.getItem(HISTORY_KEY) || '{}');
    const keys = Object.keys(all).reverse();
    if (keys.length === 0) {
      list.innerHTML = '<div class="history-empty">No history yet</div>';
      return;
    }
    list.innerHTML = keys.map(k => `
      <div class="history-item" onclick="loadSession('${k}')">${escapeHtml(all[k].title || k)}</div>
    `).join('');
  }

  function loadSession(id) {
    const all = JSON.parse(localStorage.getItem(HISTORY_KEY) || '{}');
    const sess = all[id];
    if (!sess) return;
    localStorage.setItem(SESSION_KEY, id);
    currentSession = id;
    renderMessages(sess.messages);
  }

  function renderMessages(msgs) {
    messages.innerHTML = '';
    if (msgs.length === 0) {
      messages.innerHTML = '<div class="welcome"><h2>你好，我是 M-Agent</h2><p>我能帮你写代码、审查代码、修复bug，也可以聊聊</p></div>';
      return;
    }
    msgs.forEach(m => addMessage(m.role, m.content, false));
  }

  function saveMessage(role, content) {
    const all = JSON.parse(localStorage.getItem(HISTORY_KEY) || '{}');
    if (!currentSession) {
      currentSession = Date.now().toString();
      localStorage.setItem(SESSION_KEY, currentSession);
    }
    if (!all[currentSession]) all[currentSession] = { title: '', messages: [] };
    all[currentSession].messages.push({ role, content });
    // 用第一条用户消息做标题
    if (role === 'user' && !all[currentSession].title) {
      all[currentSession].title = content.slice(0, 30);
    }
    localStorage.setItem(HISTORY_KEY, JSON.stringify(all));
    loadHistory();
  }

  function clearHistory() {
    localStorage.removeItem(SESSION_KEY);
    currentSession = null;
    messages.innerHTML = '<div class="welcome"><h2>你好，我是 M-Agent</h2><p>我能帮你写代码、审查代码、修复bug，也可以聊聊</p></div>';
    loadHistory();
  }

  function escapeHtml(t) {
    return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  function addMessage(role, content, save=true) {
    // Remove welcome if first real message
    const welcome = messages.querySelector('.welcome');
    if (welcome) messages.removeChild(welcome);

    const div = document.createElement('div');
    div.className = 'msg ' + role;
    div.innerHTML = `
      <div class="avatar">${role === 'user' ? 'U' : 'M'}</div>
      <div class="bubble">${escapeHtml(content)}</div>
    `;
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
    if (save) saveMessage(role, content);
  }

  function setLoading(on) {
    loading = on;
    sendBtn.disabled = on;
    sendBtn.textContent = on ? '思考中...' : '发送';
  }

  function showLoading() {
    const div = document.createElement('div');
    div.className = 'msg agent';
    div.id = 'loadingMsg';
    div.innerHTML = '<div class="avatar">M</div><div class="bubble"><div class="loading"><div class="spinner"></div>思考中...</div></div>';
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
  }

  function removeLoading() {
    const el = document.getElementById('loadingMsg');
    if (el) el.remove();
  }

  async function send() {
    const text = promptEl.value.trim();
    if (!text || loading) return;

    promptEl.value = '';
    addMessage('user', text);
    showLoading();
    setLoading(true);

    try {
      const body = { prompt: text };
      if (currentSession) body.session_id = currentSession;

      const res = await fetch('/execute/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      removeLoading();
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let reply = '';

      // 创建 agent 消息气泡
      const agentDiv = document.createElement('div');
      agentDiv.className = 'msg agent';
      agentDiv.innerHTML = '<div class="avatar">M</div><div class="bubble" id="agentBubble"></div>';
      messages.appendChild(agentDiv);
      const bubble = document.getElementById('agentBubble');

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const data = line.slice(6);
          if (data === '[DONE]') continue;
          // 解码：\\\\n → 真实换行，\\n → 换行
          const decoded = data.replace(/\\\\n/g, '\n').replace(/\\n/g, '\n').replace(/\\n/, '\n');
          bubble.textContent += decoded;
          reply += decoded;
          messages.scrollTop = messages.scrollHeight;
        }
      }
      if (reply) saveMessage('agent', reply);
    } catch (e) {
      removeLoading();
      const errDiv = document.createElement('div');
      errDiv.className = 'msg agent';
      errDiv.innerHTML = '<div class="avatar">M</div><div class="bubble" style="color:#f87171">Error: ' + escapeHtml(e.message) + '</div>';
      messages.appendChild(errDiv);
    }
    setLoading(false);
    loadHistory();
  }

  // Init
  loadHistory();
  promptEl.focus();
</script>
</body>
</html>
"""


# === Entry Point ===

def main():
    uvicorn.run(
        "agentm.interfaces.api.main:app",
        host="0.0.0.0",
        port=8766,
        reload=True,   # 开发时 True，改代码自动重启
        log_level="info",
    )


if __name__ == "__main__":
    main()
