"""
File Processing Skill 单元测试
"""

import pytest
import tempfile
from pathlib import Path
from file_skill import (
    FileProcessingSkill,
    FileConfig,
    CSVHandler,
    ExcelHandler,
    PDFHandler,
    FileError,
    read_csv,
    write_csv,
    read_excel,
    write_excel
)


class TestFileConfig:
    """测试文件配置"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = FileConfig()
        assert config.encoding == "utf-8"
        assert config.delimiter == ","
        assert config.sheet_name is None
        assert config.header_row == 0
    
    def test_custom_config(self):
        """测试自定义配置"""
        config = FileConfig(
            encoding="gbk",
            delimiter=";",
            sheet_name="Data",
            header_row=1
        )
        assert config.encoding == "gbk"
        assert config.delimiter == ";"
        assert config.sheet_name == "Data"


class TestCSVHandler:
    """测试 CSV 处理器"""
    
    @pytest.fixture
    def csv_handler(self):
        """创建 CSV 处理器"""
        return CSVHandler()
    
    @pytest.fixture
    def sample_data(self):
        """样本数据"""
        return [
            {"name": "张三", "age": "25", "city": "北京"},
            {"name": "李四", "age": "30", "city": "上海"},
            {"name": "王五", "age": "28", "city": "广州"}
        ]
    
    def test_write_and_read(self, csv_handler: CSVHandler, sample_data: list, tmp_path: Path):
        """测试写入和读取 CSV"""
        csv_path = tmp_path / "test.csv"
        
        # 写入
        written = csv_handler.write(str(csv_path), sample_data)
        assert written == 3
        
        # 读取
        data = csv_handler.read(str(csv_path))
        assert len(data) == 3
        assert data[0]["name"] == "张三"
        assert data[1]["city"] == "上海"
    
    def test_append(self, csv_handler: CSVHandler, tmp_path: Path):
        """测试追加数据"""
        csv_path = tmp_path / "test.csv"
        
        # 初始写入
        csv_handler.write(str(csv_path), [{"name": "张三", "age": "25"}])
        
        # 追加
        appended = csv_handler.append(
            str(csv_path),
            [{"name": "李四", "age": "30"}, {"name": "王五", "age": "28"}]
        )
        assert appended == 2
        
        # 验证
        data = csv_handler.read(str(csv_path))
        assert len(data) == 3
    
    def test_read_nonexistent(self, csv_handler: CSVHandler):
        """测试读取不存在的文件"""
        with pytest.raises(FileError, match="文件不存在"):
            csv_handler.read("/nonexistent/file.csv")
    
    def test_write_empty_data(self, csv_handler: CSVHandler, tmp_path: Path):
        """测试写入空数据"""
        csv_path = tmp_path / "empty.csv"
        written = csv_handler.write(str(csv_path), [])
        assert written == 0
    
    def test_custom_delimiter(self, tmp_path: Path):
        """测试自定义分隔符"""
        config = FileConfig(delimiter=";")
        handler = CSVHandler(config)
        
        data = [{"name": "张三", "age": "25"}]
        csv_path = tmp_path / "semicolon.csv"
        
        handler.write(str(csv_path), data)
        read_data = handler.read(str(csv_path))
        
        assert len(read_data) == 1
        assert read_data[0]["name"] == "张三"


class TestExcelHandler:
    """测试 Excel 处理器"""
    
    @pytest.fixture
    def excel_handler(self):
        """创建 Excel 处理器"""
        return ExcelHandler()
    
    @pytest.fixture
    def sample_data(self):
        """样本数据"""
        return [
            {"name": "张三", "age": 25, "city": "北京"},
            {"name": "李四", "age": 30, "city": "上海"}
        ]
    
    def test_write_and_read(self, excel_handler: ExcelHandler, sample_data: list, tmp_path: Path):
        """测试写入和读取 Excel"""
        excel_path = tmp_path / "test.xlsx"
        
        # 写入
        written = excel_handler.write(str(excel_path), sample_data)
        assert written == 2
        
        # 读取
        data = excel_handler.read(str(excel_path))
        assert len(data) == 2
        assert data[0]["name"] == "张三"
    
    def test_write_multiple_sheets(self, excel_handler: ExcelHandler, tmp_path: Path):
        """测试写入多 sheet"""
        excel_path = tmp_path / "multi_sheet.xlsx"
        
        data_dict = {
            "Sheet1": [{"name": "张三", "age": 25}],
            "Sheet2": [{"name": "李四", "age": 30}],
            "Sheet3": [{"name": "王五", "age": 28}]
        }
        
        total = excel_handler.write_multiple_sheets(str(excel_path), data_dict)
        assert total == 3
        
        # 验证可以读取
        all_sheets = excel_handler.read(str(excel_path))
        assert isinstance(all_sheets, dict)
        assert len(all_sheets) == 3
    
    def test_read_nonexistent(self, excel_handler: ExcelHandler):
        """测试读取不存在的文件"""
        with pytest.raises(FileError, match="文件不存在"):
            excel_handler.read("/nonexistent/file.xlsx")
    
    def test_write_empty_data(self, excel_handler: ExcelHandler, tmp_path: Path):
        """测试写入空数据"""
        excel_path = tmp_path / "empty.xlsx"
        written = excel_handler.write(str(excel_path), [])
        assert written == 0


class TestPDFHandler:
    """测试 PDF 处理器"""
    
    @pytest.fixture
    def pdf_handler(self):
        """创建 PDF 处理器"""
        return PDFHandler()
    
    def test_create_pdf(self, pdf_handler: PDFHandler, tmp_path: Path):
        """测试创建 PDF"""
        pdf_path = tmp_path / "test.pdf"
        
        content = [
            "这是第一行内容",
            "这是第二行内容",
            "这是第三行内容"
        ]
        
        result = pdf_handler.create(
            str(pdf_path),
            title="测试文档",
            content=content,
            author="测试作者"
        )
        
        assert result is True
        assert pdf_path.exists()
    
    def test_create_pdf_empty_content(self, pdf_handler: PDFHandler, tmp_path: Path):
        """测试创建空内容 PDF"""
        pdf_path = tmp_path / "empty.pdf"
        
        result = pdf_handler.create(
            str(pdf_path),
            title="空文档",
            content=[]
        )
        
        assert result is True
        assert pdf_path.exists()
    
    def test_merge_pdfs(self, pdf_handler: PDFHandler, tmp_path: Path):
        """测试合并 PDF"""
        # 创建多个 PDF
        pdf1 = tmp_path / "file1.pdf"
        pdf2 = tmp_path / "file2.pdf"
        output = tmp_path / "merged.pdf"
        
        pdf_handler.create(str(pdf1), "文档 1", ["内容 1"])
        pdf_handler.create(str(pdf2), "文档 2", ["内容 2"])
        
        result = pdf_handler.merge([str(pdf1), str(pdf2)], str(output))
        
        assert result is True
        assert output.exists()
    
    def test_merge_with_nonexistent(self, pdf_handler: PDFHandler, tmp_path: Path):
        """测试合并不存在的文件"""
        pdf1 = tmp_path / "exists.pdf"
        pdf_handler.create(str(pdf1), "文档 1", ["内容 1"])
        
        output = tmp_path / "merged.pdf"
        result = pdf_handler.merge([str(pdf1), "/nonexistent.pdf"], str(output))
        
        assert result is True
        assert output.exists()


class TestFileProcessingSkill:
    """测试文件处理技能主类"""
    
    def test_create_skill(self):
        """测试创建技能实例"""
        skill = FileProcessingSkill()
        assert skill.csv is not None
        assert skill.excel is not None
        assert skill.pdf is not None
    
    def test_convert_csv_to_excel(self, tmp_path: Path):
        """测试 CSV 转 Excel"""
        skill = FileProcessingSkill()
        
        # 创建 CSV
        csv_path = tmp_path / "data.csv"
        excel_path = tmp_path / "data.xlsx"
        
        skill.csv.write(str(csv_path), [
            {"name": "张三", "age": "25"},
            {"name": "李四", "age": "30"}
        ])
        
        # 转换
        rows = skill.convert_csv_to_excel(str(csv_path), str(excel_path))
        assert rows == 2
        assert excel_path.exists()
    
    def test_convert_excel_to_csv(self, tmp_path: Path):
        """测试 Excel 转 CSV"""
        skill = FileProcessingSkill()
        
        # 创建 Excel
        excel_path = tmp_path / "data.xlsx"
        csv_path = tmp_path / "data.csv"
        
        skill.excel.write(str(excel_path), [
            {"name": "张三", "age": 25},
            {"name": "李四", "age": 30}
        ])
        
        # 转换
        rows = skill.convert_excel_to_csv(str(excel_path), str(csv_path))
        assert rows == 2
        assert csv_path.exists()


class TestConvenienceFunctions:
    """测试便捷函数"""
    
    def test_read_write_csv(self, tmp_path: Path):
        """测试 CSV 便捷函数"""
        csv_path = tmp_path / "test.csv"
        
        data = [{"name": "张三", "age": "25"}]
        written = write_csv(str(csv_path), data)
        assert written == 1
        
        read_data = read_csv(str(csv_path))
        assert len(read_data) == 1
    
    def test_read_write_excel(self, tmp_path: Path):
        """测试 Excel 便捷函数"""
        excel_path = tmp_path / "test.xlsx"
        
        data = [{"name": "张三", "age": 25}]
        written = write_excel(str(excel_path), data)
        assert written == 1
        
        read_data = read_excel(str(excel_path))
        assert len(read_data) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
