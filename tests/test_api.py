"""
M-Agent 集成测试

运行方法：
  cd D:\agentm
  pytest tests/test_api.py -v

前提：
  - Ollama 运行中（ollama serve）
  - 模型已下载（qwen3 + deepseek-coder）
  - 依赖已安装（pip install -e D:\agentm）
"""

import pytest
from fastapi.testclient import TestClient
from agentm.interfaces.api.main import app


client = TestClient(app)


class TestHealth:
    """健康检查"""

    def test_root(self):
        """网页界面可访问"""
        response = client.get("/")
        assert response.status_code == 200
        assert "M-Agent" in response.text

    def test_docs(self):
        """API 文档可访问"""
        response = client.get("/docs")
        assert response.status_code == 200


class TestExecution:
    """执行功能测试（需要 Ollama 运行）"""

    def test_simple_task(self):
        """简单代码生成任务"""
        response = client.post(
            "/execute",
            json={"prompt": "写一个求两个数最大值的函数"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["verdict"] in ["pass", "fail", "unknown"]

    def test_complex_task(self):
        """复杂代码生成任务（多候选 + Z3 严格验证）"""
        response = client.post(
            "/execute",
            json={"prompt": "写一个支持中文的冒泡排序，要求对重复字符正确处理"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("mode") == "complex"  # 复杂任务应该升级

    def test_invalid_input(self):
        """空输入处理"""
        response = client.post("/execute", json={"prompt": ""})
        assert response.status_code == 422  # FastAPI validation error
