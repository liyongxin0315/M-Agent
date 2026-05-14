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
from fastapi.responses import StreamingResponse
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
