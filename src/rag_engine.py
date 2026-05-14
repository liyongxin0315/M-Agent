"""
AgentM RAG Engine - 检索增强生成引擎

提供向量数据库集成、语义检索、检索结果重排序功能

特性:
- ChromaDB 向量存储
- Sentence-Transformers 语义嵌入
- BM25 + 向量混合检索
- Rerank 重排序
- 与工作流引擎集成
"""

import asyncio
import hashlib
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# 延迟导入重型依赖
_chromadb = None
_sentence_transformers = None
_rank_bm25 = None
_np = None


def _get_chromadb():
    """懒加载 ChromaDB"""
    global _chromadb
    if _chromadb is None:
        import chromadb
        _chromadb = chromadb
    return _chromadb


def _get_sentence_transformers():
    """懒加载 Sentence-Transformers"""
    global _sentence_transformers
    if _sentence_transformers is None:
        from sentence_transformers import SentenceTransformer
        _sentence_transformers = SentenceTransformer
    return _sentence_transformers


def _get_rank_bm25():
    """懒加载 Rank-BM25"""
    global _rank_bm25
    if _rank_bm25 is None:
        import rank_bm25
        _rank_bm25 = rank_bm25
    return _rank_bm25


def _get_numpy():
    """懒加载 NumPy"""
    global _np
    if _np is None:
        import numpy as np
        _np = np
    return _np


class RerankStrategy(Enum):
    """重排序策略"""
    NONE = "none"
    BM25 = "bm25"
    RECIPROCAL_RANK = "reciprocal_rank"
    HYBRID = "hybrid"


@dataclass
class Document:
    """文档对象"""
    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    @classmethod
    def from_text(cls, text: str, metadata: Optional[Dict] = None) -> "Document":
        """从文本创建文档"""
        doc_id = hashlib.md5(text.encode()).hexdigest()[:16]
        return cls(
            id=doc_id,
            content=text,
            metadata=metadata or {}
        )


@dataclass
class RetrievalResult:
    """检索结果"""
    document: Document
    score: float
    rank: int
    strategy: str = "vector"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.document.id,
            "content": self.document.content[:200],
            "metadata": self.document.metadata,
            "score": round(self.score, 4),
            "rank": self.rank,
            "strategy": self.strategy
        }


@dataclass
class RAGConfig:
    """RAG 配置"""
    persist_directory: str = "./agentm_data/rag_db"
    embedding_model: str = "all-MiniLM-L6-v2"
    collection_name: str = "agentm_knowledge"
    top_k: int = 5
    rerank_strategy: RerankStrategy = RerankStrategy.HYBRID
    bm25_k1: float = 1.5
    bm25_b: float = 0.75
    hybrid_alpha: float = 0.5  # 向量权重，1-alpha 为 BM25 权重
    max_content_length: int = 4000
    chunk_size: int = 500
    chunk_overlap: int = 50
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "persist_directory": self.persist_directory,
            "embedding_model": self.embedding_model,
            "collection_name": self.collection_name,
            "top_k": self.top_k,
            "rerank_strategy": self.rerank_strategy.value,
            "bm25_k1": self.bm25_k1,
            "bm25_b": self.bm25_b,
            "hybrid_alpha": self.hybrid_alpha,
            "max_content_length": self.max_content_length,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap
        }


class TextChunker:
    """文本分块器"""
    
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def chunk(self, text: str) -> List[str]:
        """将文本分块"""
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]
            
            # 尝试在句子边界处切分
            if end < len(text):
                for sep in ['. ', '! ', '? ', '\n', '。', '！', '？']:
                    last_sep = chunk.rfind(sep)
                    if last_sep > self.chunk_size // 2:
                        chunk = text[start:start + last_sep + len(sep)]
                        break
            
            chunks.append(chunk.strip())
            start = end - self.chunk_overlap
        
        return chunks


class EmbeddingModel:
    """嵌入模型封装"""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
    
    @property
    def model(self):
        """懒加载模型"""
        if self._model is None:
            SentenceTransformer = _get_sentence_transformers()
            logger.info(f"加载嵌入模型：{self.model_name}")
            self._model = SentenceTransformer(self.model_name)
        return self._model
    
    def encode(self, texts: Union[str, List[str]], **kwargs) -> Any:
        """生成嵌入向量"""
        if isinstance(texts, str):
            texts = [texts]
        
        np = _get_numpy()
        embeddings = self.model.encode(texts, **kwargs)
        
        # 确保返回 list
        if isinstance(embeddings, np.ndarray):
            return embeddings.tolist()
        return embeddings
    
    def encode_query(self, query: str) -> List[float]:
        """编码查询"""
        result = self.encode([query], convert_to_numpy=True)
        return result[0] if isinstance(result, list) and len(result) > 0 else result
    
    def encode_documents(self, documents: List[str]) -> List[List[float]]:
        """编码文档列表"""
        return self.encode(documents, convert_to_numpy=True)


class RAGEngine:
    """
    RAG 引擎
    
    功能:
    - 文档入库（自动分块 + 嵌入）
    - 语义检索（向量 + BM25 混合）
    - 结果重排序
    - 与工作流集成
    """
    
    def __init__(self, config: Optional[RAGConfig] = None):
        self.config = config or RAGConfig()
        self._client = None
        self._collection = None
        self._embedding_model = None
        self._bm25_index = None
        self._documents: Dict[str, Document] = {}
        self._initialized = False
    
    def _ensure_initialized(self) -> None:
        """确保引擎已初始化"""
        if not self._initialized:
            self.initialize()
    
    def initialize(self) -> None:
        """初始化 RAG 引擎"""
        if self._initialized:
            logger.info("RAG 引擎已初始化，跳过")
            return
        
        logger.info("初始化 RAG 引擎...")
        
        # 创建 ChromaDB 客户端
        chromadb = _get_chromadb()
        
        # 设置持久化目录
        persist_dir = Path(self.config.persist_directory)
        persist_dir.mkdir(parents=True, exist_ok=True)
        
        self._client = chromadb.PersistentClient(path=str(persist_dir))
        
        # 获取或创建集合
        self._collection = self._client.get_or_create_collection(
            name=self.config.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        
        # 初始化嵌入模型
        self._embedding_model = EmbeddingModel(self.config.embedding_model)
        
        # 加载已有文档到内存
        self._load_documents()
        
        self._initialized = True
        logger.info(f"RAG 引擎初始化完成，集合：{self.config.collection_name}")
    
    def _load_documents(self) -> None:
        """从 ChromaDB 加载已有文档"""
        try:
            if self._collection.count() == 0:
                return
            
            # 获取所有文档
            all_docs = self._collection.get(
                include=["documents", "metadatas", "embeddings"]
            )
            
            for i, doc_id in enumerate(all_docs["ids"]):
                self._documents[doc_id] = Document(
                    id=doc_id,
                    content=all_docs["documents"][i],
                    metadata=all_docs["metadatas"][i] or {},
                    embedding=all_docs["embeddings"][i] if all_docs.get("embeddings") else None
                )
            
            logger.info(f"加载了 {len(self._documents)} 个文档")
            
            # 构建 BM25 索引
            self._build_bm25_index()
            
        except Exception as e:
            logger.error(f"加载文档失败：{e}")
    
    def _build_bm25_index(self) -> None:
        """构建 BM25 索引"""
        if not self._documents:
            return
        
        rank_bm25 = _get_rank_bm25()
        
        # 分词
        tokenized_docs = [
            self._tokenize(doc.content)
            for doc in self._documents.values()
        ]
        
        self._bm25_index = rank_bm25.BM25Okapi(
            tokenized_docs,
            k1=self.config.bm25_k1,
            b=self.config.bm25_b
        )
        
        logger.info(f"BM25 索引构建完成，文档数：{len(tokenized_docs)}")
    
    def _tokenize(self, text: str) -> List[str]:
        """简单分词"""
        # 中文按字符，英文按空格
        import re
        # 提取中英文词汇
        tokens = re.findall(r'[\w\u4e00-\u9fff]+', text.lower())
        return tokens
    
    def add_document(
        self,
        text: str,
        metadata: Optional[Dict] = None,
        chunk: bool = True
    ) -> List[str]:
        """
        添加文档
        
        Args:
            text: 文档内容
            metadata: 元数据
            chunk: 是否自动分块
        
        Returns:
            文档 ID 列表
        """
        self._ensure_initialized()
        
        metadata = metadata or {}
        doc_ids = []
        
        if chunk and len(text) > self.config.chunk_size:
            # 自动分块
            chunker = TextChunker(
                self.config.chunk_size,
                self.config.chunk_overlap
            )
            chunks = chunker.chunk(text)
            
            for i, chunk_text in enumerate(chunks):
                chunk_metadata = {
                    **metadata,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "is_chunk": True
                }
                doc_id = self._add_single_document(
                    chunk_text,
                    chunk_metadata
                )
                doc_ids.append(doc_id)
        else:
            doc_id = self._add_single_document(text, metadata)
            doc_ids.append(doc_id)
        
        logger.info(f"添加了 {len(doc_ids)} 个文档块")
        return doc_ids
    
    def _add_single_document(
        self,
        text: str,
        metadata: Dict
    ) -> str:
        """添加单个文档"""
        # 限制长度
        if len(text) > self.config.max_content_length:
            text = text[:self.config.max_content_length]
        
        # 生成 ID
        doc_id = hashlib.md5(
            f"{text}:{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]
        
        # 生成嵌入
        embedding = self._embedding_model.encode_query(text)
        
        # 存入 ChromaDB
        self._collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[metadata]
        )
        
        # 存入内存
        self._documents[doc_id] = Document(
            id=doc_id,
            content=text,
            metadata=metadata,
            embedding=embedding
        )
        
        # 重建 BM25 索引
        self._build_bm25_index()
        
        return doc_id
    
    def add_documents(
        self,
        documents: List[Union[str, Document]],
        chunk: bool = True
    ) -> List[str]:
        """批量添加文档"""
        all_ids = []
        
        for doc in documents:
            if isinstance(doc, Document):
                ids = self.add_document(
                    doc.content,
                    doc.metadata,
                    chunk=chunk
                )
            else:
                ids = self.add_document(doc, chunk=chunk)
            
            all_ids.extend(ids)
        
        return all_ids
    
    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        rerank_strategy: Optional[RerankStrategy] = None,
        filter_metadata: Optional[Dict] = None
    ) -> List[RetrievalResult]:
        """
        检索文档
        
        Args:
            query: 查询文本
            top_k: 返回数量
            rerank_strategy: 重排序策略
            filter_metadata: 元数据过滤
        
        Returns:
            检索结果列表
        """
        self._ensure_initialized()
        
        top_k = top_k or self.config.top_k
        strategy = rerank_strategy or self.config.rerank_strategy
        
        logger.info(f"检索查询：{query[:50]}..., top_k={top_k}")
        
        # 向量检索
        vector_results = self._vector_search(query, top_k * 2, filter_metadata)
        
        # 根据策略进行重排序
        if strategy == RerankStrategy.NONE:
            results = vector_results[:top_k]
        elif strategy == RerankStrategy.BM25:
            bm25_results = self._bm25_search(query, top_k * 2)
            results = self._reciprocal_rank_fusion(
                vector_results,
                bm25_results,
                top_k
            )
        elif strategy == RerankStrategy.RECIPROCAL_RANK:
            bm25_results = self._bm25_search(query, top_k * 2)
            results = self._reciprocal_rank_fusion(
                vector_results,
                bm25_results,
                top_k,
                weights=(0.5, 0.5)
            )
        elif strategy == RerankStrategy.HYBRID:
            bm25_results = self._bm25_search(query, top_k * 2)
            results = self._hybrid_rank(
                vector_results,
                bm25_results,
                top_k,
                alpha=self.config.hybrid_alpha
            )
        else:
            results = vector_results[:top_k]
        
        # 设置排名
        for i, result in enumerate(results):
            result.rank = i + 1
        
        logger.info(f"检索完成，返回 {len(results)} 个结果")
        return results
    
    def _vector_search(
        self,
        query: str,
        top_k: int,
        filter_metadata: Optional[Dict] = None
    ) -> List[RetrievalResult]:
        """向量检索"""
        query_embedding = self._embedding_model.encode_query(query)
        
        where = filter_metadata if filter_metadata else None
        
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"]
        )
        
        retrieval_results = []
        
        if results and results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                doc = self._documents.get(doc_id)
                if not doc:
                    doc = Document(
                        id=doc_id,
                        content=results["documents"][0][i],
                        metadata=results["metadatas"][0][i] or {}
                    )
                
                # 距离转相似度（余弦距离）
                distance = results["distances"][0][i] if results.get("distances") else 0
                similarity = 1 - distance
                
                retrieval_results.append(RetrievalResult(
                    document=doc,
                    score=similarity,
                    rank=0,
                    strategy="vector"
                ))
        
        return retrieval_results
    
    def _bm25_search(
        self,
        query: str,
        top_k: int
    ) -> List[RetrievalResult]:
        """BM25 检索"""
        if not self._bm25_index or not self._documents:
            return []
        
        rank_bm25 = _get_rank_bm25()
        
        query_tokens = self._tokenize(query)
        
        # BM25 评分
        doc_ids = list(self._documents.keys())
        scores = self._bm25_index.get_scores(query_tokens)
        
        # 排序
        scored_docs = sorted(
            zip(doc_ids, scores),
            key=lambda x: x[1],
            reverse=True
        )[:top_k]
        
        retrieval_results = []
        for doc_id, score in scored_docs:
            doc = self._documents[doc_id]
            retrieval_results.append(RetrievalResult(
                document=doc,
                score=score,
                rank=0,
                strategy="bm25"
            ))
        
        return retrieval_results
    
    def _reciprocal_rank_fusion(
        self,
        results1: List[RetrievalResult],
        results2: List[RetrievalResult],
        top_k: int,
        weights: Tuple[float, float] = (0.5, 0.5)
    ) -> List[RetrievalResult]:
        """倒数排名融合"""
        # 构建排名映射
        rank_map1 = {r.document.id: len(results1) - i for i, r in enumerate(results1)}
        rank_map2 = {r.document.id: len(results2) - i for i, r in enumerate(results2)}
        
        # 合并文档
        all_docs = {}
        for r in results1:
            all_docs[r.document.id] = r
        for r in results2:
            if r.document.id not in all_docs:
                all_docs[r.document.id] = r
        
        # 计算融合分数
        fused_results = []
        for doc_id, doc in all_docs.items():
            rank1 = rank_map1.get(doc_id, 0)
            rank2 = rank_map2.get(doc_id, 0)
            
            # 倒数排名融合公式
            score = (
                weights[0] * rank1 / len(results1) +
                weights[1] * rank2 / len(results2)
            )
            
            fused_results.append(RetrievalResult(
                document=doc,
                score=score,
                rank=0,
                strategy="reciprocal_rank"
            ))
        
        # 排序
        fused_results.sort(key=lambda x: x.score, reverse=True)
        
        return fused_results[:top_k]
    
    def _hybrid_rank(
        self,
        vector_results: List[RetrievalResult],
        bm25_results: List[RetrievalResult],
        top_k: int,
        alpha: float = 0.5
    ) -> List[RetrievalResult]:
        """混合排序"""
        # 归一化分数
        def normalize(results: List[RetrievalResult]) -> Dict[str, float]:
            if not results:
                return {}
            
            scores = [r.score for r in results]
            min_score = min(scores)
            max_score = max(scores)
            range_score = max_score - min_score if max_score > min_score else 1
            
            return {
                r.document.id: (r.score - min_score) / range_score
                for r in results
            }
        
        vector_scores = normalize(vector_results)
        bm25_scores = normalize(bm25_results)
        
        # 合并
        all_doc_ids = set(vector_scores.keys()) | set(bm25_scores.keys())
        
        hybrid_results = []
        for doc_id in all_doc_ids:
            v_score = vector_scores.get(doc_id, 0)
            b_score = bm25_scores.get(doc_id, 0)
            
            hybrid_score = alpha * v_score + (1 - alpha) * b_score
            
            doc = (
                next((r.document for r in vector_results if r.document.id == doc_id), None) or
                next((r.document for r in bm25_results if r.document.id == doc_id), None)
            )
            
            if doc:
                hybrid_results.append(RetrievalResult(
                    document=doc,
                    score=hybrid_score,
                    rank=0,
                    strategy="hybrid"
                ))
        
        # 排序
        hybrid_results.sort(key=lambda x: x.score, reverse=True)
        
        return hybrid_results[:top_k]
    
    def delete_document(self, doc_id: str) -> bool:
        """删除文档"""
        self._ensure_initialized()
        
        try:
            self._collection.delete(ids=[doc_id])
            del self._documents[doc_id]
            
            # 重建 BM25 索引
            self._build_bm25_index()
            
            logger.info(f"删除文档：{doc_id}")
            return True
        except Exception as e:
            logger.error(f"删除文档失败：{e}")
            return False
    
    def clear(self) -> None:
        """清空所有文档"""
        self._ensure_initialized()
        
        # 删除并重建集合
        self._client.delete_collection(self.config.collection_name)
        self._collection = self._client.create_collection(
            name=self.config.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        
        self._documents.clear()
        self._bm25_index = None
        
        logger.info("已清空所有文档")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        self._ensure_initialized()
        
        return {
            "collection_name": self.config.collection_name,
            "document_count": len(self._documents),
            "embedding_model": self.config.embedding_model,
            "top_k": self.config.top_k,
            "rerank_strategy": self.config.rerank_strategy.value,
            "persist_directory": self.config.persist_directory,
            "bm25_indexed": self._bm25_index is not None
        }
    
    def to_workflow_step(self) -> Callable:
        """转换为工作流步骤"""
        async def rag_search_step(context: Dict) -> List[Dict]:
            query = context.get("query", "")
            top_k = context.get("top_k", self.config.top_k)
            
            if not query:
                raise ValueError("查询不能为空")
            
            results = self.search(query, top_k=top_k)
            
            context["rag_results"] = [r.to_dict() for r in results]
            context["rag_context"] = "\n\n".join([
                f"[{i+1}] {r.document.content}"
                for i, r in enumerate(results)
            ])
            
            return context["rag_results"]
        
        return rag_search_step


# ============ 工作流集成 ============

class RAGWorkflow:
    """RAG 工作流"""
    
    def __init__(self, config: Optional[RAGConfig] = None):
        self.engine = RAGEngine(config)
    
    async def ingest_documents(
        self,
        documents: List[Union[str, Document]],
        chunk: bool = True
    ) -> Dict[str, Any]:
        """文档入库工作流"""
        logger.info("开始文档入库工作流")
        
        doc_ids = self.engine.add_documents(documents, chunk=chunk)
        
        return {
            "status": "success",
            "ingested_count": len(doc_ids),
            "document_ids": doc_ids,
            "stats": self.engine.get_stats()
        }
    
    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        rerank_strategy: Optional[RerankStrategy] = None
    ) -> Dict[str, Any]:
        """检索工作流"""
        logger.info(f"开始检索工作流：{query[:50]}...")
        
        results = self.engine.search(query, top_k=top_k, rerank_strategy=rerank_strategy)
        
        return {
            "status": "success",
            "query": query,
            "results": [r.to_dict() for r in results],
            "result_count": len(results),
            "context": "\n\n".join([
                f"[来源 {i+1}] {r.document.content}"
                for i, r in enumerate(results)
            ])
        }
    
    async def query_with_context(
        self,
        query: str,
        top_k: int = 5,
        llm_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """带上下文的查询工作流"""
        logger.info("开始 RAG 查询工作流")
        
        # 检索
        retrieval_result = await self.retrieve(query, top_k=top_k)
        context = retrieval_result["context"]
        
        # 调用 LLM
        if llm_callback:
            augmented_query = f"""基于以下上下文回答问题：

{context}

问题：{query}

请基于上下文提供准确的回答。如果上下文中没有相关信息，请说明。"""
            
            response = await llm_callback(augmented_query)
            retrieval_result["llm_response"] = response
        
        return retrieval_result


# ============ 主程序 ============

async def main():
    """测试 RAG 引擎"""
    logging.basicConfig(level=logging.INFO)
    
    # 创建引擎
    config = RAGConfig(
        persist_directory="./agentm_data/rag_db_test",
        top_k=3,
        rerank_strategy=RerankStrategy.HYBRID
    )
    
    engine = RAGEngine(config)
    engine.initialize()
    
    # 添加测试文档
    test_docs = [
        "Python 是一种高级编程语言，由 Guido van Rossum 于 1989 年发明。",
        "机器学习是人工智能的一个分支，它使计算机能够从数据中学习。",
        "深度学习使用神经网络来模拟人脑的工作方式。",
        "自然语言处理 (NLP) 让计算机理解和生成人类语言。",
        "向量数据库专门用于存储和检索高维向量数据。"
    ]
    
    doc_ids = engine.add_documents(test_docs)
    print(f"\n添加了 {len(doc_ids)} 个文档")
    
    # 测试检索
    query = "什么是机器学习？"
    print(f"\n查询：{query}")
    
    results = engine.search(query, top_k=3)
    
    print("\n检索结果:")
    for i, result in enumerate(results, 1):
        print(f"\n[{i}] 分数：{result.score:.4f}, 策略：{result.strategy}")
        print(f"内容：{result.document.content[:100]}...")
    
    # 统计信息
    print("\n统计信息:")
    stats = engine.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print("\nRAG 引擎测试完成")


if __name__ == "__main__":
    asyncio.run(main())
