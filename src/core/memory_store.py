#!/usr/bin/env python3
"""
Memory Store Module - 记忆存储模块

Provides long-term memory storage with ChromaDB and short-term caching.
长期记忆存储（ChromaDB）和短期记忆缓存。

Author: AgentM Core Team
"""

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import json


class MemoryType(str, Enum):
    """记忆类型枚举"""
    SHORT_TERM = "short_term"  # 短期记忆
    LONG_TERM = "long_term"    # 长期记忆
    WORKING = "working"        # 工作记忆
    EPISODIC = "episodic"      # 情景记忆
    SEMANTIC = "semantic"      # 语义记忆


class ConfidenceLevel(float, Enum):
    """置信度级别"""
    VERY_LOW = 0.2
    LOW = 0.4
    MEDIUM = 0.6
    HIGH = 0.8
    VERY_HIGH = 1.0


@dataclass
class Memory:
    """
    记忆数据结构
    
    Attributes:
        content: 记忆内容
        memory_type: 记忆类型
        metadata: 元数据
        confidence: 置信度 (0.0-1.0)
        created_at: 创建时间
        updated_at: 更新时间
        access_count: 访问次数
        memory_id: 记忆 ID
    """
    content: str
    memory_type: MemoryType = MemoryType.LONG_TERM
    metadata: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    access_count: int = 0
    memory_id: str = field(default_factory=lambda: f"mem_{datetime.utcnow().timestamp()}")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            **asdict(self),
            'memory_type': self.memory_type.value
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Memory":
        """从字典创建"""
        data = data.copy()
        if 'memory_type' in data and isinstance(data['memory_type'], str):
            data['memory_type'] = MemoryType(data['memory_type'])
        return cls(**data)
    
    def generate_embedding_key(self) -> str:
        """生成用于向量检索的键"""
        return hashlib.sha256(self.content.encode()).hexdigest()[:16]


@dataclass
class MemoryQueryResult:
    """记忆查询结果"""
    memory: Memory
    distance: float  # 向量距离，越小越相关
    score: float     # 综合得分


class MemoryStore:
    """
    记忆存储类
    
    提供分层记忆存储：
    - 长期记忆：ChromaDB 向量存储
    - 短期记忆：内存缓存（LRU）
    - 支持记忆检索、更新置信度
    
    Attributes:
        chromadb_path: ChromaDB 数据路径
        cache_ttl: 缓存生存时间（秒）
        max_memories: 最大记忆数量
    """
    
    def __init__(
        self,
        chromadb_path: Optional[str] = None,
        cache_ttl: int = 3600,
        max_memories: int = 10000
    ):
        """
        初始化记忆存储
        
        Args:
            chromadb_path: ChromaDB 数据路径
            cache_ttl: 缓存生存时间（秒）
            max_memories: 最大记忆数量
        """
        self._chromadb_path = Path(chromadb_path) if chromadb_path else None
        self._cache_ttl = cache_ttl
        self._max_memories = max_memories
        
        # 短期记忆缓存 (memory_id -> Memory)
        self._short_term_cache: Dict[str, Tuple[Memory, float]] = {}
        
        # ChromaDB 客户端（延迟初始化）
        self._chroma_client = None
        self._collection = None
        
        # 日志
        self._logger = logging.getLogger(__name__)
        
        # 确保持久化目录存在
        if self._chromadb_path:
            self._chromadb_path.parent.mkdir(parents=True, exist_ok=True)
    
    def _init_chromadb(self) -> None:
        """初始化 ChromaDB 连接"""
        try:
            import chromadb
            from chromadb.config import Settings
            
            if self._chromadb_path:
                self._chroma_client = chromadb.PersistentClient(
                    path=str(self._chromadb_path)
                )
            else:
                self._chroma_client = chromadb.Client()
            
            # 获取或创建集合
            self._collection = self._chroma_client.get_or_create_collection(
                name="agentm_memories",
                metadata={"description": "AgentM long-term memory storage"}
            )
            
            self._logger.info("ChromaDB initialized successfully")
            
        except ImportError:
            self._logger.warning("ChromaDB not installed, using in-memory storage only")
        except Exception as e:
            self._logger.error(f"Failed to initialize ChromaDB: {e}")
    
    @property
    def chroma_client(self):
        """懒加载 ChromaDB 客户端"""
        if self._chroma_client is None:
            self._init_chromadb()
        return self._chroma_client
    
    @property
    def collection(self):
        """懒加载 ChromaDB 集合"""
        if self._collection is None:
            self._init_chromadb()
        return self._collection
    
    def add_memory(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        memory_type: MemoryType = MemoryType.LONG_TERM,
        confidence: float = 0.5
    ) -> Memory:
        """
        添加记忆
        
        Args:
            content: 记忆内容
            metadata: 元数据
            memory_type: 记忆类型
            confidence: 初始置信度
        
        Returns:
            创建的 Memory 对象
        
        Raises:
            ValueError: 当内容为空时
        """
        if not content or not content.strip():
            raise ValueError("Memory content cannot be empty")
        
        memory = Memory(
            content=content,
            memory_type=memory_type,
            metadata=metadata or {},
            confidence=confidence
        )
        
        # 添加到短期缓存
        self._add_to_cache(memory)
        
        # 添加到长期存储
        if self.collection:
            try:
                # ChromaDB 要求元数据是扁平的键值对
                chroma_metadata = {
                    "memory_type": memory.memory_type.value,
                    "confidence": memory.confidence,
                    "created_at": memory.created_at,
                    "access_count": memory.access_count
                }
                # 添加简单元数据（扁平化）
                if memory.metadata:
                    for k, v in memory.metadata.items():
                        if isinstance(v, (str, int, float, bool, type(None))):
                            chroma_metadata[k] = v
                        elif isinstance(v, list):
                            chroma_metadata[k] = v
                
                self.collection.add(
                    ids=[memory.memory_id],
                    documents=[content],
                    metadatas=[chroma_metadata],
                )
                self._logger.debug(f"Memory added to ChromaDB: {memory.memory_id}")
            except Exception as e:
                self._logger.error(f"Failed to add memory to ChromaDB: {e}")
        
        self._logger.info(f"Memory added: {memory.memory_id} (type={memory_type.value})")
        return memory
    
    def _add_to_cache(self, memory: Memory) -> None:
        """添加到短期缓存"""
        current_time = time.time()
        
        # 清理过期缓存
        self._cleanup_cache()
        
        # 检查是否超过最大数量
        if len(self._short_term_cache) >= self._max_memories:
            # 移除最旧的
            oldest_id = min(
                self._short_term_cache.keys(),
                key=lambda k: self._short_term_cache[k][1]
            )
            del self._short_term_cache[oldest_id]
        
        self._short_term_cache[memory.memory_id] = (memory, current_time)
    
    def _cleanup_cache(self) -> None:
        """清理过期缓存"""
        current_time = time.time()
        expired = [
            mem_id for mem_id, (_, timestamp) in self._short_term_cache.items()
            if current_time - timestamp > self._cache_ttl
        ]
        for mem_id in expired:
            del self._short_term_cache[mem_id]
    
    def search_memories(
        self,
        query: str,
        limit: int = 10,
        memory_type: Optional[MemoryType] = None,
        min_confidence: float = 0.0
    ) -> List[MemoryQueryResult]:
        """
        搜索记忆
        
        Args:
            query: 搜索查询
            limit: 最大返回数量
            memory_type: 记忆类型过滤
            min_confidence: 最小置信度
        
        Returns:
            记忆查询结果列表
        """
        results = []
        
        # 首先搜索 ChromaDB
        if self.collection:
            try:
                # 构建过滤条件
                where = {}
                if memory_type:
                    where["memory_type"] = memory_type.value
                if min_confidence > 0:
                    where["confidence"] = {"$gte": min_confidence}
                
                chroma_results = self.collection.query(
                    query_texts=[query],
                    n_results=limit,
                    where=where if where else None,
                    include=["documents", "metadatas", "distances"]
                )
                
                # 解析结果
                if chroma_results and chroma_results['ids']:
                    for i, mem_id in enumerate(chroma_results['ids'][0]):
                        metadata = chroma_results['metadatas'][0][i] if chroma_results['metadatas'] else {}
                        distance = chroma_results['distances'][0][i] if chroma_results['distances'] else 0.0
                        
                        # 从元数据重建 Memory
                        memory = Memory(
                            content=chroma_results['documents'][0][i] if chroma_results['documents'] else "",
                            memory_type=MemoryType(metadata.get('memory_type', 'long_term')),
                            metadata=metadata,
                            confidence=metadata.get('confidence', 0.5),
                            memory_id=mem_id
                        )
                        
                        # 计算综合得分（距离越小越好，置信度越高越好）
                        score = (1.0 - distance) * memory.confidence
                        
                        results.append(MemoryQueryResult(
                            memory=memory,
                            distance=distance,
                            score=score
                        ))
                        
                        # 更新访问计数
                        memory.access_count += 1
                        
            except Exception as e:
                self._logger.error(f"Failed to search ChromaDB: {e}")
        
        # 如果 ChromaDB 没有结果或不可用，回退到 JSON 文件搜索
        if not results:
            self._logger.info("ChromaDB 没有结果，回退到 JSON 文件搜索")
            json_results = self._search_json_file(query, limit)
            self._logger.info(f"JSON 文件搜索返回 {len(json_results)} 条结果")
            for mem in json_results:
                results.append(MemoryQueryResult(
                    memory=mem,
                    distance=0.0,
                    score=mem.confidence
                ))
        
        # 也搜索短期缓存
        cache_results = self._search_cache(query, limit - len(results))
        for cache_mem in cache_results:
            if not any(r.memory.memory_id == cache_mem.memory_id for r in results):
                results.append(MemoryQueryResult(
                    memory=cache_mem,
                    distance=0.0,
                    score=cache_mem.confidence
                ))
        
        # 按得分排序
        results.sort(key=lambda x: x.score, reverse=True)
        
        self._logger.info(f"Search returned {len(results)} memories for query: {query[:50]}...")
        return results
    
    def _search_json_file(self, query: str, limit: int) -> List[Memory]:
        """在 JSON 文件中搜索记忆"""
        results = []
        try:
            # 使用固定的记忆文件路径
            json_path = "/tmp/agentm/memory.json"
            if os.path.exists(json_path):
                with open(json_path, 'r') as f:
                    data = json.load(f)
                    facts = data.get('facts', [])
                    query_lower = query.lower()
                    for fact_data in facts:
                        if query_lower in fact_data.get('content', '').lower():
                            memory = Memory(
                                content=fact_data.get('content', ''),
                                memory_type=MemoryType(fact_data.get('category', 'long_term')),
                                metadata={'source': fact_data.get('source', '')},
                                confidence=fact_data.get('confidence', 0.5),
                                memory_id=fact_data.get('id', '')
                            )
                            results.append(memory)
                            if len(results) >= limit:
                                break
        except Exception as e:
            self._logger.error(f"Failed to search JSON file: {e}")
        return results
    
    def _search_cache(self, query: str, limit: int) -> List[Memory]:
        """在短期缓存中搜索"""
        # 简单文本匹配（生产环境可用更复杂的相似度计算）
        query_lower = query.lower()
        matches = []
        
        for memory, _ in self._short_term_cache.values():
            if query_lower in memory.content.lower():
                matches.append(memory)
                if len(matches) >= limit:
                    break
        
        return matches
    
    def get_memory(self, memory_id: str) -> Optional[Memory]:
        """
        根据 ID 获取记忆
        
        Args:
            memory_id: 记忆 ID
        
        Returns:
            Memory 对象或 None
        """
        # 先查缓存
        if memory_id in self._short_term_cache:
            memory, _ = self._short_term_cache[memory_id]
            memory.access_count += 1
            return memory
        
        # 再查长期存储
        if self.collection:
            try:
                results = self.collection.get(
                    ids=[memory_id],
                    include=["documents", "metadatas"]
                )
                
                if results and results['ids']:
                    metadata = results['metadatas'][0] if results['metadatas'] else {}
                    memory = Memory(
                        content=results['documents'][0] if results['documents'] else "",
                        memory_type=MemoryType(metadata.get('memory_type', 'long_term')),
                        metadata=metadata,
                        confidence=metadata.get('confidence', 0.5),
                        memory_id=memory_id
                    )
                    
                    # 加入缓存
                    self._add_to_cache(memory)
                    return memory
                    
            except Exception as e:
                self._logger.error(f"Failed to get memory from ChromaDB: {e}")
        
        return None
    
    def update_confidence(self, memory_id: str, confidence: float) -> bool:
        """
        更新记忆置信度
        
        Args:
            memory_id: 记忆 ID
            confidence: 新置信度 (0.0-1.0)
        
        Returns:
            bool: 是否成功更新
        """
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        
        memory = self.get_memory(memory_id)
        if not memory:
            self._logger.warning(f"Memory not found: {memory_id}")
            return False
        
        memory.confidence = confidence
        memory.updated_at = datetime.utcnow().isoformat()
        
        # 更新缓存
        self._add_to_cache(memory)
        
        # 更新长期存储
        if self.collection:
            try:
                # ChromaDB 要求元数据是扁平的键值对
                chroma_metadata = {
                    "memory_type": memory.memory_type.value,
                    "confidence": memory.confidence,
                    "created_at": memory.created_at,
                    "access_count": memory.access_count
                }
                
                self.collection.update(
                    ids=[memory_id],
                    metadatas=[chroma_metadata]
                )
            except Exception as e:
                self._logger.error(f"Failed to update memory in ChromaDB: {e}")
                return False
        
        self._logger.info(f"Memory confidence updated: {memory_id} -> {confidence}")
        return True
    
    def delete_memory(self, memory_id: str) -> bool:
        """
        删除记忆
        
        Args:
            memory_id: 记忆 ID
        
        Returns:
            bool: 是否成功删除
        """
        # 从缓存移除
        if memory_id in self._short_term_cache:
            del self._short_term_cache[memory_id]
        
        # 从长期存储移除
        if self.collection:
            try:
                self.collection.delete(ids=[memory_id])
                self._logger.info(f"Memory deleted: {memory_id}")
                return True
            except Exception as e:
                self._logger.error(f"Failed to delete memory from ChromaDB: {e}")
                return False
        
        return True
    
    def get_memories_by_type(
        self,
        memory_type: MemoryType,
        limit: int = 100
    ) -> List[Memory]:
        """
        根据类型获取记忆
        
        Args:
            memory_type: 记忆类型
            limit: 最大返回数量
        
        Returns:
            Memory 列表
        """
        memories = []
        
        if self.collection:
            try:
                results = self.collection.get(
                    where={"memory_type": memory_type.value},
                    limit=limit,
                    include=["documents", "metadatas"]
                )
                
                if results and results['ids']:
                    for i, mem_id in enumerate(results['ids']):
                        metadata = results['metadatas'][i] if results['metadatas'] else {}
                        memory = Memory(
                            content=results['documents'][i] if results['documents'] else "",
                            memory_type=memory_type,
                            metadata=metadata,
                            confidence=metadata.get('confidence', 0.5),
                            memory_id=mem_id
                        )
                        memories.append(memory)
                        
            except Exception as e:
                self._logger.error(f"Failed to get memories by type: {e}")
        
        return memories
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取记忆存储统计信息
        
        Returns:
            统计信息字典
        """
        stats = {
            "short_term_cache_size": len(self._short_term_cache),
            "long_term_count": 0,
            "memory_types": {},
            "avg_confidence": 0.0
        }
        
        if self.collection:
            try:
                # 获取总数
                stats["long_term_count"] = self.collection.count()
                
                # 获取类型分布（简化实现）
                # 生产环境可用更高效的聚合查询
                
            except Exception as e:
                self._logger.error(f"Failed to get statistics: {e}")
        
        return stats
    
    def clear_cache(self) -> None:
        """清空短期缓存"""
        self._short_term_cache.clear()
        self._logger.info("Short-term cache cleared")


# 全局单例
_memory_store: Optional[MemoryStore] = None


def get_memory_store() -> MemoryStore:
    """
    获取全局记忆存储单例
    
    Returns:
        MemoryStore 实例
    """
    global _memory_store
    if _memory_store is None:
        _memory_store = MemoryStore()
    return _memory_store


async def main():
    """记忆存储独立进程入口（用于测试）"""
    import yaml
    
    # 加载配置
    config_path = Path(__file__).parent.parent / "config.yaml"
    config = {}
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    
    memory_config = config.get('memory', {})
    
    # 创建记忆存储
    store = MemoryStore(
        chromadb_path=memory_config.get('chromadb_path'),
        cache_ttl=memory_config.get('cache_ttl', 3600),
        max_memories=memory_config.get('max_memories', 10000)
    )
    
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 测试功能
    logging.info("Memory Store initialized")
    
    # 添加测试记忆
    test_memory = store.add_memory(
        content="AgentM Core 是一个自主 Agent 系统",
        metadata={"source": "test", "category": "system"},
        memory_type=MemoryType.SEMANTIC,
        confidence=0.9
    )
    logging.info(f"Test memory added: {test_memory.memory_id}")
    
    # 搜索测试
    results = store.search_memories("AgentM", limit=5)
    logging.info(f"Search returned {len(results)} results")
    
    # 统计信息
    stats = store.get_statistics()
    logging.info(f"Statistics: {stats}")
    
    logging.info("Memory Store test completed")


if __name__ == "__main__":
    asyncio.run(main())
