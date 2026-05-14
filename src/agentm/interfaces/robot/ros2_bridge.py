"""
机器人接口（ROS 2 桥接）

通过 ROS 2 接入硬件传感器/执行器

功能：
  - 接收传感器数据 → 传给主 Agent
  - 接收 Agent 执行结果 → 控制执行器
  - 支持话题（Topic）、服务（Service）、动作（Action）

前置依赖：
  - ROS 2 Humble+
  - rclpy

注意：Windows 上 ROS 2 支持有限，此接口主要在 Linux/嵌入式设备上运行
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

# ROS 2 相关（条件导入，Windows 下优雅降级）
try:
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String, Int32, Float32
    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False
    Node = object  # 占位，防止后续代码报错


@dataclass
class SensorReading:
    """传感器读数"""
    sensor_id: str
    sensor_type: str  # camera / lidar / imu / temperature / ...
    value: Any
    timestamp: float


@dataclass
class ActuatorCommand:
    """执行器指令"""
    actuator_id: str
    command: str  # move / grip / stop / ...
    params: dict
    timestamp: float


class ROS2Bridge:
    """
    ROS 2 桥接器

    在 ROS 2 环境下运行时：
      - 订阅传感器话题，接收数据
      - 向执行器话题发布指令

    在非 ROS 2 环境下：
      - 模拟模式，提供 mock 数据
      - 供开发和测试用
    """

    def __init__(
        self,
        node_name: str = "agentm_bridge",
        sensor_callback: Callable[[SensorReading], None] | None = None,
        command_callback: Callable[[ActuatorCommand], None] | None = None,
    ):
        self.node_name = node_name
        self.sensor_callback = sensor_callback
        self.command_callback = command_callback
        self._node = None
        self._subscriptions = []
        self._mock_mode = not ROS2_AVAILABLE

        if not ROS2_AVAILABLE:
            import logging
            logging.warning(
                "ROS 2 (rclpy) not available. "
                "Running in mock mode for development/testing."
            )

    def start(self):
        """启动桥接器"""
        if self._mock_mode:
            return

        rclpy.init()
        self._node = rclpy.node.Node(self.node_name)
        self._setup_subscriptions()
        self._spin_async()

    def _setup_subscriptions(self):
        """设置 ROS 2 话题订阅"""
        # 示例：订阅传感器话题
        # 实际使用时根据具体硬件配置话题
        topics = [
            ("/sensor/camera", String),
            ("/sensor/lidar", String),
            ("/sensor/imu", String),
        ]

        for topic, msg_type in topics:
            sub = self._node.create_subscription(
                msg_type,
                topic,
                lambda msg, t=topic: self._on_sensor_message(t, msg),
                10,
            )
            self._subscriptions.append(sub)

    def _on_sensor_message(self, topic: str, msg):
        """处理传感器消息"""
        if self.sensor_callback:
            reading = SensorReading(
                sensor_id=topic,
                sensor_type=topic.split("/")[-1],
                value=msg.data,
                timestamp=time.time(),
            )
            self.sensor_callback(reading)

    def publish_command(self, command: ActuatorCommand):
        """发布执行器指令"""
        if self._mock_mode:
            # Mock 模式：打印指令
            print(f"[Mock Actuator] {command.actuator_id}: {command.command} {command.params}")
            if self.command_callback:
                self.command_callback(command)
            return

        # 实际 ROS 2 发布
        cmd_msg = String()
        cmd_msg.data = json.dumps({
            "actuator_id": command.actuator_id,
            "command": command.command,
            "params": command.params,
            "timestamp": command.timestamp,
        })

        # 发布到执行器话题
        topic = f"/actuator/{command.actuator_id}"
        pub = self._node.create_publisher(String, topic, 10)
        pub.publish(cmd_msg)

    def _spin_async(self):
        """异步 spin ROS 节点"""
        # 在独立线程中 spin
        import threading
        spin_thread = threading.Thread(target=self._spin, daemon=True)
        spin_thread.start()

    def _spin(self):
        """Spin ROS 节点"""
        while rclpy.ok():
            rclpy.spin_once(self._node, timeout_sec=0.1)

    def stop(self):
        """停止桥接器"""
        if not self._mock_mode and self._node:
            self._node.destroy_node()
            rclpy.shutdown()

    # ------------------------------------------------------------------
    # Mock 模式（开发/测试用）
    # ------------------------------------------------------------------

    def simulate_sensor_reading(
        self,
        sensor_id: str = "mock_camera",
        sensor_type: str = "camera",
        value: Any = None,
    ):
        """模拟一条传感器读数（Mock 模式下调用）"""
        if value is None:
            value = {"frame_id": 0, "data": "mock_image_data"}

        reading = SensorReading(
            sensor_id=sensor_id,
            sensor_type=sensor_type,
            value=value,
            timestamp=time.time(),
        )

        if self.sensor_callback:
            self.sensor_callback(reading)

        return reading


# ---------------------------------------------------------------------------
# Integration with Main Agent
# ---------------------------------------------------------------------------

class RobotAgentBridge:
    """
    机器人 Agent 桥接

    将 ROS 2 传感器数据接入主 Agent：
      传感器数据 → 主 Agent 分析 → 执行器指令 → ROS 2 发布
    """

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self.bridge = ROS2Bridge(
            sensor_callback=self._on_sensor_data,
        )

    def _on_sensor_data(self, reading: SensorReading):
        """传感器数据到达 → 传给主 Agent"""
        # 构建任务描述
        task = f"传感器 {reading.sensor_id} 读数：{reading.value}。需要分析并给出执行建议。"

        # 异步执行
        asyncio.create_task(self._run_analysis(task))

    async def _run_analysis(self, task: str):
        """运行主 Agent 分析"""
        async for chunk in self.coordinator.run(task):
            # 分析结果可以用于决策
            pass

    def send_command(self, actuator_id: str, command: str, params: dict):
        """发送执行器指令"""
        cmd = ActuatorCommand(
            actuator_id=actuator_id,
            command=command,
            params=params,
            timestamp=time.time(),
        )
        self.bridge.publish_command(cmd)
