"""
知识库（K 知识空间）

初始状态：完整代码规范
运行时：自动存入错误模式和修正方式

知识来源：
  - 初始种子（人工编写的代码规范）
  - 运行时（每次 Z3 发现 bug，自动转为知识）
"""

from __future__ import annotations

import uuid
import time
from pathlib import Path
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class RuleCategory(Enum):
    CORRECTNESS = "correctness"         # 正确性（能用底线）
    PERFORMANCE = "performance"         # 性能
    SECURITY = "security"              # 安全
    STYLE = "style"                     # 代码风格
    DESIGN = "design"                   # 架构设计
    TESTING = "testing"                # 测试


class RuleSeverity(Enum):
    CRITICAL = "critical"  # 必须遵守，违反 = 不能用
    WARNING = "warning"      # 推荐遵守
    INFO = "info"           # 建议


@dataclass
class Rule:
    """一条知识规则"""
    id: str
    category: RuleCategory
    severity: RuleSeverity

    # 规则内容
    title: str                    # 简短标题
    description: str              # 详细说明
    code_pattern: str | None = None  # 触发这条规则的代码模式（正则）
    fix_suggestion: str | None = None  # 如何修复

    # 元数据
    source: str = "seed"         # seed | z3 | correction | manual
    examples: list[dict] = field(default_factory=list)  # 正例/反例

    # 评分
    match_count: int = 0         # 这条规则被触发过多少次
    violation_count: int = 0     # 违反过多少次

    # 时间戳
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Rule":
        data["category"] = RuleCategory(data["category"])
        data["severity"] = RuleSeverity(data["severity"])
        return cls(**data)

    def to_prompt_text(self) -> str:
        """转换为提示文本"""
        text = f"[{self.severity.value.upper()}] {self.title}\n{self.description}"
        if self.fix_suggestion:
            text += f"\n修复建议：{self.fix_suggestion}"
        return text


# ---------------------------------------------------------------------------
# Knowledge Base (ChromaDB)
# ---------------------------------------------------------------------------

class KnowledgeBase:
    """
    代码知识库

    初始加载：代码规范种子（人工编写）
    运行时补充：从 Z3 错误自动生成规则
    """

    COLLECTION_NAME = "agentm_knowledge"

    # 默认规则种子
    SEED_RULES: list[dict] = [
        # ===== 正确性（CRITICAL）=====
        {
            "title": "除法前必须检查分母",
            "category": RuleCategory.CORRECTNESS,
            "severity": RuleSeverity.CRITICAL,
            "description": "所有除法操作前必须检查分母不为零。Z3 可检测整数除零和浮点除零。",
            "code_pattern": r"/\s*\w+\s*(?!.*==\s*0)",
            "fix_suggestion": "在除法前添加：if denominator == 0: raise ValueError(...)",
            "examples": [
                {"good": "if b != 0: return a / b", "bad": "return a / b"},
            ],
        },
        {
            "title": "数组访问必须做边界检查",
            "category": RuleCategory.CORRECTNESS,
            "severity": RuleSeverity.CRITICAL,
            "description": "访问数组/列表元素前必须检查索引在有效范围内。",
            "code_pattern": r"\[\s*\w+\s*\]",
            "fix_suggestion": "访问前检查：0 <= index < len(array)",
            "examples": [
                {"good": "if 0 <= i < len(arr): return arr[i]", "bad": "return arr[i]"},
            ],
        },
        {
            "title": "所有外部输入必须校验",
            "category": RuleCategory.CORRECTNESS,
            "severity": RuleSeverity.CRITICAL,
            "description": "来自文件、网络、用户输入的数据在使用前必须校验类型和范围。",
            "fix_suggestion": "使用 isinstance() 和范围检查验证输入",
            "examples": [],
        },
        {
            "title": "空指针/None 检查",
            "category": RuleCategory.CORRECTNESS,
            "severity": RuleSeverity.CRITICAL,
            "description": "调用对象方法或访问属性前必须检查对象不为 None。",
            "code_pattern": r"\.\w+\(",
            "fix_suggestion": "调用前添加：if obj is not None:",
            "examples": [
                {"good": "if obj is not None: obj.method()", "bad": "obj.method()"},
            ],
        },
        {
            "title": "循环必须有终止条件",
            "category": RuleCategory.CORRECTNESS,
            "severity": RuleSeverity.CRITICAL,
            "description": "所有循环（for/while）必须有明确的终止条件，防止无限循环。",
            "fix_suggestion": "确保循环变量在每次迭代后向终止条件靠近，或使用 max_iterations 防护",
            "examples": [],
        },
        {
            "title": "锁保护的共享资源访问",
            "category": RuleCategory.CORRECTNESS,
            "severity": RuleSeverity.CRITICAL,
            "description": "多线程访问共享变量必须加锁保护。",
            "code_pattern": r"global\s+\w+|shared\w+",
            "fix_suggestion": "使用 threading.Lock 或 threading.RLock 保护共享资源",
            "examples": [],
        },
        # ===== 性能（WARNING）=====
        {
            "title": "避免嵌套循环导致的 O(n³) 复杂度",
            "category": RuleCategory.PERFORMANCE,
            "severity": RuleSeverity.WARNING,
            "description": "嵌套循环如果每个循环都是 O(n)，总复杂度是 O(n³) 或更高。优先考虑哈希表优化。",
            "fix_suggestion": "用空间换时间：使用 dict/set 做 O(1) 查找代替内层循环",
            "examples": [],
        },
        {
            "title": "字符串拼接用 join 而非 +",
            "category": RuleCategory.PERFORMANCE,
            "severity": RuleSeverity.WARNING,
            "description": "循环内拼接字符串用 str.join()，不用 + 运算符（每次创建新字符串对象）。",
            "code_pattern": r'for.*\+=\s*str|str\s*\+\s*str',
            "fix_suggestion": "用 ''.join([...]) 代替循环内的 + 拼接",
            "examples": [
                {"good": "''.join([str(x) for x in items])", "bad": "result = ''\\nfor x in items: result += str(x)"},
            ],
        },
        # ===== 安全（CRITICAL）=====
        {
            "title": "禁止 SQL 拼接",
            "category": RuleCategory.SECURITY,
            "severity": RuleSeverity.CRITICAL,
            "description": "SQL 查询禁止用字符串拼接，必须用参数化查询。",
            "fix_suggestion": "使用 SQLAlchemy、psycopg2 的参数化查询或 ORM",
            "examples": [
                {"good": "cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))", "bad": "cursor.execute(f'SELECT * FROM users WHERE id = {user_id}')"},
            ],
        },
        {
            "title": "禁止 eval/exec 执行动态代码",
            "category": RuleCategory.SECURITY,
            "severity": RuleSeverity.CRITICAL,
            "description": "禁止使用 eval()、exec()、ast.literal_eval() 执行未验证的用户输入。",
            "fix_suggestion": "使用安全的 AST 解析或专门的表达式求值库",
            "examples": [
                {"good": "# 使用安全的表达式解析库", "bad": "eval(user_input)"},
            ],
        },
        {
            "title": "禁止明文存储密码",
            "category": RuleCategory.SECURITY,
            "severity": RuleSeverity.CRITICAL,
            "description": "密码必须哈希存储，禁止明文。使用 bcrypt 或 argon2。",
            "fix_suggestion": "使用 bcrypt.hashpw() 哈希密码，bcrypt.checkpw() 验证",
            "examples": [],
        },
        # ===== 代码风格（INFO）=====
        {
            "title": "函数不超过 50 行",
            "category": RuleCategory.STYLE,
            "severity": RuleSeverity.INFO,
            "description": "函数应保持简短，单个函数不超过 50 行。超过时应拆分成子函数。",
            "fix_suggestion": "将函数分解为多个职责单一的小函数",
            "examples": [],
        },
        {
            "title": "变量命名有意义",
            "category": RuleCategory.STYLE,
            "severity": RuleSeverity.INFO,
            "description": "变量名必须有意义，避免单字母（循环变量除外）和无意义名称。",
            "fix_suggestion": "使用描述性名称：user_count 而不是 uc，max_retries 而不是 mr",
            "examples": [],
        },
        {
            "title": "DRY 原则：不重复代码",
            "category": RuleCategory.STYLE,
            "severity": RuleSeverity.INFO,
            "description": "相同逻辑只写一次，提取为公共函数或类方法。",
            "fix_suggestion": "提取重复代码为函数、类或常量",
            "examples": [],
        },
    ]

    def __init__(self, persist_dir: str | Path | None = None):
        if persist_dir is None:
            persist_dir = Path("D:/agentm/data/knowledge")
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir / "chroma_db"),
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
        )

        try:
            self.collection = self.client.get_collection(name=self.COLLECTION_NAME)
        except Exception:
            self.collection = self.client.create_collection(
                name=self.COLLECTION_NAME,
                metadata={"description": "M-Agent knowledge base"},
            )

        # 初始化种子规则
        if self.collection.count() == 0:
            self._load_seed_rules()

    def _load_seed_rules(self):
        """加载初始规则种子"""
        for rule_data in self.SEED_RULES:
            self.add_rule(
                category=rule_data["category"],
                severity=rule_data["severity"],
                title=rule_data["title"],
                description=rule_data["description"],
                code_pattern=rule_data.get("code_pattern"),
                fix_suggestion=rule_data.get("fix_suggestion"),
                examples=rule_data.get("examples", []),
                source="seed",
            )

    def add_rule(
        self,
        category: RuleCategory,
        severity: RuleSeverity,
        title: str,
        description: str,
        code_pattern: str | None = None,
        fix_suggestion: str | None = None,
        examples: list[dict] | None = None,
        source: str = "manual",
    ) -> Rule:
        """添加一条规则"""
        rid = str(uuid.uuid4())

        rule = Rule(
            id=rid,
            category=category,
            severity=severity,
            title=title,
            description=description,
            code_pattern=code_pattern,
            fix_suggestion=fix_suggestion,
            examples=examples or [],
            source=source,
        )

        # ChromaDB 不直接支持 dict 列表，用 JSON 字符串
        self.collection.add(
            documents=[description],
            metadatas=[{
                "id": rid,
                "category": category.value,
                "severity": severity.value,
                "title": title,
                "description": description,
                "code_pattern": code_pattern or "",
                "fix_suggestion": fix_suggestion or "",
                "examples": str(examples or []),
                "source": source,
                "match_count": 0,
                "violation_count": 0,
                "created_at": rule.created_at,
                "last_updated": rule.last_updated,
            }],
            ids=[rid],
        )

        return rule

    def search(
        self,
        query: str,
        top_k: int = 10,
        category: RuleCategory | None = None,
        severity: RuleSeverity | None = None,
    ) -> list[Rule]:
        """语义搜索规则"""
        where_filter = {}
        if category:
            where_filter["category"] = category.value
        if severity:
            where_filter["severity"] = severity.value

        results = self.collection.query(
            query_texts=[query],
            n_results=top_k * 2,
            where=where_filter if where_filter else None,
        )

        rules = []
        if not results["ids"]:
            return []

        for i, rid in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i]
            try:
                rule = Rule(
                    id=rid,
                    category=RuleCategory(meta["category"]),
                    severity=RuleSeverity(meta["severity"]),
                    title=meta["title"],
                    description=meta["description"],
                    code_pattern=meta.get("code_pattern") or None,
                    fix_suggestion=meta.get("fix_suggestion") or None,
                    examples=eval(meta.get("examples", "[]")),
                    source=meta.get("source", "manual"),
                    match_count=int(meta.get("match_count", 0)),
                    violation_count=int(meta.get("violation_count", 0)),
                    created_at=float(meta.get("created_at", time.time())),
                    last_updated=float(meta.get("last_updated", time.time())),
                )
                rules.append(rule)
            except (KeyError, ValueError):
                continue

            if len(rules) >= top_k:
                break

        return rules

    def get_critical_rules(self) -> list[Rule]:
        """获取所有 CRITICAL 规则（Z3 验证时必须检查）"""
        return self.search(
            query="correctness critical safety",
            top_k=50,
            severity=RuleSeverity.CRITICAL,
        )

    def record_match(self, rule_id: str):
        """记录规则被触发（匹配）"""
        results = self.collection.get(ids=[rule_id])
        if results["ids"]:
            meta = results["metadatas"][0]
            self.collection.update(
                ids=[rule_id],
                metadatas=[{
                    **meta,
                    "match_count": int(meta.get("match_count", 0)) + 1,
                    "last_updated": time.time(),
                }],
            )

    def record_violation(self, rule_id: str):
        """记录规则被违反"""
        results = self.collection.get(ids=[rule_id])
        if results["ids"]:
            meta = results["metadatas"][0]
            self.collection.update(
                ids=[rule_id],
                metadatas=[{
                    **meta,
                    "violation_count": int(meta.get("violation_count", 0)) + 1,
                    "last_updated": time.time(),
                }],
            )

    def rules_from_z3_failure(
        self,
        counterexample: str,
        task_description: str,
        fix_applied: str | None = None,
    ) -> Rule:
        """从 Z3 失败中自动生成规则"""
        # 从反例提取关键信息
        rule = self.add_rule(
            category=RuleCategory.CORRECTNESS,
            severity=RuleSeverity.CRITICAL,
            title=f"Z3 发现：{task_description[:50]}",
            description=f"Z3 验证失败。反例：{counterexample[:300]}",
            fix_suggestion=fix_applied or "需要修复代码逻辑",
            source="z3",
        )
        return rule


# ---------------------------------------------------------------------------
# Global Instance
# ---------------------------------------------------------------------------

_kb: KnowledgeBase | None = None


def get_knowledge_base() -> KnowledgeBase:
    global _kb
    if _kb is None:
        _kb = KnowledgeBase()
    return _kb
