"""
AgentM Multi-Agent Coordinator - 多 Agent 协调器

实现 Agent 间通信协议、任务分发和协调、角色定义

特性:
- 基于消息的 Agent 通信
- 任务队列和分发
- 角色系统（规划者/执行者/审核者）
- 协作工作流模板
- 冲突检测和解决
"""

import asyncio
import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


# ============ 核心枚举 ============

class AgentRole(Enum):
    """Agent 角色"""
    PLANNER = "planner"      # 规划者：任务拆解和规划
    EXECUTOR = "executor"    # 执行者：执行具体任务
    REVIEWER = "reviewer"    # 审核者：质量审核
    COORDINATOR = "coordinator"  # 协调者：总体协调
    SPECIALIST = "specialist"    # 专家：特定领域专家


class AgentStatus(Enum):
    """Agent 状态"""
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"
    ERROR = "error"


class MessageType(Enum):
    """消息类型"""
    TASK_ASSIGN = "task_assign"      # 任务分配
    TASK_COMPLETE = "task_complete"  # 任务完成
    TASK_FAILED = "task_failed"      # 任务失败
    REQUEST_HELP = "request_help"    # 请求帮助
    PROVIDE_HELP = "provide_help"    # 提供帮助
    STATUS_UPDATE = "status_update"  # 状态更新
    BROADCAST = "broadcast"          # 广播消息
    SYNC_REQUEST = "sync_request"    # 同步请求
    SYNC_RESPONSE = "sync_response"  # 同步响应


class TaskPriority(Enum):
    """任务优先级"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ============ 数据类 ============

@dataclass
class AgentMessage:
    """Agent 间消息"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    sender_id: str = ""
    receiver_id: Optional[str] = None  # None 表示广播
    message_type: MessageType = MessageType.BROADCAST
    content: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    priority: TaskPriority = TaskPriority.NORMAL
    requires_ack: bool = False
    acknowledged: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "message_type": self.message_type.value,
            "content": str(self.content)[:200] if self.content else None,
            "timestamp": self.timestamp.isoformat(),
            "priority": self.priority.value,
            "requires_ack": self.requires_ack,
            "acknowledged": self.acknowledged
        }


@dataclass
class Task:
    """任务定义"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    description: str = ""
    parent_task_id: Optional[str] = None
    sub_tasks: List[str] = field(default_factory=list)
    assigned_to: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Any = None
    error: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "assigned_to": self.assigned_to,
            "status": self.status.value,
            "priority": self.priority.value,
            "dependencies": self.dependencies,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": str(self.result)[:200] if self.result else None,
            "error": self.error
        }


@dataclass
class Agent:
    """Agent 定义"""
    id: str
    name: str
    role: AgentRole
    status: AgentStatus = AgentStatus.IDLE
    capabilities: List[str] = field(default_factory=list)
    current_task: Optional[str] = None
    completed_tasks: int = 0
    failed_tasks: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_heartbeat: datetime = field(default_factory=datetime.now)
    
    # 任务执行回调
    task_handler: Optional[Callable] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role.value,
            "status": self.status.value,
            "capabilities": self.capabilities,
            "current_task": self.current_task,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "last_heartbeat": self.last_heartbeat.isoformat()
        }
    
    def is_available(self) -> bool:
        """检查是否可用"""
        return self.status == AgentStatus.IDLE and self.current_task is None


@dataclass
class CollaborationSession:
    """协作会话"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    goal: str = ""
    status: str = "active"  # active, completed, failed, cancelled
    agents: List[str] = field(default_factory=list)
    tasks: List[str] = field(default_factory=list)
    messages: List[AgentMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    result: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "goal": self.goal,
            "status": self.status,
            "agent_count": len(self.agents),
            "task_count": len(self.tasks),
            "message_count": len(self.messages),
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


# ============ 消息队列 ============

class MessageQueue:
    """
    消息队列
    
    支持优先级排序和订阅模式
    """
    
    def __init__(self, max_size: int = 10000):
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=max_size)
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}
        self._running = False
        self._processor_task: Optional[asyncio.Task] = None
    
    async def put(self, message: AgentMessage) -> None:
        """放入消息"""
        priority = -message.priority.value  # 负数使高优先级先出队
        await self._queue.put((priority, message.timestamp.timestamp(), message))
        
        # 通知订阅者
        await self._notify_subscribers(message)
        
        logger.debug(f"消息入队：{message.id}, 类型：{message.message_type.value}")
    
    async def get(self, timeout: Optional[float] = None) -> Optional[AgentMessage]:
        """获取消息"""
        try:
            if timeout:
                _, _, message = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=timeout
                )
            else:
                _, _, message = await self._queue.get()
            
            return message
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            logger.error(f"获取消息失败：{e}")
            return None
    
    def subscribe(self, agent_id: str) -> asyncio.Queue:
        """订阅消息"""
        if agent_id not in self._subscribers:
            self._subscribers[agent_id] = []
        
        queue = asyncio.Queue(maxsize=1000)
        self._subscribers[agent_id].append(queue)
        
        logger.info(f"Agent {agent_id} 订阅消息队列")
        return queue
    
    def unsubscribe(self, agent_id: str) -> None:
        """取消订阅"""
        if agent_id in self._subscribers:
            del self._subscribers[agent_id]
            logger.info(f"Agent {agent_id} 取消订阅")
    
    async def _notify_subscribers(self, message: AgentMessage) -> None:
        """通知订阅者"""
        # 广播给所有订阅者
        for agent_id, queues in self._subscribers.items():
            if message.receiver_id is None or message.receiver_id == agent_id:
                for queue in queues:
                    try:
                        queue.put_nowait(message)
                    except asyncio.QueueFull:
                        logger.warning(f"Agent {agent_id} 消息队列已满")
    
    async def start_processor(self, handler: Callable) -> None:
        """启动消息处理器"""
        self._running = True
        
        async def process():
            while self._running:
                message = await self.get(timeout=1.0)
                if message:
                    try:
                        await handler(message)
                    except Exception as e:
                        logger.error(f"处理消息失败：{e}")
        
        self._processor_task = asyncio.create_task(process())
        logger.info("消息处理器已启动")
    
    async def stop_processor(self) -> None:
        """停止消息处理器"""
        self._running = False
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass


# ============ 多 Agent 协调器 ============

class MultiAgentCoordinator:
    """
    多 Agent 协调器
    
    功能:
    - Agent 注册和管理
    - 任务分发和调度
    - 消息路由
    - 协作会话管理
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self._agents: Dict[str, Agent] = {}
        self._tasks: Dict[str, Task] = {}
        self._sessions: Dict[str, CollaborationSession] = {}
        self._message_queue = MessageQueue()
        self._running = False
        
        # 任务完成回调
        self._task_callbacks: Dict[str, Callable] = {}
        
        logger.info("多 Agent 协调器初始化完成")
    
    # ========== Agent 管理 ==========
    
    def register_agent(
        self,
        agent_id: str,
        name: str,
        role: AgentRole,
        capabilities: Optional[List[str]] = None,
        task_handler: Optional[Callable] = None
    ) -> Agent:
        """注册 Agent"""
        if agent_id in self._agents:
            raise ValueError(f"Agent {agent_id} 已存在")
        
        agent = Agent(
            id=agent_id,
            name=name,
            role=role,
            capabilities=capabilities or [],
            task_handler=task_handler
        )
        
        self._agents[agent_id] = agent
        
        # 订阅消息
        self._message_queue.subscribe(agent_id)
        
        logger.info(f"注册 Agent: {agent_id} ({role.value})")
        return agent
    
    def unregister_agent(self, agent_id: str) -> bool:
        """注销 Agent"""
        if agent_id not in self._agents:
            return False
        
        self._message_queue.unsubscribe(agent_id)
        del self._agents[agent_id]
        
        logger.info(f"注销 Agent: {agent_id}")
        return True
    
    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """获取 Agent"""
        return self._agents.get(agent_id)
    
    def list_agents(
        self,
        role: Optional[AgentRole] = None,
        status: Optional[AgentStatus] = None
    ) -> List[Agent]:
        """列出 Agent"""
        agents = list(self._agents.values())
        
        if role:
            agents = [a for a in agents if a.role == role]
        if status:
            agents = [a for a in agents if a.status == status]
        
        return agents
    
    def find_available_agent(
        self,
        role: Optional[AgentRole] = None,
        required_capabilities: Optional[List[str]] = None
    ) -> Optional[Agent]:
        """查找可用的 Agent"""
        available = [
            a for a in self._agents.values()
            if a.is_available()
        ]
        
        if role:
            available = [a for a in available if a.role == role]
        
        if required_capabilities:
            available = [
                a for a in available
                if all(cap in a.capabilities for cap in required_capabilities)
            ]
        
        # 返回最空闲的（完成任务最多的）
        if available:
            return max(available, key=lambda a: a.completed_tasks)
        
        return None
    
    # ========== 任务管理 ==========
    
    def create_task(
        self,
        name: str,
        description: str = "",
        priority: TaskPriority = TaskPriority.NORMAL,
        dependencies: Optional[List[str]] = None,
        metadata: Optional[Dict] = None,
        parent_task_id: Optional[str] = None
    ) -> Task:
        """创建任务"""
        task = Task(
            name=name,
            description=description,
            priority=priority,
            dependencies=dependencies or [],
            metadata=metadata or {},
            parent_task_id=parent_task_id
        )
        
        self._tasks[task.id] = task
        
        # 更新父任务的子任务列表
        if parent_task_id and parent_task_id in self._tasks:
            self._tasks[parent_task_id].sub_tasks.append(task.id)
        
        logger.info(f"创建任务：{task.id} - {name}")
        return task
    
    def assign_task(
        self,
        task_id: str,
        agent_id: str,
        auto_start: bool = True
    ) -> bool:
        """分配任务"""
        if task_id not in self._tasks:
            logger.error(f"任务不存在：{task_id}")
            return False
        
        if agent_id not in self._agents:
            logger.error(f"Agent 不存在：{agent_id}")
            return False
        
        task = self._tasks[task_id]
        agent = self._agents[agent_id]
        
        # 检查依赖
        if not self._check_dependencies(task):
            logger.warning(f"任务 {task_id} 依赖未满足")
            return False
        
        # 检查 Agent 是否可用
        if not agent.is_available():
            logger.warning(f"Agent {agent_id} 不可用")
            return False
        
        # 分配
        task.assigned_to = agent_id
        task.status = TaskStatus.ASSIGNED
        agent.current_task = task_id
        
        # 发送任务分配消息
        message = AgentMessage(
            sender_id="coordinator",
            receiver_id=agent_id,
            message_type=MessageType.TASK_ASSIGN,
            content=task.to_dict(),
            requires_ack=True
        )
        
        # 在有事件循环时异步发送，否则同步添加
        try:
            loop = asyncio.get_running_loop()
            asyncio.create_task(self._message_queue.put(message))
        except RuntimeError:
            # 没有运行中的事件循环，稍后处理
            logger.debug(f"消息队列将在事件循环中处理：{message.id}")
        
        logger.info(f"任务 {task_id} 分配给 Agent {agent_id}")
        
        if auto_start:
            try:
                loop = asyncio.get_running_loop()
                asyncio.create_task(self.start_task(task_id))
            except RuntimeError:
                logger.warning(f"任务 {task_id} 需要事件循环来自动启动")
        
        return True
    
    async def start_task(self, task_id: str) -> bool:
        """启动任务"""
        if task_id not in self._tasks:
            return False
        
        task = self._tasks[task_id]
        agent = self._agents.get(task.assigned_to)
        
        if not agent:
            logger.error(f"任务 {task_id} 未分配 Agent")
            return False
        
        # 更新状态
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.now()
        agent.status = AgentStatus.BUSY
        
        logger.info(f"启动任务：{task_id}")
        
        # 执行任务
        if agent.task_handler:
            try:
                result = await agent.task_handler(task)
                await self.complete_task(task_id, result)
            except Exception as e:
                await self.fail_task(task_id, str(e))
        
        return True
    
    async def complete_task(
        self,
        task_id: str,
        result: Any = None
    ) -> bool:
        """完成任务"""
        if task_id not in self._tasks:
            return False
        
        task = self._tasks[task_id]
        agent = self._agents.get(task.assigned_to)
        
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now()
        task.result = result
        
        if agent:
            agent.status = AgentStatus.IDLE
            agent.current_task = None
            agent.completed_tasks += 1
        
        # 发送完成消息
        message = AgentMessage(
            sender_id=task.assigned_to or "unknown",
            message_type=MessageType.TASK_COMPLETE,
            content={"task_id": task_id, "result": result}
        )
        await self._message_queue.put(message)
        
        # 触发回调
        if task_id in self._task_callbacks:
            await self._task_callbacks[task_id](task)
        
        logger.info(f"任务完成：{task_id}")
        
        # 检查并启动依赖任务
        await self._check_and_start_dependent_tasks(task_id)
        
        return True
    
    async def fail_task(
        self,
        task_id: str,
        error: str,
        retry: bool = True
    ) -> bool:
        """失败任务"""
        if task_id not in self._tasks:
            return False
        
        task = self._tasks[task_id]
        agent = self._agents.get(task.assigned_to)
        
        task.error = error
        
        if retry and task.retry_count < task.max_retries:
            task.retry_count += 1
            task.status = TaskStatus.PENDING
            logger.warning(f"任务 {task_id} 失败，重试 {task.retry_count}/{task.max_retries}")
            
            if agent:
                agent.status = AgentStatus.IDLE
                agent.current_task = None
            
            # 延迟重试
            await asyncio.sleep(1.0 * task.retry_count)
            asyncio.create_task(self.start_task(task_id))
        else:
            task.status = TaskStatus.FAILED
            
            if agent:
                agent.status = AgentStatus.IDLE
                agent.current_task = None
                agent.failed_tasks += 1
            
            # 发送失败消息
            message = AgentMessage(
                sender_id=task.assigned_to or "unknown",
                message_type=MessageType.TASK_FAILED,
                content={"task_id": task_id, "error": error}
            )
            await self._message_queue.put(message)
            
            logger.error(f"任务失败：{task_id}, 错误：{error}")
        
        return True
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        if task_id not in self._tasks:
            return False
        
        task = self._tasks[task_id]
        task.status = TaskStatus.CANCELLED
        
        agent = self._agents.get(task.assigned_to)
        if agent:
            agent.status = AgentStatus.IDLE
            agent.current_task = None
        
        logger.info(f"任务取消：{task_id}")
        return True
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self._tasks.get(task_id)
    
    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        assigned_to: Optional[str] = None
    ) -> List[Task]:
        """列出任务"""
        tasks = list(self._tasks.values())
        
        if status:
            tasks = [t for t in tasks if t.status == status]
        if assigned_to:
            tasks = [t for t in tasks if t.assigned_to == assigned_to]
        
        return tasks
    
    def _check_dependencies(self, task: Task) -> bool:
        """检查依赖是否满足"""
        for dep_id in task.dependencies:
            dep_task = self._tasks.get(dep_id)
            if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                return False
        return True
    
    async def _check_and_start_dependent_tasks(self, completed_task_id: str) -> None:
        """检查并启动依赖此任务的其他任务"""
        for task in self._tasks.values():
            if (
                task.status == TaskStatus.PENDING and
                completed_task_id in task.dependencies
            ):
                # 检查所有依赖
                if self._check_dependencies(task):
                    # 分配并启动
                    agent = self.find_available_agent()
                    if agent:
                        self.assign_task(task.id, agent.id, auto_start=True)
    
    # ========== 会话管理 ==========
    
    def create_session(
        self,
        name: str,
        goal: str,
        agent_ids: Optional[List[str]] = None
    ) -> CollaborationSession:
        """创建协作会话"""
        session = CollaborationSession(
            name=name,
            goal=goal,
            agents=agent_ids or []
        )
        
        self._sessions[session.id] = session
        
        logger.info(f"创建协作会话：{session.id} - {name}")
        return session
    
    def add_agent_to_session(
        self,
        session_id: str,
        agent_id: str
    ) -> bool:
        """添加 Agent 到会话"""
        if session_id not in self._sessions:
            return False
        
        session = self._sessions[session_id]
        if agent_id not in session.agents:
            session.agents.append(agent_id)
        
        return True
    
    def add_task_to_session(
        self,
        session_id: str,
        task_id: str
    ) -> bool:
        """添加任务到会话"""
        if session_id not in self._sessions:
            return False
        
        session = self._sessions[session_id]
        if task_id not in session.tasks:
            session.tasks.append(task_id)
        
        return True
    
    def get_session(self, session_id: str) -> Optional[CollaborationSession]:
        """获取会话"""
        return self._sessions.get(session_id)
    
    def complete_session(
        self,
        session_id: str,
        result: Any = None
    ) -> bool:
        """完成会话"""
        if session_id not in self._sessions:
            return False
        
        session = self._sessions[session_id]
        session.status = "completed"
        session.completed_at = datetime.now()
        session.result = result
        
        logger.info(f"协作会话完成：{session_id}")
        return True
    
    # ========== 消息发送 ==========
    
    async def send_message(
        self,
        sender_id: str,
        receiver_id: Optional[str],
        message_type: MessageType,
        content: Any,
        requires_ack: bool = False
    ) -> AgentMessage:
        """发送消息"""
        message = AgentMessage(
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type=message_type,
            content=content,
            requires_ack=requires_ack
        )
        
        await self._message_queue.put(message)
        return message
    
    async def broadcast(
        self,
        sender_id: str,
        message_type: MessageType,
        content: Any
    ) -> AgentMessage:
        """广播消息"""
        return await self.send_message(
            sender_id,
            None,
            message_type,
            content
        )
    
    # ========== 统计和监控 ==========
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "agents": {
                "total": len(self._agents),
                "by_role": {
                    role.value: len([
                        a for a in self._agents.values()
                        if a.role == role
                    ])
                    for role in AgentRole
                },
                "by_status": {
                    status.value: len([
                        a for a in self._agents.values()
                        if a.status == status
                    ])
                    for status in AgentStatus
                }
            },
            "tasks": {
                "total": len(self._tasks),
                "by_status": {
                    status.value: len([
                        t for t in self._tasks.values()
                        if t.status == status
                    ])
                    for status in TaskStatus
                }
            },
            "sessions": {
                "total": len(self._sessions),
                "active": len([
                    s for s in self._sessions.values()
                    if s.status == "active"
                ])
            }
        }
    
    def to_workflow_step(self) -> Callable:
        """转换为工作流步骤"""
        async def coordinator_step(context: Dict) -> Dict[str, Any]:
            goal = context.get("goal", "")
            agent_configs = context.get("agents", [])
            
            if not goal:
                raise ValueError("协作目标不能为空")
            
            # 创建会话
            session = self.create_session(
                name=f"Session-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                goal=goal
            )
            
            # 注册 Agent
            for config in agent_configs:
                self.register_agent(
                    agent_id=config["id"],
                    name=config["name"],
                    role=AgentRole(config["role"]),
                    capabilities=config.get("capabilities", [])
                )
                self.add_agent_to_session(session.id, config["id"])
            
            context["session_id"] = session.id
            context["coordinator_stats"] = self.get_stats()
            
            return context
        
        return coordinator_step


# ============ 工作流模板 ============

class MultiAgentWorkflowTemplates:
    """多 Agent 协作工作流模板"""
    
    @staticmethod
    def create_planner_executor_workflow(
        coordinator: MultiAgentCoordinator,
        goal: str,
        tasks: List[Dict]
    ) -> CollaborationSession:
        """
        创建规划者 - 执行者工作流
        
        模式：
        1. 规划者拆解任务
        2. 执行者并行执行
        3. 审核者验证结果
        """
        session = coordinator.create_session(
            name="Planner-Executor Workflow",
            goal=goal
        )
        
        # 注册角色
        planner = coordinator.register_agent(
            agent_id="planner-1",
            name="规划者",
            role=AgentRole.PLANNER,
            capabilities=["task_decomposition", "planning"]
        )
        
        executors = []
        for i in range(2):
            executor = coordinator.register_agent(
                agent_id=f"executor-{i+1}",
                name=f"执行者{i+1}",
                role=AgentRole.EXECUTOR,
                capabilities=["execution", "implementation"]
            )
            executors.append(executor)
        
        reviewer = coordinator.register_agent(
            agent_id="reviewer-1",
            name="审核者",
            role=AgentRole.REVIEWER,
            capabilities=["review", "quality_check"]
        )
        
        # 添加到会话
        for agent in [planner] + executors + [reviewer]:
            coordinator.add_agent_to_session(session.id, agent.id)
        
        # 创建任务
        main_task = coordinator.create_task(
            name="Main Task",
            description=goal,
            priority=TaskPriority.HIGH
        )
        coordinator.add_task_to_session(session.id, main_task.id)
        
        # 创建子任务
        for i, task_def in enumerate(tasks):
            sub_task = coordinator.create_task(
                name=task_def.get("name", f"Sub-Task-{i+1}"),
                description=task_def.get("description", ""),
                dependencies=[main_task.id] if i == 0 else [f"sub-task-{i}"],
                parent_task_id=main_task.id
            )
            coordinator.add_task_to_session(session.id, sub_task.id)
        
        return session
    
    @staticmethod
    def create_parallel_execution_workflow(
        coordinator: MultiAgentCoordinator,
        goal: str,
        parallel_tasks: List[Dict]
    ) -> CollaborationSession:
        """
        创建并行执行工作流
        
        模式：多个执行者并行执行独立任务
        """
        session = coordinator.create_session(
            name="Parallel Execution Workflow",
            goal=goal
        )
        
        # 注册执行者
        executors = []
        for i in range(len(parallel_tasks)):
            executor = coordinator.register_agent(
                agent_id=f"parallel-executor-{i+1}",
                name=f"并行执行者{i+1}",
                role=AgentRole.EXECUTOR,
                capabilities=["parallel_execution"]
            )
            executors.append(executor)
            coordinator.add_agent_to_session(session.id, executor.id)
        
        # 创建并行任务（无依赖）
        for i, task_def in enumerate(parallel_tasks):
            task = coordinator.create_task(
                name=task_def.get("name", f"Parallel-Task-{i+1}"),
                description=task_def.get("description", ""),
                priority=TaskPriority.NORMAL
            )
            coordinator.add_task_to_session(session.id, task.id)
            
            # 分配给执行者
            coordinator.assign_task(task.id, executors[i].id)
        
        return session


# ============ 主程序 ============

async def main():
    """测试多 Agent 协调器"""
    logging.basicConfig(level=logging.INFO)
    
    # 创建协调器
    coordinator = MultiAgentCoordinator()
    
    # 注册 Agent
    planner = coordinator.register_agent(
        agent_id="planner-1",
        name="规划者",
        role=AgentRole.PLANNER,
        capabilities=["planning", "decomposition"]
    )
    
    executor1 = coordinator.register_agent(
        agent_id="executor-1",
        name="执行者 1",
        role=AgentRole.EXECUTOR,
        capabilities=["coding", "testing"]
    )
    
    executor2 = coordinator.register_agent(
        agent_id="executor-2",
        name="执行者 2",
        role=AgentRole.EXECUTOR,
        capabilities=["documentation", "review"]
    )
    
    reviewer = coordinator.register_agent(
        agent_id="reviewer-1",
        name="审核者",
        role=AgentRole.REVIEWER,
        capabilities=["quality_check", "validation"]
    )
    
    print("\n已注册 Agent:")
    for agent in coordinator.list_agents():
        print(f"  - {agent.name} ({agent.role.value})")
    
    # 创建任务
    task1 = coordinator.create_task(
        name="任务 1",
        description="第一个子任务",
        priority=TaskPriority.HIGH
    )
    
    task2 = coordinator.create_task(
        name="任务 2",
        description="第二个子任务",
        dependencies=[task1.id]
    )
    
    task3 = coordinator.create_task(
        name="任务 3",
        description="第三个子任务",
        dependencies=[task1.id]
    )
    
    print("\n已创建任务:")
    for task in coordinator.list_tasks():
        print(f"  - {task.name} (依赖：{task.dependencies})")
    
    # 分配任务
    coordinator.assign_task(task1.id, planner.id)
    
    print("\n协调器统计:")
    stats = coordinator.get_stats()
    print(f"  Agent 总数：{stats['agents']['total']}")
    print(f"  任务总数：{stats['tasks']['total']}")
    
    print("\n多 Agent 协调器测试完成")


if __name__ == "__main__":
    asyncio.run(main())
