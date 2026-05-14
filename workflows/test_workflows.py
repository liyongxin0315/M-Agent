"""
工作流引擎单元测试
"""

import pytest
import asyncio
from workflow_engine import (
    WorkflowEngine,
    WorkflowStatus,
    StepStatus,
    DataSyncWorkflow,
    ScheduledReportWorkflow,
    APIIntegrationWorkflow,
    AIAssistantWorkflow,
    run_data_sync,
    run_scheduled_report
)


class TestWorkflowEngine:
    """测试工作流引擎"""
    
    def test_create_engine(self):
        """测试创建工作流引擎"""
        engine = WorkflowEngine("test_workflow")
        assert engine.name == "test_workflow"
        assert engine.status == WorkflowStatus.PENDING
    
    def test_add_step(self):
        """测试添加步骤"""
        engine = WorkflowEngine("test")
        
        def step_func(ctx):
            return "result"
        
        engine.add_step(
            name="test_step",
            func=step_func,
            description="测试步骤",
            retry_count=2
        )
        
        assert len(engine._steps) == 1
        assert engine._steps[0].name == "test_step"
    
    def test_execute_single_step(self):
        """测试执行单步骤工作流"""
        engine = WorkflowEngine("test")
        
        def step_func(ctx):
            ctx["result"] = "success"
            return "success"
        
        engine.add_step("step1", step_func)
        
        result = asyncio.run(engine.execute())
        
        assert result.status == WorkflowStatus.COMPLETED
        assert len(result.step_results) == 1
        assert result.step_results[0].status == StepStatus.COMPLETED
        assert engine.context["result"] == "success"
    
    def test_execute_multiple_steps(self):
        """测试执行多步骤工作流"""
        engine = WorkflowEngine("test")
        
        def step1(ctx):
            ctx["step1_done"] = True
            return True
        
        def step2(ctx):
            ctx["step2_done"] = True
            return True
        
        engine.add_step("step1", step1)
        engine.add_step("step2", step2)
        
        result = asyncio.run(engine.execute())
        
        assert result.status == WorkflowStatus.COMPLETED
        assert len(result.step_results) == 2
        assert engine.context["step1_done"] is True
        assert engine.context["step2_done"] is True
    
    def test_step_failure(self):
        """测试步骤失败"""
        engine = WorkflowEngine("test")
        
        def failing_step(ctx):
            raise ValueError("测试失败")
        
        engine.add_step("failing", failing_step)
        
        result = asyncio.run(engine.execute())
        
        assert result.status == WorkflowStatus.FAILED
        assert result.step_results[0].status == StepStatus.FAILED
        assert "测试失败" in result.step_results[0].error
    
    def test_skip_on_error(self):
        """测试跳过错误步骤"""
        engine = WorkflowEngine("test")
        
        def failing_step(ctx):
            raise ValueError("测试失败")
        
        def success_step(ctx):
            ctx["done"] = True
            return True
        
        engine.add_step("failing", failing_step, skip_on_error=True)
        engine.add_step("success", success_step)
        
        result = asyncio.run(engine.execute())
        
        assert result.status == WorkflowStatus.COMPLETED
        assert result.step_results[0].status == StepStatus.SKIPPED
        assert result.step_results[1].status == StepStatus.COMPLETED
        assert engine.context["done"] is True
    
    def test_retry_on_failure(self):
        """测试重试机制"""
        engine = WorkflowEngine("test")
        
        attempt_count = [0]
        
        def retry_step(ctx):
            attempt_count[0] += 1
            if attempt_count[0] < 3:
                raise ValueError("重试中")
            return "success"
        
        engine.add_step("retry", retry_step, retry_count=3)
        
        result = asyncio.run(engine.execute())
        
        assert result.status == WorkflowStatus.COMPLETED
        assert attempt_count[0] == 3
    
    def test_result_to_dict(self):
        """测试结果转字典"""
        engine = WorkflowEngine("test")
        engine.add_step("step1", lambda ctx: "result")
        
        result = asyncio.run(engine.execute())
        result_dict = result.to_dict()
        
        assert "workflow_name" in result_dict
        assert "status" in result_dict
        assert "step_results" in result_dict
        assert result_dict["workflow_name"] == "test"


class TestDataSyncWorkflow:
    """测试数据同步工作流"""
    
    def test_create_workflow(self):
        """测试创建工作流"""
        config = {
            "source": {"type": "mysql", "host": "localhost"},
            "target": {"type": "postgres", "host": "localhost"}
        }
        workflow = DataSyncWorkflow(config)
        
        assert workflow.engine.name == "DataSyncWorkflow"
        assert len(workflow.engine._steps) == 7
    
    def test_execute_workflow(self):
        """测试执行工作流"""
        config = {
            "source": {"type": "mysql"},
            "target": {"type": "postgres"}
        }
        workflow = DataSyncWorkflow(config)
        
        result = asyncio.run(workflow.execute())
        
        assert result.status == WorkflowStatus.COMPLETED
        assert len(result.step_results) == 7
    
    def test_missing_config(self):
        """测试缺少配置"""
        workflow = DataSyncWorkflow({})
        
        result = asyncio.run(workflow.execute())
        
        assert result.status == WorkflowStatus.FAILED
        assert "缺少必需配置" in result.error


class TestScheduledReportWorkflow:
    """测试定时报告工作流"""
    
    def test_create_workflow(self):
        """测试创建工作流"""
        config = {"output_path": "report.pdf"}
        workflow = ScheduledReportWorkflow(config)
        
        assert len(workflow.engine._steps) == 4
    
    def test_execute_workflow(self):
        """测试执行工作流"""
        config = {"output_path": "report.pdf"}
        workflow = ScheduledReportWorkflow(config)
        
        result = asyncio.run(workflow.execute())
        
        assert result.status == WorkflowStatus.COMPLETED


class TestAPIIntegrationWorkflow:
    """测试 API 集成工作流"""
    
    def test_create_workflow(self):
        """测试创建工作流"""
        config = {
            "auth": {"type": "bearer", "token": "test"},
            "api": {"url": "https://api.example.com"}
        }
        workflow = APIIntegrationWorkflow(config)
        
        assert len(workflow.engine._steps) == 4
    
    def test_execute_workflow(self):
        """测试执行工作流"""
        config = {"auth": {"type": "bearer"}}
        workflow = APIIntegrationWorkflow(config)
        
        result = asyncio.run(workflow.execute())
        
        assert result.status == WorkflowStatus.COMPLETED


class TestAIAssistantWorkflow:
    """测试 AI 辅助工作流"""
    
    def test_create_workflow(self):
        """测试创建工作流"""
        config = {"request": "帮我分析数据", "model": "gpt-4"}
        workflow = AIAssistantWorkflow(config)
        
        assert len(workflow.engine._steps) == 4
    
    def test_execute_workflow(self):
        """测试执行工作流"""
        config = {"request": "test query"}
        workflow = AIAssistantWorkflow(config)
        
        result = asyncio.run(workflow.execute())
        
        assert result.status == WorkflowStatus.COMPLETED
        assert "AI 生成的响应内容" in result.step_results[2].output


class TestConvenienceFunctions:
    """测试便捷函数"""
    
    def test_run_data_sync(self):
        """测试运行数据同步"""
        config = {
            "source": {"type": "mysql"},
            "target": {"type": "postgres"}
        }
        result = asyncio.run(run_data_sync(config))
        
        assert result.status == WorkflowStatus.COMPLETED
    
    def test_run_scheduled_report(self):
        """测试运行定时报告"""
        config = {"output_path": "report.pdf"}
        result = asyncio.run(run_scheduled_report(config))
        
        assert result.status == WorkflowStatus.COMPLETED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
