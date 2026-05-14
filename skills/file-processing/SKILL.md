# File Processing Skill - 文件处理技能

## 功能描述
提供 CSV、Excel、PDF 文件的读写、转换和处理能力。

## 激活条件
当用户提到以下关键词时激活：
- 文件处理 / 数据导入导出
- CSV / Excel / PDF
- 报表生成 / 数据转换
- 批量文件处理

## 依赖安装
```bash
pip install pandas openpyxl xlsxwriter pypdf reportlab pytest pytest-asyncio
```

## 使用示例

### CSV 文件处理

#### 读取 CSV
```python
from agentm.skills.file-processing.file_skill import read_csv, CSVHandler, FileConfig

# 便捷方式
data = read_csv("data.csv")

# 自定义配置
config = FileConfig(encoding="gbk", delimiter=";")
handler = CSVHandler(config)
data = handler.read("data_gbk.csv")

# 数据处理
for row in data:
    print(f"{row['name']}: {row['age']}")
```

#### 写入 CSV
```python
from agentm.skills.file-processing.file_skill import write_csv

data = [
    {"name": "张三", "age": 25, "city": "北京"},
    {"name": "李四", "age": 30, "city": "上海"},
    {"name": "王五", "age": 28, "city": "广州"}
]

written = write_csv("output.csv", data)
print(f"写入 {written} 行")
```

#### 追加数据
```python
from agentm.skills.file-processing.file_skill import CSVHandler

handler = CSVHandler()

# 追加新数据
handler.append("data.csv", [
    {"name": "赵六", "age": 35},
    {"name": "钱七", "age": 22}
])
```

### Excel 文件处理

#### 读取 Excel
```python
from agentm.skills.file-processing.file_skill import read_excel, ExcelHandler

# 读取默认 sheet
data = read_excel("report.xlsx")

# 读取指定 sheet
data = read_excel("report.xlsx", sheet_name="Sales")

# 读取所有 sheet
handler = ExcelHandler()
all_sheets = handler.read("multi_sheet.xlsx")
# all_sheets 是字典：{"Sheet1": [...], "Sheet2": [...]}
```

#### 写入 Excel
```python
from agentm.skills.file-processing.file_skill import write_excel

data = [
    {"product": "产品 A", "sales": 1000, "region": "华北"},
    {"product": "产品 B", "sales": 1500, "region": "华南"}
]

write_excel("sales_report.xlsx", data, sheet_name="2024")
```

#### 写入多 sheet
```python
from agentm.skills.file-processing.file_skill import ExcelHandler

handler = ExcelHandler()

data_dict = {
    "Q1": [{"month": "1 月", "sales": 100}, {"month": "2 月", "sales": 150}],
    "Q2": [{"month": "4 月", "sales": 200}, {"month": "5 月", "sales": 250}],
    "Q3": [{"month": "7 月", "sales": 300}, {"month": "8 月", "sales": 350}]
}

handler.write_multiple_sheets("quarterly_report.xlsx", data_dict)
```

### PDF 文件处理

#### 创建 PDF
```python
from agentm.skills.file-processing.file_skill import create_pdf, PDFHandler

# 便捷方式
content = [
    "报告摘要：本月销售额增长 20%",
    "主要增长来自华东地区",
    "建议继续加大市场投入"
]
create_pdf("report.pdf", title="月度报告", content=content, author="分析部")

# 使用处理器
handler = PDFHandler()
handler.create(
    "detailed_report.pdf",
    title="详细分析报告",
    content=["详细内容..."] * 50,  # 多页内容会自动分页
    author="分析师"
)
```

#### 读取 PDF
```python
from agentm.skills.file-processing.file_skill import read_pdf

result = read_pdf("document.pdf")
print(f"页数：{result['pages']}")
print(f"内容：{result['content'][:500]}")  # 前 500 字符
```

#### 合并 PDF
```python
from agentm.skills.file-processing.file_skill import PDFHandler

handler = PDFHandler()

pdf_files = ["report1.pdf", "report2.pdf", "report3.pdf"]
handler.merge(pdf_files, "combined_report.pdf")
```

### 文件格式转换

#### CSV 转 Excel
```python
from agentm.skills.file-processing.file_skill import FileProcessingSkill

skill = FileProcessingSkill()
rows = skill.convert_csv_to_excel("data.csv", "data.xlsx")
```

#### Excel 转 CSV
```python
from agentm.skills.file-processing.file_skill import FileProcessingSkill

skill = FileProcessingSkill()
rows = skill.convert_excel_to_csv("data.xlsx", "data.csv")

# 指定 sheet
rows = skill.convert_excel_to_csv("data.xlsx", "data.csv", sheet_name="Sales")
```

### 完整工作流示例

#### 数据导入 → 处理 → 导出报告
```python
from agentm.skills.file-processing.file_skill import FileProcessingSkill

skill = FileProcessingSkill()

# 1. 读取原始数据
raw_data = skill.csv.read("raw_data.csv")

# 2. 数据处理
processed_data = []
for row in raw_data:
    processed_data.append({
        "name": row["name"],
        "age": int(row["age"]),
        "age_group": "青年" if int(row["age"]) < 30 else "中年"
    })

# 3. 导出 Excel 报告
skill.excel.write("report.xlsx", processed_data, sheet_name="分析结果")

# 4. 生成 PDF 摘要
summary = [
    f"总人数：{len(processed_data)}",
    f"平均年龄：{sum(p['age'] for p in processed_data) / len(processed_data):.1f}",
    f"青年占比：{sum(1 for p in processed_data if p['age_group'] == '青年') / len(processed_data):.1%}"
]
skill.pdf.create("summary.pdf", title="数据摘要", content=summary)
```

## 错误处理
所有文件操作异常都会抛出 `FileError`，包含：
- `operation`: 失败的操作类型
- `file_path`: 相关文件路径

```python
from agentm.skills.file-processing.file_skill import FileError

try:
    data = skill.csv.read("nonexistent.csv")
except FileError as e:
    print(f"操作失败：{e.operation}")
    print(f"文件路径：{e.file_path}")
```

## 测试
```bash
cd /home/liyongxin/.openclaw/workspace/agentm/skills/file-processing
pytest test_file.py -v
```

## 文件结构
```
file-processing/
├── SKILL.md              # 技能说明文档
├── README.md             # 快速入门
├── file_skill.py         # 核心实现
├── test_file.py          # 单元测试
└── __init__.py           # 模块初始化
```
