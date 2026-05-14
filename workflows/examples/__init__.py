"""
示例工作流模块

包含 5 个完整的工作流示例：
1. 数据同步管道
2. 条件分支处理
3. 循环并行处理
4. 变量和模板系统
5. 嵌套工作流调用
"""

from .example_1_data_sync import run_data_sync_pipeline, DataSyncPipelineWorkflow
from .example_2_conditional import run_conditional_processing, ConditionalProcessingWorkflow
from .example_3_parallel import run_parallel_processing, ParallelProcessingWorkflow
from .example_4_variables import run_variable_template_workflow, VariableTemplateWorkflow
from .example_5_nested import run_nested_workflow_example, NestedWorkflowExample

__all__ = [
    "DataSyncPipelineWorkflow",
    "run_data_sync_pipeline",
    "ConditionalProcessingWorkflow",
    "run_conditional_processing",
    "ParallelProcessingWorkflow",
    "run_parallel_processing",
    "VariableTemplateWorkflow",
    "run_variable_template_workflow",
    "NestedWorkflowExample",
    "run_nested_workflow_example",
]
