"""
状态管理器：管理主Agent的全局状态

功能：
  - 持久化任务状态到磁盘
  - 支持中断恢复（resume）
  - 记录完整执行轨迹
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from dataclasses import asdict
from loguru import logger

from .coordinator import CoordinatorState


class StateManager:
    """
    状态管理器

    状态文件存储在：
      D:\agentm\workflows\flows\agentm-main-agent\state\

    文件：
      coordinator_state.json  ── 主状态快照
      cursor.json             ── 当前游标（断点）
    """

    def __init__(self, state_dir: str | None = None):
        if state_dir is None:
            self.state_dir = Path(r"D:\agentm\workflows\flows\agentm-main-agent\state")
        else:
            self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.state_file = self.state_dir / "coordinator_state.json"
        self.cursor_file = self.state_dir / "cursor.json"

    def save_state(self, state: CoordinatorState) -> None:
        """保存协调器状态到磁盘"""
        try:
            data = {
                "session_id": state.session_id,
                "tasks": {
                    tid: asdict(t) for tid, t in state.tasks.items()
                },
                "completed_task_ids": state.completed_task_ids,
                "failed_task_ids": state.failed_task_ids,
                "context": state.context,
            }
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"状态已保存: {self.state_file}")
        except Exception as e:
            logger.error(f"状态保存失败: {e}")

    def load_state(self) -> CoordinatorState | None:
        """从磁盘加载状态，如果不存在返回None"""
        if not self.state_file.exists():
            return None

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            from .coordinator import Task, TaskStatus, CoordinatorState as CS

            tasks = {}
            for tid, tdata in data["tasks"].items():
                tdata["status"] = TaskStatus(tdata["status"])
                tasks[tid] = Task(**tdata)

            return CS(
                session_id=data["session_id"],
                tasks=tasks,
                completed_task_ids=data.get("completed_task_ids", []),
                failed_task_ids=data.get("failed_task_ids", []),
                context=data.get("context", {}),
            )
        except Exception as e:
            logger.error(f"状态加载失败: {e}")
            return None

    def save_cursor(self, step: str, metadata: dict | None = None) -> None:
        """保存断点游标"""
        cursor = {
            "step": step,
            "timestamp": __import__("time").time(),
        }
        if metadata:
            cursor["metadata"] = metadata

        with open(self.cursor_file, "w", encoding="utf-8") as f:
            json.dump(cursor, f, ensure_ascii=False, indent=2)

    def load_cursor(self) -> tuple[str | None, dict | None]:
        """加载断点游标"""
        if not self.cursor_file.exists():
            return None, None

        try:
            with open(self.cursor_file, "r", encoding="utf-8") as f:
                cursor = json.load(f)
            return cursor.get("step"), cursor.get("metadata")
        except Exception:
            return None, None

    def clear(self) -> None:
        """清除所有状态（用于新会话）"""
        for f in self.state_dir.glob("*.json"):
            f.unlink(missing_ok=True)
        logger.info("状态已清除")


# 全局单例
_state_manager: StateManager | None = None


def get_state_manager() -> StateManager:
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager
