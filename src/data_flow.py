"""
Data Flow - 数据流增强

提供 JSON 数组传递、数据转换和映射功能。
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class DataPacket:
    """数据包"""
    data: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    source_node: Optional[str] = None
    target_node: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "data": self.data,
            "metadata": self.metadata,
            "source_node": self.source_node,
            "target_node": self.target_node
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DataPacket":
        """从字典创建"""
        return cls(
            data=data.get("data"),
            metadata=data.get("metadata", {}),
            source_node=data.get("source_node"),
            target_node=data.get("target_node")
        )


class DataTransformer:
    """数据转换器"""
    
    @staticmethod
    def transform(
        data: Any,
        transformation: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """转换数据"""
        context = context or {}
        
        if transformation == "identity":
            return data
        
        elif transformation == "to_list":
            if isinstance(data, list):
                return data
            return [data]
        
        elif transformation == "to_dict":
            if isinstance(data, dict):
                return data
            return {"value": data}
        
        elif transformation == "flatten":
            if isinstance(data, list):
                result = []
                for item in data:
                    if isinstance(item, list):
                        result.extend(item)
                    else:
                        result.append(item)
                return result
            return data
        
        elif transformation == "group_by":
            if isinstance(data, list) and context.get("key"):
                key = context["key"]
                grouped = {}
                for item in data:
                    if isinstance(item, dict) and key in item:
                        group_key = item[key]
                        if group_key not in grouped:
                            grouped[group_key] = []
                        grouped[group_key].append(item)
                return grouped
            return data
        
        elif transformation == "filter":
            if isinstance(data, list) and context.get("condition"):
                condition = context["condition"]
                return [item for item in data if DataTransformer._evaluate_condition(item, condition)]
            return data
        
        elif transformation == "map":
            if isinstance(data, list) and context.get("mapping"):
                mapping = context["mapping"]
                return [DataTransformer._apply_mapping(item, mapping) for item in data]
            return data
        
        elif transformation == "reduce":
            if isinstance(data, list) and context.get("reducer"):
                reducer = context["reducer"]
                initial = context.get("initial", None)
                result = initial
                for item in data:
                    result = reducer(result, item)
                return result
            return data
        
        elif transformation == "json_serialize":
            return json.dumps(data, ensure_ascii=False, default=str)
        
        elif transformation == "json_deserialize":
            if isinstance(data, str):
                return json.loads(data)
            return data
        
        else:
            logger.warning(f"未知转换类型：{transformation}")
            return data
    
    @staticmethod
    def _evaluate_condition(item: Any, condition: Dict[str, Any]) -> bool:
        """评估条件"""
        if not isinstance(item, dict):
            return False
        
        for key, expected in condition.items():
            if key not in item:
                return False
            
            actual = item[key]
            
            if isinstance(expected, dict):
                op = expected.get("op", "eq")
                value = expected.get("value")
                
                if op == "eq" and actual != value:
                    return False
                elif op == "ne" and actual == value:
                    return False
                elif op == "gt" and not (actual > value):
                    return False
                elif op == "gte" and not (actual >= value):
                    return False
                elif op == "lt" and not (actual < value):
                    return False
                elif op == "lte" and not (actual <= value):
                    return False
                elif op == "in" and value not in actual:
                    return False
                elif op == "contains" and value not in actual:
                    return False
            else:
                if actual != expected:
                    return False
        
        return True
    
    @staticmethod
    def _apply_mapping(item: Any, mapping: Dict[str, str]) -> Dict[str, Any]:
        """应用映射"""
        if not isinstance(item, dict):
            item = {"value": item}
        
        result = {}
        for target_key, source_key in mapping.items():
            if source_key in item:
                result[target_key] = item[source_key]
            elif "." in source_key:
                value = DataTransformer._get_nested_value(item, source_key)
                if value is not None:
                    result[target_key] = value
        
        return result
    
    @staticmethod
    def _get_nested_value(data: Dict[str, Any], path: str) -> Any:
        """获取嵌套值"""
        keys = path.split(".")
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current


class DataMapper:
    """数据映射器"""
    
    def __init__(self):
        self._mappings: Dict[str, Dict[str, str]] = {}
    
    def add_mapping(
        self,
        source_node: str,
        target_node: str,
        field_mapping: Dict[str, str]
    ) -> None:
        """添加字段映射"""
        key = f"{source_node}->{target_node}"
        self._mappings[key] = field_mapping
        logger.debug(f"添加映射：{key} = {field_mapping}")
    
    def map_data(
        self,
        source_node: str,
        target_node: str,
        data: Any
    ) -> Any:
        """映射数据"""
        key = f"{source_node}->{target_node}"
        
        if key not in self._mappings:
            logger.debug(f"未找到映射：{key}，返回原始数据")
            return data
        
        mapping = self._mappings[key]
        
        if isinstance(data, list):
            return [DataTransformer._apply_mapping(item, mapping) for item in data]
        elif isinstance(data, dict):
            return DataTransformer._apply_mapping(data, mapping)
        else:
            return data
    
    def clear_mappings(self) -> None:
        """清除所有映射"""
        self._mappings.clear()


class DataFlowManager:
    """数据流管理器"""
    
    def __init__(self):
        self.transformer = DataTransformer()
        self.mapper = DataMapper()
        self._data_store: Dict[str, DataPacket] = {}
    
    def send(
        self,
        source_node: str,
        target_node: str,
        data: Any,
        transformation: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> DataPacket:
        """发送数据"""
        if transformation:
            data = self.transformer.transform(data, transformation)
        
        packet = DataPacket(
            data=data,
            metadata=metadata or {},
            source_node=source_node,
            target_node=target_node
        )
        
        store_key = f"{source_node}->{target_node}"
        self._data_store[store_key] = packet
        
        logger.debug(f"发送数据：{source_node} -> {target_node}")
        return packet
    
    def receive(
        self,
        target_node: str,
        source_node: Optional[str] = None
    ) -> Optional[Any]:
        """接收数据"""
        if source_node:
            store_key = f"{source_node}->{target_node}"
            packet = self._data_store.get(store_key)
        else:
            for key, packet in self._data_store.items():
                if packet.target_node == target_node:
                    return packet.data
            return None
        
        if packet:
            return packet.data
        return None
    
    def map_and_send(
        self,
        source_node: str,
        target_node: str,
        data: Any
    ) -> DataPacket:
        """映射并发送数据"""
        mapped_data = self.mapper.map_data(source_node, target_node, data)
        return self.send(source_node, target_node, mapped_data)
    
    def add_mapping(
        self,
        source_node: str,
        target_node: str,
        field_mapping: Dict[str, str]
    ) -> None:
        """添加字段映射"""
        self.mapper.add_mapping(source_node, target_node, field_mapping)
    
    def transform_data(
        self,
        data: Any,
        transformation: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """转换数据"""
        return self.transformer.transform(data, transformation, context)
    
    def get_all_packets(self) -> List[DataPacket]:
        """获取所有数据包"""
        return list(self._data_store.values())
    
    def clear(self) -> None:
        """清除数据流"""
        self._data_store.clear()
        self.mapper.clear_mappings()


def create_data_flow() -> DataFlowManager:
    """创建数据流管理器"""
    return DataFlowManager()
