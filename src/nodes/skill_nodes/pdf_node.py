"""
PDF Node - PDF 处理节点

集成 nano-pdf 技能，提供 PDF 处理能力。
"""

import logging
from typing import Any, Dict, List, Optional

from ..base_node import BaseNode, NodeResult, NodeStatus

logger = logging.getLogger(__name__)


class PDFNode(BaseNode):
    """PDF 处理节点"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("pdf", config)
    
    async def execute(self, context: Dict[str, Any]) -> NodeResult:
        """
        执行 PDF 处理
        
        Args:
            context: 执行上下文，包含:
                - operation: 操作类型 (read, merge, split, convert)
                - input_paths: 输入文件路径列表
                - output_path: 输出文件路径
                - pages: 页码范围 (可选)
        
        Returns:
            NodeResult: 处理结果
        """
        try:
            operation = context.get("operation", "read")
            input_paths = context.get("input_paths", [])
            output_path = context.get("output_path")
            pages = context.get("pages")
            
            if not input_paths:
                return NodeResult(
                    status=NodeStatus.FAILED,
                    error="缺少必需参数：input_paths",
                    node_name=self.name
                )
            
            # 调用 PDF 处理技能
            result = await self._process_pdf(
                operation=operation,
                input_paths=input_paths,
                output_path=output_path,
                pages=pages
            )
            
            return NodeResult(
                status=NodeStatus.COMPLETED,
                output=result,
                node_name=self.name
            )
        
        except Exception as e:
            logger.error(f"PDF 处理失败：{e}")
            return NodeResult(
                status=NodeStatus.FAILED,
                error=str(e),
                node_name=self.name
            )
    
    async def _process_pdf(
        self,
        operation: str,
        input_paths: List[str],
        output_path: Optional[str] = None,
        pages: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        处理 PDF
        """
        from pathlib import Path
        
        if operation == "read":
            return await self._read_pdf(input_paths[0])
        elif operation == "merge":
            return await self._merge_pdfs(input_paths, output_path)
        elif operation == "split":
            return await self._split_pdf(input_paths[0], output_path, pages)
        elif operation == "extract_text":
            return await self._extract_text(input_paths[0])
        elif operation == "extract_images":
            return await self._extract_images(input_paths[0], output_path)
        else:
            raise ValueError(f"不支持的操作：{operation}")
    
    async def _read_pdf(self, input_path: str) -> Dict[str, Any]:
        """
        读取 PDF 信息
        """
        from pypdf import PdfReader
        from pathlib import Path
        
        path = Path(input_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF 文件不存在：{input_path}")
        
        reader = PdfReader(str(path))
        
        return {
            "pages": len(reader.pages),
            "metadata": dict(reader.metadata) if reader.metadata else {},
            "is_encrypted": reader.is_encrypted,
            "file_size": path.stat().st_size
        }
    
    async def _merge_pdfs(
        self,
        input_paths: List[str],
        output_path: Optional[str]
    ) -> Dict[str, Any]:
        """
        合并多个 PDF
        """
        from pypdf import PdfWriter, PdfReader
        from pathlib import Path
        
        if not output_path:
            output_path = "merged.pdf"
        
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        writer = PdfWriter()
        merged_files = []
        
        for input_path in input_paths:
            input_file = Path(input_path)
            if not input_file.exists():
                logger.warning(f"文件不存在，跳过：{input_path}")
                continue
            
            reader = PdfReader(str(input_file))
            for page in reader.pages:
                writer.add_page(page)
            
            merged_files.append(str(input_file))
        
        with open(path, "wb") as f:
            writer.write(f)
        
        return {
            "operation": "merge",
            "output_path": str(path),
            "merged_files": merged_files,
            "total_pages": len(writer.pages)
        }
    
    async def _split_pdf(
        self,
        input_path: str,
        output_path: Optional[str],
        pages: Optional[str]
    ) -> Dict[str, Any]:
        """
        分割 PDF
        """
        from pypdf import PdfReader, PdfWriter
        from pathlib import Path
        
        path = Path(input_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF 文件不存在：{input_path}")
        
        reader = PdfReader(str(path))
        
        # 解析页码范围
        if pages:
            page_ranges = self._parse_page_ranges(pages, len(reader.pages))
        else:
            # 默认每页一个文件
            page_ranges = [[i] for i in range(len(reader.pages))]
        
        output_files = []
        
        for i, page_nums in enumerate(page_ranges):
            writer = PdfWriter()
            for page_num in page_nums:
                writer.add_page(reader.pages[page_num])
            
            if output_path:
                out_path = Path(output_path)
                file_name = f"{out_path.stem}_{i+1}{out_path.suffix}"
                split_path = out_path.parent / file_name
            else:
                split_path = path.parent / f"{path.stem}_{i+1}.pdf"
            
            with open(split_path, "wb") as f:
                writer.write(f)
            
            output_files.append(str(split_path))
        
        return {
            "operation": "split",
            "output_paths": output_files,
            "total_splits": len(output_files)
        }
    
    async def _extract_text(self, input_path: str) -> Dict[str, Any]:
        """
        提取 PDF 文本
        """
        from pypdf import PdfReader
        from pathlib import Path
        
        path = Path(input_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF 文件不存在：{input_path}")
        
        reader = PdfReader(str(path))
        
        text_by_page = []
        full_text = []
        
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            text_by_page.append({
                "page": i + 1,
                "text": text
            })
            full_text.append(text)
        
        return {
            "operation": "extract_text",
            "total_pages": len(reader.pages),
            "text_by_page": text_by_page,
            "full_text": "\n".join(full_text)
        }
    
    async def _extract_images(
        self,
        input_path: str,
        output_path: Optional[str]
    ) -> Dict[str, Any]:
        """
        提取 PDF 中的图片
        """
        from pypdf import PdfReader
        from pathlib import Path
        
        path = Path(input_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF 文件不存在：{input_path}")
        
        if not output_path:
            output_path = str(path.parent / "extracted_images")
        
        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        reader = PdfReader(str(path))
        extracted_images = []
        
        for i, page in enumerate(reader.pages):
            images = page.images
            for j, image in enumerate(images):
                img_path = output_dir / f"page_{i+1}_img_{j+1}.{image.name.split('.')[-1] or 'png'}"
                
                with open(img_path, "wb") as f:
                    f.write(image.data)
                
                extracted_images.append(str(img_path))
        
        return {
            "operation": "extract_images",
            "output_dir": str(output_dir),
            "extracted_images": extracted_images,
            "total_images": len(extracted_images)
        }
    
    def _parse_page_ranges(self, pages: str, total_pages: int) -> List[List[int]]:
        """
        解析页码范围字符串
        
        支持格式：
        - "1-5" : 第 1 到 5 页
        - "1,3,5" : 第 1, 3, 5 页
        - "1-3,5,7-9" : 组合
        """
        result = []
        
        for part in pages.split(","):
            part = part.strip()
            if "-" in part:
                start, end = part.split("-")
                start = max(0, int(start) - 1)
                end = min(total_pages, int(end))
                result.append(list(range(start, end)))
            else:
                page = int(part) - 1
                if 0 <= page < total_pages:
                    result.append([page])
        
        return result
    
    def get_schema(self) -> Dict[str, Any]:
        """返回节点输入输出 schema"""
        return {
            "inputs": {
                "operation": {
                    "type": "string",
                    "required": False,
                    "default": "read",
                    "enum": ["read", "merge", "split", "extract_text", "extract_images"]
                },
                "input_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "required": True,
                    "description": "输入文件路径列表"
                },
                "output_path": {"type": "string", "required": False, "description": "输出文件路径"},
                "pages": {
                    "type": "string",
                    "required": False,
                    "description": "页码范围 (如：1-5, 1,3,5)"
                }
            },
            "outputs": {
                "pdf_result": {"type": "object", "description": "PDF 处理结果"}
            }
        }
