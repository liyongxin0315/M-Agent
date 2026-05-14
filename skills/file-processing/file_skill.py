"""
File Processing Skill - 文件处理模块

支持 CSV、Excel、PDF 文件的读写和处理
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class FileError(Exception):
    """文件操作异常"""
    def __init__(self, message: str, operation: str = "", file_path: str = ""):
        self.operation = operation
        self.file_path = file_path
        super().__init__(f"[{operation}] {message} - {file_path}")


@dataclass
class FileConfig:
    """文件配置"""
    encoding: str = "utf-8"
    delimiter: str = ","
    sheet_name: Optional[str] = None
    header_row: int = 0


class CSVHandler:
    """CSV 文件处理器"""
    
    def __init__(self, config: Optional[FileConfig] = None):
        self.config = config or FileConfig()
        self._import_dependencies()
    
    def _import_dependencies(self) -> None:
        """延迟导入依赖"""
        try:
            import csv
            self._csv = csv
        except ImportError as e:
            raise FileError(f"缺少依赖 csv: {e}", "import")
    
    def read(self, file_path: str) -> List[Dict[str, Any]]:
        """读取 CSV 文件"""
        try:
            path = Path(file_path)
            if not path.exists():
                raise FileError("文件不存在", "read", file_path)
            
            with open(path, "r", encoding=self.config.encoding, newline="") as f:
                reader = self._csv.DictReader(f, delimiter=self.config.delimiter)
                return list(reader)
        except Exception as e:
            raise FileError(str(e), "read", file_path)
    
    def write(self, file_path: str, data: List[Dict[str, Any]], fieldnames: Optional[List[str]] = None) -> int:
        """写入 CSV 文件"""
        try:
            if not data:
                logger.warning("数据为空，跳过写入")
                return 0
            
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            if fieldnames is None:
                fieldnames = list(data[0].keys())
            
            with open(path, "w", encoding=self.config.encoding, newline="") as f:
                writer = self._csv.DictWriter(f, fieldnames=fieldnames, delimiter=self.config.delimiter)
                writer.writeheader()
                writer.writerows(data)
            
            logger.info(f"CSV 文件写入成功：{file_path} ({len(data)} 行)")
            return len(data)
        except Exception as e:
            raise FileError(str(e), "write", file_path)
    
    def append(self, file_path: str, data: List[Dict[str, Any]]) -> int:
        """追加数据到 CSV 文件"""
        try:
            if not data:
                return 0
            
            path = Path(file_path)
            file_exists = path.exists()
            
            with open(path, "a", encoding=self.config.encoding, newline="") as f:
                if file_exists:
                    reader = self._csv.DictReader(f, delimiter=self.config.delimiter)
                    fieldnames = reader.fieldnames
                    f.seek(0, 2)  # 移动到文件末尾
                else:
                    fieldnames = list(data[0].keys())
                
                writer = self._csv.DictWriter(f, fieldnames=fieldnames, delimiter=self.config.delimiter)
                if not file_exists:
                    writer.writeheader()
                writer.writerows(data)
            
            logger.info(f"CSV 数据追加成功：{file_path} ({len(data)} 行)")
            return len(data)
        except Exception as e:
            raise FileError(str(e), "append", file_path)


class ExcelHandler:
    """Excel 文件处理器"""
    
    def __init__(self, config: Optional[FileConfig] = None):
        self.config = config or FileConfig()
        self._import_dependencies()
    
    def _import_dependencies(self) -> None:
        """延迟导入依赖"""
        try:
            import pandas as pd
            self._pd = pd
        except ImportError as e:
            raise FileError(f"缺少依赖 pandas: {e}", "import")
    
    def read(self, file_path: str, sheet_name: Optional[str] = None) -> Union[Dict[str, List[Dict]], List[Dict]]:
        """读取 Excel 文件"""
        try:
            path = Path(file_path)
            if not path.exists():
                raise FileError("文件不存在", "read", file_path)
            
            df_dict = self._pd.read_excel(
                path,
                sheet_name=sheet_name or self.config.sheet_name or 0,
                header=self.config.header_row
            )
            
            # 如果指定了 sheet 名称，返回单个 sheet 的数据
            if sheet_name or self.config.sheet_name:
                return df_dict.to_dict(orient="records")
            
            # 否则返回所有 sheet
            if isinstance(df_dict, dict):
                return {name: df.to_dict(orient="records") for name, df in df_dict.items()}
            return df_dict.to_dict(orient="records")
        except Exception as e:
            raise FileError(str(e), "read", file_path)
    
    def write(self, file_path: str, data: List[Dict[str, Any]], sheet_name: str = "Sheet1") -> int:
        """写入 Excel 文件"""
        try:
            if not data:
                logger.warning("数据为空，跳过写入")
                return 0
            
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            df = self._pd.DataFrame(data)
            
            with self._pd.ExcelWriter(path, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name=sheet_name, index=False)
            
            logger.info(f"Excel 文件写入成功：{file_path} ({len(data)} 行)")
            return len(data)
        except Exception as e:
            raise FileError(str(e), "write", file_path)
    
    def write_multiple_sheets(
        self,
        file_path: str,
        data_dict: Dict[str, List[Dict[str, Any]]]
    ) -> int:
        """写入多 sheet 的 Excel 文件"""
        try:
            if not data_dict:
                return 0
            
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            total_rows = 0
            with self._pd.ExcelWriter(path, engine="openpyxl") as writer:
                for sheet_name, data in data_dict.items():
                    if data:
                        df = self._pd.DataFrame(data)
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
                        total_rows += len(df)
            
            logger.info(f"Excel 文件写入成功：{file_path} ({len(data_dict)} sheets, {total_rows} 行)")
            return total_rows
        except Exception as e:
            raise FileError(str(e), "write_multiple_sheets", file_path)


class PDFHandler:
    """PDF 文件处理器"""
    
    def __init__(self):
        self._import_dependencies()
    
    def _import_dependencies(self) -> None:
        """延迟导入依赖"""
        try:
            from pypdf import PdfReader
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
            self._PdfReader = PdfReader
            self._canvas = canvas
            self._letter = letter
        except ImportError as e:
            raise FileError(f"缺少依赖 pypdf 或 reportlab: {e}", "import")
    
    def read(self, file_path: str) -> Dict[str, Any]:
        """读取 PDF 文件内容"""
        try:
            path = Path(file_path)
            if not path.exists():
                raise FileError("文件不存在", "read", file_path)
            
            reader = self._PdfReader(str(path))
            
            text_content = []
            for page in reader.pages:
                text_content.append(page.extract_text())
            
            return {
                "pages": len(reader.pages),
                "metadata": reader.metadata,
                "content": "\n".join(text_content)
            }
        except Exception as e:
            raise FileError(str(e), "read", file_path)
    
    def create(
        self,
        file_path: str,
        title: str,
        content: List[str],
        author: Optional[str] = None
    ) -> bool:
        """创建 PDF 文件"""
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            c = self._canvas.Canvas(str(path), pagesize=self._letter)
            width, height = self._letter
            
            # 标题
            c.setFont("Helvetica-Bold", 16)
            c.drawString(72, height - 72, title)
            
            # 内容
            c.setFont("Helvetica", 12)
            y_position = height - 120
            
            for line in content:
                if y_position < 72:  # 需要新页面
                    c.showPage()
                    y_position = height - 72
                    c.setFont("Helvetica", 12)
                
                c.drawString(72, y_position, line)
                y_position -= 20
            
            # 作者
            if author:
                c.setFont("Helvetica-Oblique", 10)
                c.drawString(72, 50, f"Author: {author}")
            
            c.save()
            logger.info(f"PDF 文件创建成功：{file_path}")
            return True
        except Exception as e:
            raise FileError(str(e), "create", file_path)
    
    def merge(self, input_files: List[str], output_file: str) -> bool:
        """合并多个 PDF 文件"""
        try:
            from pypdf import PdfWriter
            
            if not input_files:
                raise FileError("输入文件列表为空", "merge", output_file)
            
            writer = PdfWriter()
            
            for file_path in input_files:
                path = Path(file_path)
                if not path.exists():
                    logger.warning(f"文件不存在，跳过：{file_path}")
                    continue
                
                reader = self._PdfReader(str(path))
                for page in reader.pages:
                    writer.add_page(page)
            
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, "wb") as f:
                writer.write(f)
            
            logger.info(f"PDF 合并成功：{output_file} ({len(input_files)} 个文件)")
            return True
        except Exception as e:
            raise FileError(str(e), "merge", output_file)


class FileProcessingSkill:
    """文件处理技能主类"""
    
    def __init__(self):
        self._csv_handler = CSVHandler()
        self._excel_handler = ExcelHandler()
        self._pdf_handler = PDFHandler()
    
    @property
    def csv(self) -> CSVHandler:
        """获取 CSV 处理器"""
        return self._csv_handler
    
    @property
    def excel(self) -> ExcelHandler:
        """获取 Excel 处理器"""
        return self._excel_handler
    
    @property
    def pdf(self) -> PDFHandler:
        """获取 PDF 处理器"""
        return self._pdf_handler
    
    def convert_csv_to_excel(self, csv_path: str, excel_path: str) -> int:
        """CSV 转 Excel"""
        data = self._csv_handler.read(csv_path)
        return self._excel_handler.write(excel_path, data)
    
    def convert_excel_to_csv(self, excel_path: str, csv_path: str, sheet_name: Optional[str] = None) -> int:
        """Excel 转 CSV"""
        data = self._excel_handler.read(excel_path, sheet_name=sheet_name)
        
        if isinstance(data, dict):
            # 多 sheet，只转换第一个
            first_sheet = list(data.keys())[0]
            data = data[first_sheet]
        
        return self._csv_handler.write(csv_path, data)


# 便捷函数
def read_csv(file_path: str, **kwargs) -> List[Dict[str, Any]]:
    """快速读取 CSV 文件"""
    config = FileConfig(**kwargs) if kwargs else None
    handler = CSVHandler(config)
    return handler.read(file_path)


def write_csv(file_path: str, data: List[Dict[str, Any]], **kwargs) -> int:
    """快速写入 CSV 文件"""
    config = FileConfig(**kwargs) if kwargs else None
    handler = CSVHandler(config)
    return handler.write(file_path, data)


def read_excel(file_path: str, sheet_name: Optional[str] = None) -> Union[Dict, List]:
    """快速读取 Excel 文件"""
    handler = ExcelHandler()
    return handler.read(file_path, sheet_name)


def write_excel(file_path: str, data: List[Dict[str, Any]], sheet_name: str = "Sheet1") -> int:
    """快速写入 Excel 文件"""
    handler = ExcelHandler()
    return handler.write(file_path, data, sheet_name)


def read_pdf(file_path: str) -> Dict[str, Any]:
    """快速读取 PDF 文件"""
    handler = PDFHandler()
    return handler.read(file_path)


def create_pdf(
    file_path: str,
    title: str,
    content: List[str],
    author: Optional[str] = None
) -> bool:
    """快速创建 PDF 文件"""
    handler = PDFHandler()
    return handler.create(file_path, title, content, author)
