"""
AgentM Skills 集成模块

将外部 Skills 集成到工作流引擎中
提供统一的 Skill 调用接口
"""

import importlib
import logging
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


class SkillInfo:
    """Skill 信息"""
    
    def __init__(
        self,
        name: str,
        path: str,
        description: str = "",
        version: str = "1.0.0",
        enabled: bool = True
    ):
        self.name = name
        self.path = path
        self.description = description
        self.version = version
        self.enabled = enabled
        self.module = None
        self.functions: Dict[str, Callable] = {}
    
    def load(self) -> bool:
        """加载 Skill 模块"""
        try:
            spec = importlib.util.spec_from_file_location(self.name, self.path)
            if spec and spec.loader:
                self.module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(self.module)
                
                # 提取公共函数
                for attr_name in dir(self.module):
                    attr = getattr(self.module, attr_name)
                    if callable(attr) and not attr_name.startswith('_'):
                        self.functions[attr_name] = attr
                
                logger.info(f"Skill 加载成功：{self.name}")
                return True
        except Exception as e:
            logger.error(f"Skill 加载失败 {self.name}: {e}")
            return False
        
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'name': self.name,
            'path': self.path,
            'description': self.description,
            'version': self.version,
            'enabled': self.enabled,
            'functions': list(self.functions.keys())
        }


class SkillRegistry:
    """
    Skill 注册表
    
    管理所有可用的 Skills
    """
    
    def __init__(self):
        self._skills: Dict[str, SkillInfo] = {}
        self._initialized = False
    
    def register(
        self,
        name: str,
        path: str,
        description: str = "",
        version: str = "1.0.0"
    ) -> SkillInfo:
        """注册 Skill"""
        skill = SkillInfo(name, path, description, version)
        self._skills[name] = skill
        logger.info(f"注册 Skill: {name}")
        return skill
    
    def unregister(self, name: str) -> bool:
        """注销 Skill"""
        if name in self._skills:
            del self._skills[name]
            logger.info(f"注销 Skill: {name}")
            return True
        return False
    
    def get(self, name: str) -> Optional[SkillInfo]:
        """获取 Skill"""
        return self._skills.get(name)
    
    def list_skills(self, enabled_only: bool = False) -> List[SkillInfo]:
        """列出所有 Skills"""
        if enabled_only:
            return [s for s in self._skills.values() if s.enabled]
        return list(self._skills.values())
    
    def load_all(self) -> Dict[str, bool]:
        """加载所有 Skills"""
        results = {}
        for name, skill in self._skills.items():
            if skill.enabled:
                results[name] = skill.load()
        self._initialized = True
        return results
    
    def call(
        self,
        skill_name: str,
        function_name: str,
        *args,
        **kwargs
    ) -> Any:
        """
        调用 Skill 函数
        
        Args:
            skill_name: Skill 名称
            function_name: 函数名称
            *args: 位置参数
            **kwargs: 关键字参数
        
        Returns:
            函数执行结果
        """
        skill = self.get(skill_name)
        if not skill:
            raise ValueError(f"Skill 不存在：{skill_name}")
        
        if not skill.enabled:
            raise ValueError(f"Skill 已禁用：{skill_name}")
        
        if function_name not in skill.functions:
            raise ValueError(f"函数不存在：{function_name} in {skill_name}")
        
        func = skill.functions[function_name]
        return func(*args, **kwargs)
    
    def get_status(self) -> Dict[str, Any]:
        """获取 Skill 状态"""
        loaded = sum(1 for s in self._skills.values() if s.module is not None)
        enabled = sum(1 for s in self._skills.values() if s.enabled)
        
        return {
            'total': len(self._skills),
            'loaded': loaded,
            'enabled': enabled,
            'disabled': len(self._skills) - enabled,
            'skills': {name: info.to_dict() for name, info in self._skills.items()}
        }


# ============================================
# 全局 Skill 注册表
# ============================================

_global_registry: Optional[SkillRegistry] = None


def get_registry() -> SkillRegistry:
    """获取全局注册表"""
    global _global_registry
    if _global_registry is None:
        _global_registry = SkillRegistry()
    return _global_registry


def init_external_skills(skills_dir: Optional[str] = None) -> SkillRegistry:
    """
    初始化外部 Skills
    
    自动扫描 skills_external 目录并注册所有 Skills
    """
    registry = get_registry()
    
    if skills_dir is None:
        skills_dir = Path(__file__).parent.parent / 'skills_external'
    
    skills_path = Path(skills_dir)
    if not skills_path.exists():
        logger.warning(f"Skills 目录不存在：{skills_dir}")
        return registry
    
    # 扫描 Skills
    for skill_dir in skills_path.iterdir():
        if not skill_dir.is_dir():
            continue
        
        skill_name = skill_dir.name
        skill_file = skill_dir / f"{skill_name.replace('-', '_')}_skill.py"
        
        if skill_file.exists():
            registry.register(
                name=skill_name,
                path=str(skill_file),
                description=f"External skill: {skill_name}"
            )
        else:
            # 查找其他 Python 文件
            py_files = list(skill_dir.glob("*.py"))
            if py_files:
                registry.register(
                    name=skill_name,
                    path=str(py_files[0]),
                    description=f"External skill: {skill_name}"
                )
    
    logger.info(f"扫描到 {len(registry.list_skills())} 个外部 Skills")
    return registry


def create_skill_node(skill_name: str, function_name: str):
    """
    创建工作流节点包装器
    
    用于将 Skill 函数转换为工作流节点
    """
    from workflows.workflow_engine import WorkflowEngine
    
    async def skill_step(context: Dict[str, Any]) -> Any:
        """Skill 步骤函数"""
        registry = get_registry()
        return registry.call(skill_name, function_name, **context)
    
    return skill_step


# ============================================
# 预定义 Skills
# ============================================

def register_builtin_skills(registry: Optional[SkillRegistry] = None) -> None:
    """注册内置 Skills"""
    if registry is None:
        registry = get_registry()
    
    # 天气 Skill
    registry.register(
        name="weather",
        path=str(Path(__file__).parent.parent / 'skills_external' / 'weather' / 'weather_skill.py'),
        description="天气查询 Skill",
        version="1.0.0"
    )
    
    # 图像生成 Skill
    registry.register(
        name="image-generation",
        path=str(Path(__file__).parent.parent / 'skills_external' / 'image-generation' / 'image_generation_skill.py'),
        description="图像生成 Skill",
        version="1.0.0"
    )
    
    # PPT 生成 Skill
    registry.register(
        name="ppt-generation",
        path=str(Path(__file__).parent.parent / 'skills_external' / 'ppt-generation' / 'ppt_generation_skill.py'),
        description="PPT 生成 Skill",
        version="1.0.0"
    )
    
    # 视频生成 Skill
    registry.register(
        name="video-generation",
        path=str(Path(__file__).parent.parent / 'skills_external' / 'video-generation' / 'video_generation_skill.py'),
        description="视频生成 Skill",
        version="1.0.0"
    )
    
    # 数据分析 Skill
    registry.register(
        name="data-analysis",
        path=str(Path(__file__).parent.parent / 'skills_external' / 'data-analysis' / 'data_analysis_skill.py'),
        description="数据分析 Skill",
        version="1.0.0"
    )
    
    # 深度研究 Skill
    registry.register(
        name="deep-research",
        path=str(Path(__file__).parent.parent / 'skills_external' / 'deep-research' / 'deep_research_skill.py'),
        description="深度研究 Skill",
        version="1.0.0"
    )
    
    # 代码 Agent Skill
    registry.register(
        name="coding-agent",
        path=str(Path(__file__).parent.parent / 'skills_external' / 'coding-agent' / 'coding_agent_skill.py'),
        description="代码 Agent Skill",
        version="1.0.0"
    )
    
    # 前端设计 Skill
    registry.register(
        name="frontend-design",
        path=str(Path(__file__).parent.parent / 'skills_external' / 'frontend-design' / 'frontend_design_skill.py'),
        description="前端设计 Skill",
        version="1.0.0"
    )
    
    # 图表可视化 Skill
    registry.register(
        name="chart-visualization",
        path=str(Path(__file__).parent.parent / 'skills_external' / 'chart-visualization' / 'chart_visualization_skill.py'),
        description="图表可视化 Skill",
        version="1.0.0"
    )
    
    logger.info("已注册内置 Skills")


# ============================================
# 命令行工具
# ============================================

def main():
    """命令行工具"""
    import argparse
    
    parser = argparse.ArgumentParser(description='AgentM Skills 管理工具')
    parser.add_argument('command', choices=['list', 'info', 'load', 'call', 'status'],
                       help='命令')
    parser.add_argument('--skill', '-s', help='Skill 名称')
    parser.add_argument('--function', '-f', help='函数名称')
    parser.add_argument('--args', '-a', nargs='*', help='函数参数')
    
    args = parser.parse_args()
    
    # 初始化
    registry = get_registry()
    register_builtin_skills(registry)
    
    if args.command == 'list':
        skills = registry.list_skills(enabled_only=True)
        print(f"\n已注册的 Skills ({len(skills)}):\n")
        for skill in skills:
            status = "✅" if skill.enabled else "❌"
            print(f"  {status} {skill.name} - {skill.description}")
    
    elif args.command == 'info':
        if not args.skill:
            print("错误：请指定 Skill 名称 --skill")
            return
        
        skill = registry.get(args.skill)
        if not skill:
            print(f"Skill 不存在：{args.skill}")
            return
        
        print(f"\nSkill 信息:\n")
        print(f"  名称：{skill.name}")
        print(f"  路径：{skill.path}")
        print(f"  描述：{skill.description}")
        print(f"  版本：{skill.version}")
        print(f"  状态：{'启用' if skill.enabled else '禁用'}")
        print(f"  函数：{list(skill.functions.keys())}")
    
    elif args.command == 'load':
        results = registry.load_all()
        print(f"\n加载结果:\n")
        for name, success in results.items():
            status = "✅" if success else "❌"
            print(f"  {status} {name}")
    
    elif args.command == 'call':
        if not args.skill or not args.function:
            print("错误：请指定 Skill 和函数 --skill --function")
            return
        
        try:
            result = registry.call(args.skill, args.function, *(args.args or []))
            print(f"\n执行结果:\n{result}")
        except Exception as e:
            print(f"执行失败：{e}")
    
    elif args.command == 'status':
        status = registry.get_status()
        print(f"\nSkill 状态:\n")
        print(f"  总数：{status['total']}")
        print(f"  已加载：{status['loaded']}")
        print(f"  已启用：{status['enabled']}")
        print(f"  已禁用：{status['disabled']}")


if __name__ == '__main__':
    main()
