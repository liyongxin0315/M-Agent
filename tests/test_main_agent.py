"""
主Agent 协调层集成测试

运行：
  cd D:\agentm
  python -m pytest tests/test_main_agent.py -v
"""

import pytest
import asyncio
from agentm.main_agent.coordinator import (
    Coordinator,
    IntentParser,
    IntentType,
    Task,
    TaskStatus,
)
from agentm.main_agent.state_manager import StateManager


class TestIntentParser:
    """意图解析器测试"""

    def setup_method(self):
        self.parser = IntentParser()

    def test_code_generate(self):
        intent, desc = self.parser.parse("帮我写一个快排")
        assert intent == IntentType.CODE_GENERATE
        assert "快排" in desc

    def test_code_fix(self):
        intent, desc = self.parser.parse("这段代码报错了，修复一下")
        assert intent == IntentType.CODE_FIX

    def test_code_refactor(self):
        intent, desc = self.parser.parse("帮我重构这段代码")
        assert intent == IntentType.CODE_REFACTOR

    def test_default_is_code_generate(self):
        intent, desc = self.parser.parse("给我写个函数")
        assert intent == IntentType.CODE_GENERATE


class TestCoordinator:
    """协调器测试"""

    @pytest.mark.asyncio
    async def test_coordinator_initialization(self):
        coord = Coordinator()
        assert coord.session_id is not None
        assert len(coord.session_id) == 8
        assert isinstance(coord.state.tasks, dict)

    @pytest.mark.asyncio
    async def test_coordinator_run(self):
        """测试完整执行流程（mock Ollama）"""
        # 注意：这个测试依赖 Ollama 实际运行
        # 如果没有 Ollama，会失败，这是预期行为
        coord = Coordinator()

        chunks = []
        async for chunk in coord.run("写一个整数相加的函数"):
            chunks.append(chunk)

        result = "".join(chunks)
        # 验证输出包含关键信息
        assert "[Coordinator]" in result
        assert "任务ID:" in result


class TestStateManager:
    """状态管理器测试"""

    def setup_method(self):
        import tempfile
        import shutil
        self.tmpdir = tempfile.mkdtemp()
        self.sm = StateManager(state_dir=self.tmpdir)

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_save_and_load_state(self):
        from agentm.main_agent.coordinator import CoordinatorState
        import time

        state = CoordinatorState(session_id="test123")
        task = Task(task_id="t1", description="test task")
        state.tasks["t1"] = task
        state.completed_task_ids.append("t1")

        self.sm.save_state(state)
        loaded = self.sm.load_state()

        assert loaded is not None
        assert loaded.session_id == "test123"
        assert len(loaded.tasks) == 1
        assert "t1" in loaded.completed_task_ids

    def test_save_and_load_cursor(self):
        self.sm.save_cursor("step3", {"file": "test.py"})
        step, meta = self.sm.load_cursor()

        assert step == "step3"
        assert meta["file"] == "test.py"

    def test_clear_state(self):
        from agentm.main_agent.coordinator import CoordinatorState

        state = CoordinatorState(session_id="test456")
        self.sm.save_state(state)
        self.sm.save_cursor("step1")

        self.sm.clear()

        assert not self.sm.state_file.exists()
        assert not self.sm.cursor_file.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
