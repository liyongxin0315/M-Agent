"""
AgentM Workflows - 工作流模板库
"""

from .workflow_engine import (
    WorkflowEngine,
    WorkflowStatus,
    StepStatus,
    StepResult,
    WorkflowResult,
    WorkflowStep,
    BaseWorkflow,
    DataSyncWorkflow,
    ScheduledReportWorkflow,
    APIIntegrationWorkflow,
    AIAssistantWorkflow,
    run_data_sync,
    run_scheduled_report,
    run_api_integration,
    run_ai_assistant
)

__all__ = [
    'WorkflowEngine',
    'WorkflowStatus',
    'StepStatus',
    'StepResult',
    'WorkflowResult',
    'WorkflowStep',
    'BaseWorkflow',
    'DataSyncWorkflow',
    'ScheduledReportWorkflow',
    'APIIntegrationWorkflow',
    'AIAssistantWorkflow',
    'run_data_sync',
    'run_scheduled_report',
    'run_api_integration',
    'run_ai_assistant'
]
