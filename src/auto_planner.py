"""
AgentM Auto Planner - 自主任务规划器

实现复杂任务自动拆解、子任务依赖分析、执行顺序优化、动态调整计划

特性:
- LLM 驱动的任务拆解
- 依赖图 (DAG) 分析
- 关键路径优化
- 动态计划调整
- 执行监控和重规划
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


# ============ 枚举和数据类 ============

class PlanStatus(Enum):
    """计划状态"""
    DRAFT = "draft"
    ACTIVE = "active"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    ADJUSTED = "adjusted"


class TaskType(Enum):
    """任务类型"""
    RESEARCH = "research"        # 调研类
    CODING = "coding"            # 编码类
    TESTING = "testing"          # 测试类
    DOCUMENTATION = "documentation"  # 文档类
    REVIEW = "review"            # 审核类
    DEPLOYMENT = "deployment"    # 部署类
    UNKNOWN = "unknown"


@dataclass
class PlanTask:
    """计划中的任务"""
    id: str
    name: str
    description: str
    task_type: TaskType = TaskType.UNKNOWN
    estimated_duration: float = 1.0  # 小时
    priority: int = 1  # 1-5, 5 最高
    dependencies: List[str] = field(default_factory=list)
    status: str = "pending"
    result: Any = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "task_type": self.task_type.value,
            "estimated_duration": self.estimated_duration,
            "priority": self.priority,
            "dependencies": self.dependencies,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "PlanTask":
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            task_type=TaskType(data.get("task_type", "unknown")),
            estimated_duration=data.get("estimated_duration", 1.0),
            priority=data.get("priority", 1),
            dependencies=data.get("dependencies", []),
            status=data.get("status", "pending"),
            metadata=data.get("metadata", {})
        )


@dataclass
class ExecutionPlan:
    """执行计划"""
    id: str
    goal: str
    tasks: Dict[str, PlanTask] = field(default_factory=dict)
    status: PlanStatus = PlanStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_order: List[str] = field(default_factory=list)
    critical_path: List[str] = field(default_factory=list)
    total_estimated_duration: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "goal": self.goal,
            "status": self.status.value,
            "task_count": len(self.tasks),
            "execution_order": self.execution_order,
            "critical_path": self.critical_path,
            "total_estimated_duration": self.total_estimated_duration,
            "created_at": self.created_at.isoformat(),
            "tasks": {tid: t.to_dict() for tid, t in self.tasks.items()}
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ExecutionPlan":
        plan = cls(
            id=data["id"],
            goal=data["goal"],
            status=PlanStatus(data.get("status", "draft")),
            metadata=data.get("metadata", {})
        )
        plan.tasks = {
            tid: PlanTask.from_dict(tdata)
            for tid, tdata in data.get("tasks", {}).items()
        }
        plan.execution_order = data.get("execution_order", [])
        plan.critical_path = data.get("critical_path", [])
        plan.total_estimated_duration = data.get("total_estimated_duration", 0.0)
        return plan


@dataclass
class DependencyGraph:
    """依赖图 (DAG)"""
    nodes: Set[str] = field(default_factory=set)
    edges: Dict[str, List[str]] = field(default_factory=dict)  # task -> [dependencies]
    reverse_edges: Dict[str, List[str]] = field(default_factory=dict)  # task -> [dependents]
    
    def add_node(self, task_id: str) -> None:
        """添加节点"""
        self.nodes.add(task_id)
        if task_id not in self.edges:
            self.edges[task_id] = []
        if task_id not in self.reverse_edges:
            self.reverse_edges[task_id] = []
    
    def add_edge(self, from_task: str, to_task: str) -> None:
        """添加边 (from_task 依赖 to_task)"""
        self.add_node(from_task)
        self.add_node(to_task)
        
        if to_task not in self.edges[from_task]:
            self.edges[from_task].append(to_task)
        
        if from_task not in self.reverse_edges[to_task]:
            self.reverse_edges[to_task].append(from_task)
    
    def get_dependencies(self, task_id: str) -> List[str]:
        """获取任务的所有依赖（递归）"""
        deps = set()
        stack = list(self.edges.get(task_id, []))
        
        while stack:
            dep = stack.pop()
            if dep not in deps:
                deps.add(dep)
                stack.extend(self.edges.get(dep, []))
        
        return list(deps)
    
    def get_dependents(self, task_id: str) -> List[str]:
        """获取依赖此任务的所有任务（递归）"""
        dependents = set()
        stack = list(self.reverse_edges.get(task_id, []))
        
        while stack:
            dep = stack.pop()
            if dep not in dependents:
                dependents.add(dep)
                stack.extend(self.reverse_edges.get(dep, []))
        
        return list(dependents)
    
    def has_cycle(self) -> bool:
        """检测是否有环"""
        visited = set()
        rec_stack = set()
        
        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in self.edges.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            
            rec_stack.remove(node)
            return False
        
        for node in self.nodes:
            if node not in visited:
                if dfs(node):
                    return True
        
        return False
    
    def topological_sort(self) -> List[str]:
        """拓扑排序（执行顺序）"""
        if self.has_cycle():
            raise ValueError("依赖图存在环，无法排序")
        
        in_degree = {node: len(self.edges.get(node, [])) for node in self.nodes}
        queue = [node for node in self.nodes if in_degree[node] == 0]
        result = []
        
        while queue:
            # 按优先级排序（可选）
            queue.sort()
            node = queue.pop(0)
            result.append(node)
            
            for dependent in self.reverse_edges.get(node, []):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
        
        return result
    
    def find_critical_path(self, durations: Dict[str, float]) -> List[str]:
        """寻找关键路径"""
        if not self.nodes:
            return []
        
        # 计算最早开始时间
        earliest_start = {}
        earliest_finish = {}
        
        topo_order = self.topological_sort()
        
        for task_id in topo_order:
            deps = self.edges.get(task_id, [])
            if not deps:
                earliest_start[task_id] = 0
            else:
                earliest_start[task_id] = max(
                    earliest_finish.get(dep, 0) for dep in deps
                )
            
            duration = durations.get(task_id, 1.0)
            earliest_finish[task_id] = earliest_start[task_id] + duration
        
        # 找到结束时间最晚的任务
        if not earliest_finish:
            return []
        
        end_task = max(earliest_finish, key=earliest_finish.get)
        
        # 回溯关键路径
        critical_path = [end_task]
        current = end_task
        
        while True:
            deps = self.edges.get(current, [])
            if not deps:
                break
            
            # 找到决定当前任务最早开始时间的依赖
            current_dep = max(
                deps,
                key=lambda d: earliest_finish.get(d, 0)
            )
            critical_path.append(current_dep)
            current = current_dep
        
        critical_path.reverse()
        return critical_path


# ============ LLM 任务拆解器 ============

class LLMTaskDecomposer:
    """
    LLM 驱动的任务拆解器
    
    使用 LLM 将复杂目标拆解为可执行的子任务
    """
    
    def __init__(self, llm_callback: Optional[Callable] = None):
        self.llm_callback = llm_callback
        self._default_decomposition_prompt = """
请将以下目标拆解为具体的可执行任务。

目标：{goal}

要求:
1. 每个任务应该是具体、可衡量、可执行的
2. 识别任务之间的依赖关系
3. 为每个任务估算所需时间（小时）
4. 为每个任务分配优先级 (1-5)
5. 识别任务类型 (research/coding/testing/documentation/review/deployment)

请以 JSON 格式返回，格式如下:
{{
    "tasks": [
        {{
            "id": "task-1",
            "name": "任务名称",
            "description": "任务描述",
            "task_type": "research",
            "estimated_duration": 2.0,
            "priority": 3,
            "dependencies": []
        }}
    ]
}}

目标：{goal}

请拆解任务：
"""
    
    async def decompose(
        self,
        goal: str,
        max_tasks: int = 20,
        context: Optional[str] = None
    ) -> List[PlanTask]:
        """
        拆解目标为任务列表
        
        Args:
            goal: 目标描述
            max_tasks: 最大任务数
            context: 额外上下文
        
        Returns:
            任务列表
        """
        if self.llm_callback:
            return await self._llm_decompose(goal, max_tasks, context)
        else:
            return self._rule_based_decompose(goal, max_tasks, context)
    
    async def _llm_decompose(
        self,
        goal: str,
        max_tasks: int,
        context: Optional[str]
    ) -> List[PlanTask]:
        """LLM 拆解"""
        prompt = self._default_decomposition_prompt.format(goal=goal)
        
        if context:
            prompt = f"上下文：{context}\n\n{prompt}"
        
        try:
            response = await self.llm_callback(prompt)
            tasks_data = self._parse_llm_response(response)
            
            # 限制任务数量
            tasks_data = tasks_data[:max_tasks]
            
            tasks = []
            for i, data in enumerate(tasks_data):
                task = PlanTask(
                    id=data.get("id", f"task-{i+1}"),
                    name=data.get("name", f"任务{i+1}"),
                    description=data.get("description", ""),
                    task_type=TaskType(data.get("task_type", "unknown")),
                    estimated_duration=data.get("estimated_duration", 1.0),
                    priority=data.get("priority", 1),
                    dependencies=data.get("dependencies", [])
                )
                tasks.append(task)
            
            return tasks
        
        except Exception as e:
            logger.error(f"LLM 拆解失败：{e}")
            return self._rule_based_decompose(goal, max_tasks, context)
    
    def _parse_llm_response(self, response: str) -> List[Dict]:
        """解析 LLM 响应"""
        # 尝试提取 JSON
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                data = json.loads(json_match.group())
                return data.get("tasks", [])
            except json.JSONDecodeError:
                pass
        
        # 回退到行解析
        tasks = []
        for line in response.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                tasks.append({
                    "id": f"task-{len(tasks)+1}",
                    "name": line[:50],
                    "description": line,
                    "task_type": "unknown",
                    "estimated_duration": 1.0,
                    "priority": 1,
                    "dependencies": []
                })
        
        return tasks
    
    def _rule_based_decompose(
        self,
        goal: str,
        max_tasks: int,
        context: Optional[str]
    ) -> List[PlanTask]:
        """基于规则的拆解（回退方案）"""
        # 通用软件开发流程模板
        template_tasks = [
            ("需求分析", "理解和分析需求", TaskType.RESEARCH, 2.0, 5),
            ("技术方案设计", "设计技术实现方案", TaskType.RESEARCH, 3.0, 4),
            ("环境准备", "准备开发环境和依赖", TaskType.DEPLOYMENT, 1.0, 3),
            ("核心功能开发", "实现核心功能", TaskType.CODING, 8.0, 5),
            ("辅助功能开发", "实现辅助功能", TaskType.CODING, 4.0, 3),
            ("单元测试", "编写和执行单元测试", TaskType.TESTING, 3.0, 4),
            ("集成测试", "执行集成测试", TaskType.TESTING, 2.0, 3),
            ("文档编写", "编写技术文档", TaskType.DOCUMENTATION, 2.0, 2),
            ("代码审查", "执行代码审查", TaskType.REVIEW, 1.0, 3),
            ("部署上线", "部署到生产环境", TaskType.DEPLOYMENT, 2.0, 4),
        ]
        
        tasks = []
        for i, (name, desc, ttype, duration, priority) in enumerate(template_tasks):
            if len(tasks) >= max_tasks:
                break
            
            task = PlanTask(
                id=f"task-{i+1}",
                name=f"{name}",
                description=f"{desc}: {goal[:100]}",
                task_type=ttype,
                estimated_duration=duration,
                priority=priority,
                dependencies=[f"task-{i}"] if i > 0 else []
            )
            tasks.append(task)
        
        return tasks


# ============ 自主规划器 ============

class AutoPlanner:
    """
    自主任务规划器
    
    功能:
    - 目标拆解
    - 依赖分析
    - 执行顺序优化
    - 动态计划调整
    - 执行监控
    """
    
    def __init__(
        self,
        llm_callback: Optional[Callable] = None,
        config: Optional[Dict] = None
    ):
        self.config = config or {}
        self.decomposer = LLMTaskDecomposer(llm_callback)
        self._plans: Dict[str, ExecutionPlan] = {}
        self._current_plan_id: Optional[str] = None
        
        logger.info("自主规划器初始化完成")
    
    async def create_plan(
        self,
        goal: str,
        context: Optional[str] = None,
        max_tasks: int = 20
    ) -> ExecutionPlan:
        """
        创建执行计划
        
        Args:
            goal: 目标
            context: 上下文信息
            max_tasks: 最大任务数
        
        Returns:
            执行计划
        """
        import uuid
        plan_id = str(uuid.uuid4())[:8]
        
        logger.info(f"创建计划：{goal[:50]}...")
        
        # 拆解任务
        tasks = await self.decomposer.decompose(goal, max_tasks, context)
        
        # 创建计划
        plan = ExecutionPlan(
            id=plan_id,
            goal=goal,
            tasks={task.id: task for task in tasks}
        )
        
        # 构建依赖图并分析
        self._analyze_dependencies(plan)
        
        # 优化执行顺序
        self._optimize_execution_order(plan)
        
        # 计算关键路径
        self._calculate_critical_path(plan)
        
        # 计算总时长
        plan.total_estimated_duration = sum(
            t.estimated_duration for t in plan.tasks.values()
        )
        
        self._plans[plan_id] = plan
        self._current_plan_id = plan_id
        
        logger.info(f"计划创建完成：{plan_id}, 任务数：{len(tasks)}")
        return plan
    
    def _analyze_dependencies(self, plan: ExecutionPlan) -> None:
        """分析任务依赖"""
        graph = DependencyGraph()
        
        for task_id, task in plan.tasks.items():
            graph.add_node(task_id)
            for dep in task.dependencies:
                graph.add_edge(task_id, dep)
        
        # 检测环
        if graph.has_cycle():
            logger.warning("依赖图存在环，尝试自动修复")
            self._fix_dependency_cycles(plan, graph)
        
        # 更新依赖
        for task_id, task in plan.tasks.items():
            task.dependencies = graph.edges.get(task_id, [])
    
    def _fix_dependency_cycles(
        self,
        plan: ExecutionPlan,
        graph: DependencyGraph
    ) -> None:
        """修复依赖环"""
        # 简单策略：移除后添加的边
        for task_id in list(plan.tasks.keys()):
            deps = graph.edges.get(task_id, [])
            for dep in deps:
                # 检查移除这条边是否打破环
                graph.edges[task_id].remove(dep)
                if graph.reverse_edges.get(dep):
                    graph.reverse_edges[dep].remove(task_id)
                
                if not graph.has_cycle():
                    logger.info(f"移除依赖边：{task_id} -> {dep}")
                    break
                else:
                    # 恢复
                    graph.edges[task_id].append(dep)
                    graph.reverse_edges[dep].append(task_id)
    
    def _optimize_execution_order(self, plan: ExecutionPlan) -> None:
        """优化执行顺序"""
        graph = DependencyGraph()
        
        for task_id, task in plan.tasks.items():
            graph.add_node(task_id)
            for dep in task.dependencies:
                graph.add_edge(task_id, dep)
        
        try:
            # 拓扑排序得到执行顺序
            order = graph.topological_sort()
            
            # 在同层级内按优先级排序
            plan.execution_order = order
            
            logger.info(f"执行顺序优化完成：{len(order)} 个任务")
        except ValueError as e:
            logger.error(f"执行顺序优化失败：{e}")
            plan.execution_order = list(plan.tasks.keys())
    
    def _calculate_critical_path(self, plan: ExecutionPlan) -> None:
        """计算关键路径"""
        graph = DependencyGraph()
        durations = {}
        
        for task_id, task in plan.tasks.items():
            graph.add_node(task_id)
            durations[task_id] = task.estimated_duration
            for dep in task.dependencies:
                graph.add_edge(task_id, dep)
        
        try:
            critical_path = graph.find_critical_path(durations)
            plan.critical_path = critical_path
            
            logger.info(f"关键路径：{' -> '.join(critical_path)}")
        except Exception as e:
            logger.warning(f"关键路径计算失败：{e}")
            plan.critical_path = []
    
    def get_plan(self, plan_id: Optional[str] = None) -> Optional[ExecutionPlan]:
        """获取计划"""
        if plan_id:
            return self._plans.get(plan_id)
        return self._plans.get(self._current_plan_id) if self._current_plan_id else None
    
    def list_plans(self) -> List[ExecutionPlan]:
        """列出所有计划"""
        return list(self._plans.values())
    
    async def update_task_status(
        self,
        task_id: str,
        status: str,
        result: Any = None,
        error: Optional[str] = None,
        plan_id: Optional[str] = None
    ) -> bool:
        """更新任务状态"""
        plan = self.get_plan(plan_id)
        if not plan or task_id not in plan.tasks:
            return False
        
        task = plan.tasks[task_id]
        task.status = status
        
        if result is not None:
            task.result = result
        
        if error:
            task.error = error
        
        if status == "in_progress" and not task.started_at:
            task.started_at = datetime.now()
        
        if status in ["completed", "failed"] and not task.completed_at:
            task.completed_at = datetime.now()
        
        # 检查是否需要调整计划
        if status == "failed":
            await self._handle_task_failure(plan, task)
        
        # 检查计划是否完成
        self._check_plan_completion(plan)
        
        logger.info(f"任务状态更新：{task_id} -> {status}")
        return True
    
    async def _handle_task_failure(
        self,
        plan: ExecutionPlan,
        failed_task: PlanTask
    ) -> None:
        """处理任务失败"""
        logger.warning(f"任务失败：{failed_task.id}, 尝试调整计划")
        
        # 找到受影响的后续任务
        graph = DependencyGraph()
        for task_id, task in plan.tasks.items():
            graph.add_node(task_id)
            for dep in task.dependencies:
                graph.add_edge(task_id, dep)
        
        affected_tasks = graph.get_dependents(failed_task.id)
        
        if affected_tasks:
            logger.info(f"受影响的任务：{affected_tasks}")
            
            # 可以选择重新规划或跳过
            # 这里简单地将依赖此任务的任务标记为阻塞
            for task_id in affected_tasks:
                task = plan.tasks.get(task_id)
                if task and task.status == "pending":
                    task.metadata["blocked_by"] = failed_task.id
    
    def _check_plan_completion(self, plan: ExecutionPlan) -> None:
        """检查计划是否完成"""
        if plan.status == PlanStatus.COMPLETED:
            return
        
        all_completed = all(
            t.status == "completed"
            for t in plan.tasks.values()
        )
        
        if all_completed:
            plan.status = PlanStatus.COMPLETED
            plan.completed_at = datetime.now()
            logger.info(f"计划完成：{plan.id}")
    
    async def adjust_plan(
        self,
        plan_id: Optional[str] = None,
        new_goal: Optional[str] = None,
        add_tasks: Optional[List[Dict]] = None,
        remove_tasks: Optional[List[str]] = None
    ) -> ExecutionPlan:
        """
        调整计划
        
        Args:
            plan_id: 计划 ID
            new_goal: 新目标
            add_tasks: 要添加的任务
            remove_tasks: 要移除的任务
        
        Returns:
            调整后的计划
        """
        plan = self.get_plan(plan_id)
        if not plan:
            raise ValueError("计划不存在")
        
        logger.info(f"调整计划：{plan.id}")
        
        # 更新目标
        if new_goal:
            plan.goal = new_goal
        
        # 添加任务
        if add_tasks:
            for task_data in add_tasks:
                task = PlanTask(
                    id=task_data.get("id", f"new-task-{len(plan.tasks)+1}"),
                    name=task_data.get("name", "新任务"),
                    description=task_data.get("description", ""),
                    task_type=TaskType(task_data.get("task_type", "unknown")),
                    estimated_duration=task_data.get("estimated_duration", 1.0),
                    priority=task_data.get("priority", 1),
                    dependencies=task_data.get("dependencies", [])
                )
                plan.tasks[task.id] = task
        
        # 移除任务
        if remove_tasks:
            for task_id in remove_tasks:
                if task_id in plan.tasks:
                    del plan.tasks[task_id]
        
        # 重新分析
        self._analyze_dependencies(plan)
        self._optimize_execution_order(plan)
        self._calculate_critical_path(plan)
        
        plan.status = PlanStatus.ADJUSTED
        
        logger.info(f"计划调整完成：{plan.id}")
        return plan
    
    def get_next_tasks(self, plan_id: Optional[str] = None) -> List[PlanTask]:
        """获取可执行的下一个任务"""
        plan = self.get_plan(plan_id)
        if not plan:
            return []
        
        completed = {
            tid for tid, task in plan.tasks.items()
            if task.status == "completed"
        }
        
        next_tasks = []
        for task_id in plan.execution_order:
            task = plan.tasks.get(task_id)
            if not task or task.status != "pending":
                continue
            
            # 检查依赖是否满足
            if all(dep in completed for dep in task.dependencies):
                next_tasks.append(task)
        
        # 按优先级排序
        next_tasks.sort(key=lambda t: -t.priority)
        
        return next_tasks
    
    def get_progress(self, plan_id: Optional[str] = None) -> Dict[str, Any]:
        """获取进度"""
        plan = self.get_plan(plan_id)
        if not plan:
            return {}
        
        total = len(plan.tasks)
        completed = sum(1 for t in plan.tasks.values() if t.status == "completed")
        in_progress = sum(1 for t in plan.tasks.values() if t.status == "in_progress")
        failed = sum(1 for t in plan.tasks.values() if t.status == "failed")
        
        return {
            "plan_id": plan.id,
            "goal": plan.goal,
            "status": plan.status.value,
            "total_tasks": total,
            "completed": completed,
            "in_progress": in_progress,
            "failed": failed,
            "pending": total - completed - in_progress - failed,
            "progress_percent": round(completed / total * 100, 2) if total > 0 else 0,
            "estimated_duration_hours": plan.total_estimated_duration,
            "critical_path": plan.critical_path
        }
    
    def to_workflow_step(self) -> Callable:
        """转换为工作流步骤"""
        async def planner_step(context: Dict) -> Dict[str, Any]:
            goal = context.get("goal", "")
            
            if not goal:
                raise ValueError("目标不能为空")
            
            plan = await self.create_plan(goal)
            
            context["plan_id"] = plan.id
            context["plan"] = plan.to_dict()
            context["next_tasks"] = [
                t.to_dict() for t in self.get_next_tasks(plan.id)
            ]
            
            return context
        
        return planner_step


# ============ 主程序 ============

async def main():
    """测试自主规划器"""
    logging.basicConfig(level=logging.INFO)
    
    # 创建规划器（不使用 LLM）
    planner = AutoPlanner()
    
    # 创建计划
    goal = "开发一个智能任务管理系统，支持多 Agent 协作和自动规划"
    
    print(f"\n目标：{goal}\n")
    
    plan = await planner.create_plan(goal, max_tasks=10)
    
    print(f"计划 ID: {plan.id}")
    print(f"任务数：{len(plan.tasks)}")
    print(f"预计总时长：{plan.total_estimated_duration} 小时")
    print(f"执行顺序：{plan.execution_order}")
    print(f"关键路径：{plan.critical_path}")
    
    print("\n任务列表:")
    for task_id in plan.execution_order:
        task = plan.tasks[task_id]
        deps = f" (依赖：{task.dependencies})" if task.dependencies else ""
        print(f"  [{task.priority}] {task.name} - {task.task_type.value}{deps}")
    
    # 获取进度
    print("\n进度:")
    progress = planner.get_progress()
    for key, value in progress.items():
        print(f"  {key}: {value}")
    
    # 获取可执行任务
    print("\n可执行任务:")
    next_tasks = planner.get_next_tasks()
    for task in next_tasks:
        print(f"  - {task.name} (优先级：{task.priority})")
    
    print("\n自主规划器测试完成")


if __name__ == "__main__":
    asyncio.run(main())
