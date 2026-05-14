"""
记忆系统（M 记忆空间）

基于 ChromaDB 的向量存储，支持：
  - 任务记忆、决策记忆、推理链记忆、反馈记忆
  - 极细颗粒度，向量化语义搜索
  - HOT/WARM/COLD 三层分级（参考 Self-Improving+）
  - AGI 继承时能还原完整推理过程
"""

from __future__ import annotations

import uuid
import time
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer

from ..core.llm_engine import get_llm_engine


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class MemoryTier(Enum):
    HOT = "hot"      # 频繁使用，永久加载
    WARM = "warm"   # 近期使用，按需加载
    COLD = "cold"   # 归档，很少使用


class MemoryType(Enum):
    TASK = "task"                     # 任务记忆
    DECISION = "decision"             # 决策记忆
    REASONING_CHAIN = "reasoning_chain"  # 推理链
    FEEDBACK = "feedback"              # 反馈记忆（成功/失败）
    EVOLUTION = "evolution"           # 进化记忆
    PREFERENCE = "preference"         # 偏好记忆
    KNOWLEDGE = "knowledge"          # 知识空白/学到


@dataclass
class Memory:
    """单条记忆"""
    id: str
    type: MemoryType
    tier: MemoryTier

    # 内容
    content: str              # 自然语言描述
    raw_data: dict | None = None  # 结构化原始数据

    # 语义向量（自动生成）
    embedding: list[float] | None = None

    # 关联
    tags: list[str] = field(default_factory=list)
    parent_id: str | None = None  # 父记忆ID（推理链用）

    # 评分
    use_count: int = 0
    importance: float = 0.5  # 0-1，对记忆重要性的主观评分

    # 时间戳
    created_at: float = field(default_factory=time.time)
    last_accessed_at: float = field(default_factory=time.time)
    last_modified_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Memory":
        data["type"] = MemoryType(data["type"])
        data["tier"] = MemoryTier(data["tier"])
        return cls(**data)

    def to_text(self) -> str:
        """转换为可读文本，用于向量化和展示"""
        lines = [
            f"[{self.type.value.upper()}] {self.content}",
        ]
        if self.tags:
            lines.append(f"Tags: {', '.join(self.tags)}")
        if self.raw_data:
            lines.append(f"Data: {json.dumps(self.raw_data, ensure_ascii=False)}")
        lines.append(f"Used {self.use_count}x | Importance: {self.importance:.1f}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Embedding Engine
# ---------------------------------------------------------------------------

class EmbeddingEngine:
    """
    语义向量化引擎
    使用 Sentence-Transformers 生成文本向量
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode(self, texts: str | list[str]) -> list[float] | list[list[float]]:
        """生成文本向量"""
        if isinstance(texts, str):
            texts = [texts]
        vectors = self.model.encode(texts, normalize_embeddings=True)
        return vectors.tolist()


# ---------------------------------------------------------------------------
# Memory Store (ChromaDB)
# ---------------------------------------------------------------------------

class MemoryStore:
    """
    ChromaDB 向量记忆存储

    支持：
      - 语义搜索（Similarity search）
      - 精确过滤（Filter by type/tier/tag）
      - HOT/WARM/COLD 分层
      - 推理链追溯
    """

    COLLECTION_NAME = "agentm_memories"

    def __init__(
        self,
        persist_dir: str | Path | None = None,
        embedding_model: str = "all-MiniLM-L6-v2",
    ):
        if persist_dir is None:
            persist_dir = Path("D:/agentm/data/memory")
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir / "chroma_db"),
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )

        try:
            self.collection = self.client.get_collection(name=self.COLLECTION_NAME)
        except Exception:
            self.collection = self.client.create_collection(
                name=self.COLLECTION_NAME,
                metadata={"description": "M-Agent memory store"},
            )

        self.embedder = EmbeddingEngine(model_name=embedding_model)

    def add(
        self,
        memory_type: MemoryType,
        content: str,
        raw_data: dict | None = None,
        tags: list[str] | None = None,
        parent_id: str | None = None,
        importance: float = 0.5,
        tier: MemoryTier = MemoryTier.WARM,
    ) -> Memory:
        """添加一条记忆"""
        mid = str(uuid.uuid4())
        embedding = self.embedder.encode(content)

        memory = Memory(
            id=mid,
            type=memory_type,
            tier=tier,
            content=content,
            raw_data=raw_data,
            embedding=embedding,
            tags=tags or [],
            parent_id=parent_id,
            importance=importance,
        )

        self.collection.add(
            documents=[content],
            embeddings=[embedding],
            metadatas=[{
                "id": mid,
                "type": memory_type.value,
                "tier": tier.value,
                "content": content,
                "raw_data": json.dumps(raw_data) if raw_data else "",
                "tags": json.dumps(tags or []),
                "parent_id": parent_id or "",
                "use_count": 0,
                "importance": importance,
                "created_at": memory.created_at,
                "last_accessed_at": memory.last_accessed_at,
                "last_modified_at": memory.last_modified_at,
            }],
            ids=[mid],
        )

        return memory

    def search(
        self,
        query: str,
        top_k: int = 5,
        memory_type: MemoryType | None = None,
        tier: MemoryTier | None = None,
        tags: list[str] | None = None,
        min_importance: float = 0.0,
    ) -> list[Memory]:
        """语义搜索记忆"""
        query_embedding = self.embedder.encode(query)

        where_filter: dict = {}
        if memory_type:
            where_filter["type"] = memory_type.value
        if tier:
            where_filter["tier"] = tier.value

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k * 3,
            where=where_filter if where_filter else None,
        )

        memories = []
        if not results["ids"]:
            return []

        for i, mid in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i]

            # Filter by tags
            if tags:
                mem_tags = json.loads(meta.get("tags", "[]"))
                if not any(t in mem_tags for t in tags):
                    continue

            # Filter by importance
            if float(meta.get("importance", 0)) < min_importance:
                continue

            memory = Memory(
                id=mid,
                type=MemoryType(meta["type"]),
                tier=MemoryTier(meta["tier"]),
                content=meta["content"],
                raw_data=json.loads(meta["raw_data"]) if meta.get("raw_data") else None,
                tags=json.loads(meta.get("tags", "[]")),
                parent_id=meta.get("parent_id") or None,
                use_count=int(meta.get("use_count", 0)),
                importance=float(meta.get("importance", 0)),
                created_at=float(meta.get("created_at", time.time())),
                last_accessed_at=float(meta.get("last_accessed_at", time.time())),
                last_modified_at=float(meta.get("last_modified_at", time.time())),
            )
            memories.append(memory)

            if len(memories) >= top_k:
                break

        return memories

    def get(self, memory_id: str) -> Memory | None:
        """获取单条记忆"""
        results = self.collection.get(ids=[memory_id])
        if not results["ids"]:
            return None

        meta = results["metadatas"][0]
        return Memory(
            id=memory_id,
            type=MemoryType(meta["type"]),
            tier=MemoryTier(meta["tier"]),
            content=meta["content"],
            raw_data=json.loads(meta["raw_data"]) if meta.get("raw_data") else None,
            tags=json.loads(meta.get("tags", "[]")),
            parent_id=meta.get("parent_id") or None,
            use_count=int(meta.get("use_count", 0)),
            importance=float(meta.get("importance", 0)),
            created_at=float(meta.get("created_at", time.time())),
            last_accessed_at=float(meta.get("last_accessed_at", time.time())),
            last_modified_at=float(meta.get("last_modified_at", time.time())),
        )

    def update_use(self, memory_id: str) -> None:
        """更新访问次数和时间"""
        results = self.collection.get(ids=[memory_id])
        if not results["ids"]:
            return

        meta = results["metadatas"][0]
        self.collection.update(
            ids=[memory_id],
            metadatas=[{
                **meta,
                "use_count": int(meta.get("use_count", 0)) + 1,
                "last_accessed_at": time.time(),
            }],
        )

    def get_reasoning_chain(self, memory_id: str) -> list[Memory]:
        """获取推理链（从当前记忆向上追溯父记忆）"""
        chain = []
        current_id = memory_id

        for _ in range(20):  # 最多20层
            mem = self.get(current_id)
            if not mem:
                break
            chain.append(mem)
            if mem.parent_id:
                current_id = mem.parent_id
            else:
                break

        return list(reversed(chain))

    def query_by_type(
        self,
        memory_type: MemoryType,
        limit: int = 50,
    ) -> list[Memory]:
        """按类型查询所有记忆"""
        results = self.collection.get(
            where={"type": memory_type.value},
            limit=limit,
        )

        memories = []
        for i, mid in enumerate(results["ids"]):
            meta = results["metadatas"][i]
            memories.append(Memory(
                id=mid,
                type=MemoryType(meta["type"]),
                tier=MemoryTier(meta["tier"]),
                content=meta["content"],
                raw_data=json.loads(meta["raw_data"]) if meta.get("raw_data") else None,
                tags=json.loads(meta.get("tags", "[]")),
                parent_id=meta.get("parent_id") or None,
                use_count=int(meta.get("use_count", 0)),
                importance=float(meta.get("importance", 0)),
                created_at=float(meta.get("created_at", time.time())),
                last_accessed_at=float(meta.get("last_accessed_at", time.time())),
                last_modified_at=float(meta.get("last_modified_at", time.time())),
            ))
        return memories

    def tier_stats(self) -> dict:
        """统计各层记忆数量"""
        all_memories = self.collection.get()
        stats = {"hot": 0, "warm": 0, "cold": 0, "total": 0}
        for meta in all_memories["metadatas"]:
            tier = meta.get("tier", "warm")
            if tier in stats:
                stats[tier] += 1
            stats["total"] += 1
        return stats


# ---------------------------------------------------------------------------
# Global Store
# ---------------------------------------------------------------------------

_store: MemoryStore | None = None


def get_memory_store() -> MemoryStore:
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store
