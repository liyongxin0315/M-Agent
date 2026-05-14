#!/usr/bin/env python3
"""
Autonomous Loop Module - 自主决策循环模块

Provides goal management, task planning, autonomous execution, and self-reflection.
目标管理、任务规划、自主执行和自我反思。

Author: AgentM Core Team
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from enum import Enum
import yaml

# 导入内部模块
try:
    from .event_bus import EventBus, EventType, Event, get_event_bus
    from .memory_store import MemoryStore, MemoryType, Memory, get_memory_store
    from .scheduler import TaskScheduler, Task, TaskPriority, TaskStatus, get_scheduler
except ImportError:
    from event_bus import EventBus, EventType, Event, get_event_bus
    from memory_store import MemoryStore, MemoryType, Memory, get_memory_store
    from scheduler import TaskScheduler, Task, TaskPriority, TaskStatus, get_scheduler


class GoalStatus(str, Enum):
    """目标状态枚举"""
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    ABANDONED = "abandoned"


class TaskType(str, Enum):
    """任务类型枚举"""
    ACTION = "action"      # 执行动作
    RESEARCH = "research"  # 研究/查询
    DECISION = "decision"  # 决策
    REFLECTION = "reflection"  # 反思


@dataclass
class Goal:
    """
    目标数据结构
    
    Attributes:
        goal_id: 目标 ID
        description: 目标描述
        status: 目标状态
        priority: 优先级
        created_at: 创建时间
        deadline: 截止时间
        subtasks: 子任务列表
        completed_tasks: 已完成任务
        metadata: 元数据
        reflection_notes: 反思笔记
    """
    goal_id: str = field(default_factory=lambda: f"goal_{datetime.utcnow().timestamp()}")
    description: str = ""
    status: GoalStatus = GoalStatus.ACTIVE
    priority: int = 1  # 1-5
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    deadline: Optional[str] = None
    subtasks: List[Dict[str, Any]] = field(default_factory=list)
    completed_tasks: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    reflection_notes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            **asdict(self),
            'status': self.status.value
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Goal":
        """从字典创建"""
        data = data.copy()
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = GoalStatus(data['status'])
        return cls(**data)
    
    def progress(self) -> float:
        """计算完成进度 (0.0-1.0)"""
        if not self.subtasks:
            return 0.0
        return len(self.completed_tasks) / len(self.subtasks)


@dataclass
class TaskPlan:
    """任务计划"""
    task_id: str
    task_type: TaskType
    description: str
    parameters: Dict[str, Any]
    estimated_duration: float  # 秒
    dependencies: List[str] = field(default_factory=list)
    priority: TaskPriority = TaskPriority.NORMAL


@dataclass
class ReflectionResult:
    """反思结果"""
    timestamp: str
    goal_id: str
    what_went_well: List[str]
    what_went_poorly: List[str]
    lessons_learned: List[str]
    action_items: List[str]
    confidence_change: float


class AutonomousAgent:
    """
    自主 Agent 类
    
    提供功能：
    - 目标管理和追踪
    - 任务规划和分解
    - 自主执行
    - 自我反思和学习
    
    Attributes:
        reflection_interval: 反思间隔（秒）
        max_goals: 最大目标数量
        task_timeout: 任务超时（秒）
    """
    
    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        memory_store: Optional[MemoryStore] = None,
        scheduler: Optional[TaskScheduler] = None,
        reflection_interval: int = 300,
        max_goals: int = 10,
        task_timeout: int = 3600
    ):
        """
        初始化自主 Agent
        
        Args:
            event_bus: 事件总线
            memory_store: 记忆存储
            scheduler: 任务调度器
            reflection_interval: 反思间隔（秒）
            max_goals: 最大目标数量
            task_timeout: 任务超时（秒）
        """
        self._event_bus = event_bus or get_event_bus()
        self._memory_store = memory_store or get_memory_store()
        self._scheduler = scheduler or get_scheduler()
        
        self._reflection_interval = reflection_interval
        self._max_goals = max_goals
        self._task_timeout = task_timeout
        
        # 目标管理
        self._active_goals: Dict[str, Goal] = {}
        self._goal_queue: List[Goal] = []
        
        # 任务执行器注册表
        self._task_executors: Dict[TaskType, Callable] = {}
        
        # 运行状态
        self._running = False
        self._reflection_task: Optional[asyncio.Task] = None
        
        # 日志
        self._logger = logging.getLogger(__name__)
        
        # 注册默认任务执行器
        self._register_default_executors()
    
    def _register_default_executors(self) -> None:
        """注册默认任务执行器"""
        
        async def execute_action(parameters: Dict[str, Any]) -> Any:
            """执行动作任务"""
            action = parameters.get('action', '')
            self._logger.info(f"Executing action: {action}")
            
            # 发布事件
            await self._event_bus.publish(
                EventType.TASK_STARTED.value,
                {"action": action},
                source="autonomous_agent"
            )
            
            # 实际动作执行逻辑（与 OpenClaw 集成）
            import subprocess
            import json
            
            try:
                # 解析动作
                action_data = json.loads(action) if isinstance(action, str) else action
                action_type = action_data.get('type', 'exec')
                action_params = action_data.get('params', {})
                
                if action_type == 'exec':
                    # 执行 shell 命令
                    cmd = action_params.get('command', '')
                    if cmd:
                        result = subprocess.run(
                            cmd,
                            shell=True,
                            capture_output=True,
                            text=True,
                            timeout=30
                        )
                        result_dict = {
                            "status": "completed",
                            "action": action,
                            "stdout": result.stdout,
                            "stderr": result.stderr,
                            "returncode": result.returncode
                        }
                    else:
                        result_dict = {"status": "failed", "error": "No command specified"}
                elif action_type == 'file_write':
                    # 写入文件
                    file_path = action_params.get('path', '')
                    content = action_params.get('content', '')
                    if file_path and content:
                        with open(file_path, 'w') as f:
                            f.write(content)
                        result_dict = {"status": "completed", "action": action, "path": file_path}
                    else:
                        result_dict = {"status": "failed", "error": "No path or content specified"}
                elif action_type == 'file_read':
                    # 读取文件
                    file_path = action_params.get('path', '')
                    if file_path:
                        with open(file_path, 'r') as f:
                            content = f.read()
                        result_dict = {"status": "completed", "action": action, "content": content}
                    else:
                        result_dict = {"status": "failed", "error": "No path specified"}
                else:
                    result_dict = {"status": "failed", "error": f"Unknown action type: {action_type}"}
                    
            except subprocess.TimeoutExpired:
                result_dict = {"status": "failed", "error": "Command timeout"}
            except Exception as e:
                result_dict = {"status": "failed", "error": str(e)}
            
            result = result_dict
            
            await self._event_bus.publish(
                EventType.TASK_COMPLETED.value,
                result,
                source="autonomous_agent"
            )
            
            return result
        
        async def execute_research(parameters: Dict[str, Any]) -> Any:
            """执行研究任务 - 查询记忆 + Tavily 网络搜索"""
            query = parameters.get('query', '')
            use_web = parameters.get('use_web', True)  # 默认启用网络搜索
            self._logger.info(f"Researching: {query} (web={use_web})")
            
            findings = []
            
            # 1. 查询本地记忆数据库
            memories = self._memory_store.search_memories(query, limit=5)
            findings.extend([f"[Local] {m.memory.content}" for m in memories])
            
            # 2. 使用 Tavily 网络搜索
            if use_web:
                try:
                    from tavily import TavilyClient
                    import os
                    
                    api_key = os.getenv('TAVILY_API_KEY', 'tvly-xxxxx')
                    client = TavilyClient(api_key=api_key)
                    
                    # Tavily 搜索
                    response = client.search(query, max_results=5)
                    web_findings = [
                        f"[Web] {r.get('title', 'No title')}: {r.get('content', 'No content')}"
                        for r in response.get("results", [])
                    ]
                    findings.extend(web_findings)
                    
                    # 3. 存储网络搜索结果到记忆
                    for result in response.get("results", []):
                        title = result.get("title", "Unknown")
                        content = result.get("content", "")
                        url = result.get("url", "")
                        
                        # 存储为语义记忆
                        self._memory_store.add_memory(
                            content=f"{title}: {content}",
                            memory_type="semantic",
                            metadata={
                                "source": "tavily_search",
                                "url": url,
                                "query": query
                            },
                            confidence=0.7
                        )
                    
                    self._logger.info(f"Stored {len(response.get('results', []))} web findings to memory")
                    
                except Exception as e:
                    error_msg = f"[Web Search Error] {str(e)}"
                    findings.append(error_msg)
                    self._logger.warning(error_msg)
            
            return {
                "status": "success",
                "query": query,
                "findings": findings,
                "memory_count": len(findings),
                "web_search": use_web
            }

        async def execute_decision(parameters: Dict[str, Any]) -> Any:
            """执行决策任务"""
            options = parameters.get('options', [])
            criteria = parameters.get('criteria', {})
            
            self._logger.info(f"Making decision among {len(options)} options")
            
            # 简单决策逻辑（生产环境需要更复杂的推理）
            selected = options[0] if options else None
            
            return {
                "selected": selected,
                "reasoning": "Default selection (placeholder)"
            }
        
        self._task_executors = {
            TaskType.ACTION: execute_action,
            TaskType.RESEARCH: execute_research,
            TaskType.DECISION: execute_decision,
        }
    
    def set_goal(
        self,
        description: str,
        priority: int = 3,
        deadline: Optional[str] = None,
        subtasks: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Goal:
        """
        设置目标
        
        Args:
            description: 目标描述
            priority: 优先级 (1-5)
            deadline: 截止时间 (ISO 格式)
            subtasks: 子任务列表
            metadata: 元数据
        
        Returns:
            创建的 Goal 对象
        
        Raises:
            ValueError: 当描述为空或超过最大目标数时
        """
        if not description or not description.strip():
            raise ValueError("Goal description cannot be empty")
        
        if len(self._active_goals) >= self._max_goals:
            raise ValueError(
                f"Maximum number of goals ({self._max_goals}) reached"
            )
        
        goal = Goal(
            description=description,
            priority=priority,
            deadline=deadline,
            subtasks=subtasks or [],
            metadata=metadata or {}
        )
        
        # 添加到活动目标和队列
        self._active_goals[goal.goal_id] = goal
        self._goal_queue.append(goal)
        self._goal_queue.sort(key=lambda g: -g.priority)
        
        self._logger.info(f"Goal set: {goal.goal_id} - {description[:50]}...")
        
        # 发布事件
        asyncio.create_task(self._event_bus.publish(
            EventType.GOAL_SET.value,
            goal.to_dict(),
            source="autonomous_agent"
        ))
        
        # 存储到记忆
        self._memory_store.add_memory(
            content=f"Goal: {description}",
            metadata={
                "type": "goal",
                "goal_id": goal.goal_id,
                "priority": str(priority)  # 转换为字符串
            },
            memory_type=MemoryType.EPISODIC,
            confidence=0.8
        )
        
        return goal
    
    def plan_tasks(self, goal: Goal) -> List[TaskPlan]:
        """
        为目标规划任务
        
        Args:
            goal: 目标对象
        
        Returns:
            任务计划列表
        """
        plans = []
        
        # 如果已有子任务，转换为任务计划
        for i, subtask in enumerate(goal.subtasks):
            plan = TaskPlan(
                task_id=f"{goal.goal_id}_task_{i}",
                task_type=TaskType(subtask.get('type', 'action')),
                description=subtask.get('description', ''),
                parameters=subtask.get('parameters', {}),
                estimated_duration=subtask.get('duration', 60.0),
                dependencies=subtask.get('dependencies', []),
                priority=TaskPriority(goal.priority)
            )
            plans.append(plan)
        
        # 如果没有预定义子任务，自动生成
        if not plans:
            plans = self._auto_generate_tasks(goal)
        
        self._logger.info(f"Generated {len(plans)} task plans for goal: {goal.goal_id}")
        return plans
    
    def _auto_generate_tasks(self, goal: Goal) -> List[TaskPlan]:
        """自动生成任务计划"""
        # 简单的启发式任务生成
        # 生产环境应该使用 LLM 进行智能规划
        
        plans = [
            TaskPlan(
                task_id=f"{goal.goal_id}_research",
                task_type=TaskType.RESEARCH,
                description=f"Research: {goal.description}",
                parameters={"query": goal.description},
                estimated_duration=120.0,
                priority=TaskPriority.HIGH
            ),
            TaskPlan(
                task_id=f"{goal.goal_id}_plan",
                task_type=TaskType.DECISION,
                description="Create action plan",
                parameters={
                    "options": ["Option A", "Option B"],
                    "criteria": {"efficiency": 0.5, "cost": 0.3}
                },
                estimated_duration=60.0,
                dependencies=[f"{goal.goal_id}_research"],
                priority=TaskPriority.NORMAL
            ),
            TaskPlan(
                task_id=f"{goal.goal_id}_execute",
                task_type=TaskType.ACTION,
                description="Execute plan",
                parameters={"action": goal.description},
                estimated_duration=300.0,
                dependencies=[f"{goal.goal_id}_plan"],
                priority=TaskPriority.NORMAL
            )
        ]
        
        return plans
    
    async def execute_task(self, task_plan: TaskPlan) -> Dict[str, Any]:
        """
        执行任务
        
        Args:
            task_plan: 任务计划
        
        Returns:
            执行结果
        
        Raises:
            ValueError: 当任务类型无执行器时
        """
        executor = self._task_executors.get(task_plan.task_type)
        if not executor:
            raise ValueError(f"No executor for task type: {task_plan.task_type}")
        
        self._logger.info(f"Executing task: {task_plan.task_id} ({task_plan.task_type.value})")
        
        try:
            # 设置超时
            result = await asyncio.wait_for(
                executor(task_plan.parameters),
                timeout=self._task_timeout
            )
            
            self._logger.info(f"Task completed: {task_plan.task_id}")
            return {
                "task_id": task_plan.task_id,
                "status": "success",
                "result": result
            }
            
        except asyncio.TimeoutError:
            self._logger.error(f"Task timeout: {task_plan.task_id}")
            return {
                "task_id": task_plan.task_id,
                "status": "timeout",
                "error": f"Task exceeded timeout of {self._task_timeout}s"
            }
            
        except Exception as e:
            self._logger.error(f"Task failed: {task_plan.task_id} - {e}")
            return {
                "task_id": task_plan.task_id,
                "status": "error",
                "error": str(e)
            }
    
    async def reflect(self, goal: Goal) -> ReflectionResult:
        """
        自我反思
        
        Args:
            goal: 要反思的目标
        
        Returns:
            反思结果
        """
        self._logger.info(f"Starting reflection for goal: {goal.goal_id}")
        
        # 发布反思开始事件
        await self._event_bus.publish(
            EventType.REFLECTION_STARTED.value,
            {"goal_id": goal.goal_id},
            source="autonomous_agent"
        )
        
        # 简单反思逻辑（生产环境应该用 LLM）
        progress = goal.progress()
        
        what_went_well = []
        what_went_poorly = []
        lessons_learned = []
        action_items = []
        
        if progress > 0.5:
            what_went_well.append("Made significant progress on goal")
        else:
            what_went_poorly.append("Limited progress on goal")
        
        if goal.completed_tasks:
            what_went_well.append(
                f"Completed {len(goal.completed_tasks)} subtasks"
            )
        
        # 从记忆中检索相关经验
        memories = self._memory_store.search_memories(
            goal.description,
            limit=3
        )
        for mem in memories:
            if mem.memory.confidence > 0.7:
                lessons_learned.append(
                    f"Previous experience: {mem.memory.content}"
                )
        
        # 生成行动项
        if progress < 1.0:
            action_items.append("Continue working on remaining subtasks")
        
        # 计算置信度变化
        confidence_change = 0.1 if progress > 0.5 else -0.1
        
        result = ReflectionResult(
            timestamp=datetime.utcnow().isoformat(),
            goal_id=goal.goal_id,
            what_went_well=what_went_well,
            what_went_poorly=what_went_poorly,
            lessons_learned=lessons_learned,
            action_items=action_items,
            confidence_change=confidence_change
        )
        
        # 存储反思结果
        goal.reflection_notes.append(json.dumps(result.__dict__))
        
        # 发布反思完成事件
        await self._event_bus.publish(
            EventType.REFLECTION_COMPLETED.value,
            result.__dict__,
            source="autonomous_agent"
        )
        
        self._logger.info(f"Reflection completed for goal: {goal.goal_id}")
        return result
    
    async def autonomous_loop(self) -> None:
        """
        自主决策循环（后台循环）
        
        持续执行：
        1. 选择最高优先级目标
        2. 规划任务
        3. 执行任务
        4. 定期反思
        """
        self._running = True
        self._logger.info("Autonomous agent loop started")
        
        # 启动反思任务
        self._reflection_task = asyncio.create_task(self._reflection_loop())
        
        try:
            while self._running:
                # 选择目标
                goal = self._select_next_goal()
                if not goal:
                    self._logger.debug("No active goals, waiting...")
                    await asyncio.sleep(5)
                    continue
                
                # 规划任务
                plans = self.plan_tasks(goal)
                if not plans:
                    self._logger.warning(f"No tasks planned for goal: {goal.goal_id}")
                    continue
                
                # 执行任务
                for plan in plans:
                    if not self._running:
                        break
                    
                    # 检查依赖
                    if not self._check_dependencies(plan, goal):
                        self._logger.debug(
                            f"Dependencies not met for task: {plan.task_id}"
                        )
                        continue
                    
                    # 执行
                    result = await self.execute_task(plan)
                    
                    # 更新目标状态
                    if result['status'] == 'success':
                        goal.completed_tasks.append(plan.task_id)
                        
                        # 检查目标是否完成
                        if goal.progress() >= 1.0:
                            goal.status = GoalStatus.COMPLETED
                            await self._event_bus.publish(
                                EventType.GOAL_COMPLETED.value,
                                goal.to_dict(),
                                source="autonomous_agent"
                            )
                            self._logger.info(f"Goal completed: {goal.goal_id}")
                            break
                
                # 短暂休息
                await asyncio.sleep(1)
                
        except asyncio.CancelledError:
            self._logger.info("Autonomous agent loop cancelled")
        except Exception as e:
            self._logger.error(f"Autonomous agent loop error: {e}")
        finally:
            self._running = False
            if self._reflection_task:
                self._reflection_task.cancel()
                try:
                    await self._reflection_task
                except asyncio.CancelledError:
                    pass
            self._logger.info("Autonomous agent loop stopped")
    
    async def _reflection_loop(self) -> None:
        """反思循环"""
        while self._running:
            try:
                await asyncio.sleep(self._reflection_interval)
                
                # 对所有活动目标进行反思
                for goal in list(self._active_goals.values()):
                    if goal.status == GoalStatus.ACTIVE:
                        await self.reflect(goal)
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Reflection loop error: {e}")
    
    def _select_next_goal(self) -> Optional[Goal]:
        """选择下一个要执行的目标"""
        # 按优先级排序
        active_goals = [
            g for g in self._active_goals.values()
            if g.status == GoalStatus.ACTIVE
        ]
        
        if not active_goals:
            return None
        
        # 返回最高优先级
        return max(active_goals, key=lambda g: g.priority)
    
    def _check_dependencies(
        self,
        plan: TaskPlan,
        goal: Goal
    ) -> bool:
        """检查任务依赖是否满足"""
        for dep_id in plan.dependencies:
            if dep_id not in goal.completed_tasks:
                return False
        return True
    
    def get_goal(self, goal_id: str) -> Optional[Goal]:
        """获取目标"""
        return self._active_goals.get(goal_id)
    
    def get_active_goals(self) -> List[Goal]:
        """获取所有活动目标"""
        return [
            g for g in self._active_goals.values()
            if g.status == GoalStatus.ACTIVE
        ]
    
    def pause_goal(self, goal_id: str) -> bool:
        """暂停目标"""
        goal = self._active_goals.get(goal_id)
        if goal and goal.status == GoalStatus.ACTIVE:
            goal.status = GoalStatus.PAUSED
            self._logger.info(f"Goal paused: {goal_id}")
            return True
        return False
    
    def resume_goal(self, goal_id: str) -> bool:
        """恢复目标"""
        goal = self._active_goals.get(goal_id)
        if goal and goal.status == GoalStatus.PAUSED:
            goal.status = GoalStatus.ACTIVE
            self._logger.info(f"Goal resumed: {goal_id}")
            return True
        return False
    
    def cancel_goal(self, goal_id: str) -> bool:
        """取消目标"""
        goal = self._active_goals.get(goal_id)
        if goal and goal.status in [GoalStatus.ACTIVE, GoalStatus.PAUSED]:
            goal.status = GoalStatus.ABANDONED
            del self._active_goals[goal_id]
            self._logger.info(f"Goal cancelled: {goal_id}")
            return True
        return False
    
    def stop(self) -> None:
        """停止自主 Agent"""
        self._running = False
        self._logger.info("Autonomous agent stop requested")
    
    @property
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._running


# 全局单例
_agent: Optional[AutonomousAgent] = None


def get_autonomous_agent() -> AutonomousAgent:
    """
    获取全局自主 Agent 单例
    
    Returns:
        AutonomousAgent 实例
    """
    global _agent
    if _agent is None:
        _agent = AutonomousAgent()
    return _agent


async def main():
    """自主 Agent 独立进程入口（用于测试）"""
    import yaml
    
    # 加载配置
    config_path = Path(__file__).parent.parent / "config.yaml"
    config = {}
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    
    autonomous_config = config.get('autonomous', {})
    
    # 创建组件
    event_bus = EventBus()
    memory_store = MemoryStore()
    scheduler = TaskScheduler()
    
    # 创建 Agent
    agent = AutonomousAgent(
        event_bus=event_bus,
        memory_store=memory_store,
        scheduler=scheduler,
        reflection_interval=autonomous_config.get('reflection_interval', 300),
        max_goals=autonomous_config.get('max_goals', 10),
        task_timeout=autonomous_config.get('task_timeout', 3600)
    )
    
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logging.info("Autonomous Agent initialized")
    
    # 设置测试目标
    test_goal = agent.set_goal(
        description="Test autonomous agent functionality",
        priority=3,
        subtasks=[
            {
                "type": "research",
                "description": "Research test requirements",
                "parameters": {"query": "agent testing"},
                "duration": 30.0
            },
            {
                "type": "action",
                "description": "Execute test",
                "parameters": {"action": "run_tests"},
                "duration": 60.0
            }
        ]
    )
    logging.info(f"Test goal set: {test_goal.goal_id}")
    
    # 启动事件总线
    event_bus_task = asyncio.create_task(event_bus.process_events())
    
    try:
        # 运行自主循环（测试 30 秒）
        agent._running = True
        for _ in range(30):
            goal = agent._select_next_goal()
            if goal:
                plans = agent.plan_tasks(goal)
                for plan in plans:
                    result = await agent.execute_task(plan)
                    logging.info(f"Task result: {result}")
                    if result['status'] == 'success':
                        goal.completed_tasks.append(plan.task_id)
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logging.info("Shutting down agent...")
    finally:
        agent.stop()
        event_bus.stop()
        event_bus_task.cancel()
    
    logging.info("Autonomous Agent test completed")


if __name__ == "__main__":
    asyncio.run(main())
