"""
Workflow Examples Tests - 示例工作流测试
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock

from agentm.workflows.examples.data_analysis_workflow import (
    DataAnalysisWorkflow,
    run_data_analysis
)
from agentm.workflows.examples.research_workflow import (
    ResearchWorkflow,
    run_research
)
from agentm.workflows.workflow_engine import WorkflowStatus


class TestDataAnalysisWorkflow:
    """数据分析工作流测试"""
    
    @pytest.fixture
    def sample_data_path(self, tmp_path):
        """创建示例数据文件"""
        csv_path = tmp_path / "sample.csv"
        csv_path.write_text("name,value\nitem1,100\nitem2,200\nitem3,150")
        return str(csv_path)
    
    def test_workflow_initialization(self, sample_data_path):
        """测试工作流初始化"""
        config = {
            "data_path": sample_data_path,
            "analysis_type": "descriptive"
        }
        
        workflow = DataAnalysisWorkflow(config)
        assert workflow.engine is not None
        assert len(workflow.engine._steps) > 0
    
    @pytest.mark.asyncio
    async def test_load_data_step(self, sample_data_path):
        """测试数据加载步骤"""
        config = {
            "data_path": sample_data_path
        }
        
        workflow = DataAnalysisWorkflow(config)
        context = {}
        
        result = workflow._load_data(context)
        
        assert result["status"] == "success"
        assert context["data_loaded"] is True
    
    @pytest.mark.asyncio
    async def test_missing_data_path(self):
        """测试缺少数据路径"""
        config = {}
        workflow = DataAnalysisWorkflow(config)
        
        with pytest.raises(ValueError, match="缺少数据文件路径"):
            workflow._load_data({})
    
    @pytest.mark.asyncio
    async def test_nonexistent_file(self):
        """测试不存在的文件"""
        config = {
            "data_path": "/nonexistent/path/data.csv"
        }
        workflow = DataAnalysisWorkflow(config)
        
        with pytest.raises(FileNotFoundError):
            workflow._load_data({})


class TestResearchWorkflow:
    """研究工作流测试"""
    
    def test_workflow_initialization(self):
        """测试工作流初始化"""
        config = {
            "query": "test query",
            "max_sources": 5
        }
        
        workflow = ResearchWorkflow(config)
        assert workflow.engine is not None
    
    def test_missing_query(self):
        """测试缺少查询"""
        config = {}
        workflow = ResearchWorkflow(config)
        
        with pytest.raises(ValueError, match="缺少研究主题"):
            workflow._web_research({})


class TestConvenienceFunctions:
    """便捷函数测试"""
    
    @pytest.mark.asyncio
    async def test_run_data_analysis(self, tmp_path):
        """测试运行数据分析"""
        # 创建示例数据
        csv_path = tmp_path / "test.csv"
        csv_path.write_text("a,b\n1,2\n3,4")
        
        # Mock 分析节点
        with patch('agentm.workflows.examples.data_analysis_workflow.DataAnalysisNode') as mock_node:
            mock_instance = MagicMock()
            mock_instance.execute = asyncio.coroutine(lambda ctx: MagicMock(
                status=MagicMock(value="completed"),
                output={"result": "test"}
            ))
            mock_node.return_value = mock_instance
            
            result = await run_data_analysis(
                data_path=str(csv_path),
                analysis_type="descriptive"
            )
            
            assert result is not None
    
    @pytest.mark.asyncio
    async def test_run_research(self):
        """测试运行研究"""
        # Mock 研究节点
        with patch('agentm.workflows.examples.research_workflow.DeepResearchNode') as mock_node:
            mock_instance = MagicMock()
            mock_instance.execute = asyncio.coroutine(lambda ctx: MagicMock(
                status=MagicMock(value="completed"),
                output={"answer": "test answer"}
            ))
            mock_node.return_value = mock_instance
            
            result = await run_research(
                query="test query",
                max_sources=5
            )
            
            assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
