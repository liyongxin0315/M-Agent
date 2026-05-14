"""
AgentM RAG 知识库管理工具

用于导入、管理、查询 RAG 知识库
支持从文件、目录、URL 导入文档
"""

import asyncio
import hashlib
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.rag_engine import RAGEngine, RAGConfig, Document
from config.config import get_rag_config

logger = logging.getLogger(__name__)


class KnowledgeBaseManager:
    """
    知识库管理器
    
    提供知识库的导入、查询、管理功能
    """
    
    def __init__(self, config: Optional[RAGConfig] = None):
        self.config = config or get_rag_config()
        self.engine: Optional[RAGEngine] = None
    
    async def initialize(self) -> 'KnowledgeBaseManager':
        """初始化 RAG 引擎"""
        self.engine = RAGEngine(self.config)
        self.engine.initialize()  # 同步方法
        logger.info("RAG 引擎已初始化")
        return self
    
    async def close(self) -> None:
        """关闭 RAG 引擎"""
        if self.engine:
            # RAG 引擎无 close 方法
            logger.info("RAG 引擎已关闭")
    
    async def import_file(
        self,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None
    ) -> List[str]:
        """
        导入单个文件到知识库
        
        Args:
            file_path: 文件路径
            metadata: 元数据
            chunk_size: 分块大小
            chunk_overlap: 分块重叠
        
        Returns:
            文档 ID 列表
        """
        if not self.engine:
            raise RuntimeError("RAG 引擎未初始化")
        
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在：{file_path}")
        
        # 读取文件
        content = path.read_text(encoding='utf-8')
        
        # 创建文档
        doc = Document.from_text(
            content,
            metadata={
                **(metadata or {}),
                'source': str(path),
                'source_type': 'file',
                'file_name': path.name,
                'imported_at': datetime.now().isoformat()
            }
        )
        
        # 添加到引擎（同步方法）
        doc_ids = self.engine.add_documents([doc])
        
        logger.info(f"导入文件：{file_path}, 文档 ID: {doc_ids}")
        return doc_ids
    
    async def import_directory(
        self,
        dir_path: str,
        pattern: str = "*.md",
        recursive: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        导入目录到知识库
        
        Args:
            dir_path: 目录路径
            pattern: 文件匹配模式
            recursive: 是否递归子目录
            metadata: 元数据
        
        Returns:
            文档 ID 列表
        """
        if not self.engine:
            raise RuntimeError("RAG 引擎未初始化")
        
        path = Path(dir_path)
        if not path.is_dir():
            raise NotADirectoryError(f"目录不存在：{dir_path}")
        
        # 查找文件
        if recursive:
            files = list(path.rglob(pattern))
        else:
            files = list(path.glob(pattern))
        
        logger.info(f"找到 {len(files)} 个文件")
        
        # 导入所有文件
        all_doc_ids = []
        for file_path in files:
            try:
                doc_ids = await self.import_file(
                    str(file_path),
                    metadata={
                        **(metadata or {}),
                        'directory': dir_path
                    }
                )
                all_doc_ids.extend(doc_ids)
            except Exception as e:
                logger.error(f"导入文件失败 {file_path}: {e}")
        
        return all_doc_ids
    
    async def import_text(
        self,
        text: str,
        title: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        导入文本到知识库
        
        Args:
            text: 文本内容
            title: 标题
            metadata: 元数据
        
        Returns:
            文档 ID 列表
        """
        if not self.engine:
            raise RuntimeError("RAG 引擎未初始化")
        
        doc = Document.from_text(
            text,
            metadata={
                **(metadata or {}),
                'title': title,
                'source_type': 'text',
                'imported_at': datetime.now().isoformat()
            }
        )
        
        doc_ids = self.engine.add_documents([doc])
        logger.info(f"导入文本：{title}, 文档 ID: {doc_ids}")
        return doc_ids
    
    async def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        搜索知识库
        
        Args:
            query: 查询文本
            top_k: 返回数量
            filter_metadata: 元数据过滤
        
        Returns:
            检索结果列表
        """
        if not self.engine:
            raise RuntimeError("RAG 引擎未初始化")
        
        # retrieve 是同步方法
        results = self.engine.retrieve(
            query,
            top_k=top_k,
            filter_metadata=filter_metadata
        )
        
        return [r.to_dict() for r in results]
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取知识库统计信息"""
        if not self.engine:
            raise RuntimeError("RAG 引擎未初始化")
        
        try:
            # 获取集合统计（同步方法）
            collection = self.engine._collection
            count = collection.count()
            
            return {
                'total_documents': count,
                'persist_directory': self.config.persist_directory,
                'embedding_model': self.config.embedding_model,
                'collection_name': self.config.collection_name,
                'top_k': self.config.top_k
            }
        except Exception as e:
            return {
                'error': str(e),
                'persist_directory': self.config.persist_directory
            }
    
    async def clear(self) -> None:
        """清空知识库"""
        if not self.engine:
            raise RuntimeError("RAG 引擎未初始化")
        
        self.engine.delete_all()
        logger.info("知识库已清空")


async def main():
    """命令行工具入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='AgentM 知识库管理工具')
    parser.add_argument('command', choices=['import', 'search', 'stats', 'clear'],
                       help='命令：导入/搜索/统计/清空')
    parser.add_argument('--input', '-i', help='输入文件/目录路径')
    parser.add_argument('--query', '-q', help='搜索查询')
    parser.add_argument('--top-k', '-k', type=int, default=5, help='返回数量')
    parser.add_argument('--pattern', '-p', default='*.md', help='文件匹配模式')
    parser.add_argument('--recursive', '-r', action='store_true', help='递归子目录')
    
    args = parser.parse_args()
    
    # 初始化
    kb = KnowledgeBaseManager()
    await kb.initialize()
    
    try:
        if args.command == 'import':
            if not args.input:
                print("错误：请指定输入路径 --input")
                return
            
            path = Path(args.input)
            if path.is_file():
                doc_ids = await kb.import_file(args.input)
                print(f"导入文件完成，文档 ID: {doc_ids}")
            elif path.is_dir():
                doc_ids = await kb.import_directory(
                    args.input,
                    pattern=args.pattern,
                    recursive=args.recursive
                )
                print(f"导入目录完成，共 {len(doc_ids)} 个文档")
            else:
                print(f"错误：路径不存在 {args.input}")
        
        elif args.command == 'search':
            if not args.query:
                print("错误：请指定查询 --query")
                return
            
            results = await kb.search(args.query, top_k=args.top_k)
            print(f"\n搜索结果 ({len(results)} 条):\n")
            for i, result in enumerate(results, 1):
                print(f"[{i}] 分数：{result['score']:.4f}")
                print(f"    内容：{result['content'][:200]}...")
                print(f"    元数据：{result['metadata']}\n")
        
        elif args.command == 'stats':
            stats = await kb.get_stats()
            print("\n知识库统计:\n")
            for key, value in stats.items():
                print(f"  {key}: {value}")
        
        elif args.command == 'clear':
            confirm = input("确定要清空知识库吗？(yes/no): ")
            if confirm.lower() == 'yes':
                await kb.clear()
                print("知识库已清空")
            else:
                print("操作已取消")
    
    finally:
        await kb.close()


if __name__ == '__main__':
    asyncio.run(main())
