"""
Skill Registry Tests - 技能注册表测试
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock

from agentm.src.skill_registry import (
    SkillRegistry,
    SkillCategory,
    get_registry,
    register_default_skills
)
from agentm.src.nodes.base_node import NodeStatus


class TestSkillRegistry:
    """技能注册表测试"""
    
    @pytest.fixture
    def registry(self):
        """创建注册表实例"""
        # 重置单例
        SkillRegistry._instance = None
        SkillRegistry._initialized = False
        return get_registry()
    
    def test_singleton(self, registry):
        """测试单例模式"""
        registry2 = get_registry()
        assert registry is registry2
    
    def test_register_skill(self, registry):
        """测试注册技能"""
        registry.register(
            name="test_skill",
            class_name="TestNode",
            category=SkillCategory.UTILITY_TOOLS,
            description="测试技能",
            module_path="test.module"
        )
        
        skill = registry.get_skill("test_skill")
        assert skill is not None
        assert skill.name == "test_skill"
        assert skill.category == SkillCategory.UTILITY_TOOLS
    
    def test_unregister_skill(self, registry):
        """测试注销技能"""
        registry.register(
            name="test_skill",
            class_name="TestNode",
            category=SkillCategory.UTILITY_TOOLS,
            description="测试技能",
            module_path="test.module"
        )
        
        assert registry.unregister("test_skill") is True
        assert registry.get_skill("test_skill") is None
    
    def test_list_skills(self, registry):
        """测试列出技能"""
        registry.register(
            name="skill1",
            class_name="Node1",
            category=SkillCategory.DATA_PROCESSING,
            description="技能 1",
            module_path="test.module1"
        )
        registry.register(
            name="skill2",
            class_name="Node2",
            category=SkillCategory.CONTENT_GENERATION,
            description="技能 2",
            module_path="test.module2"
        )
        
        all_skills = registry.list_skills()
        assert len(all_skills) == 2
        
        data_skills = registry.list_skills(category=SkillCategory.DATA_PROCESSING)
        assert len(data_skills) == 1
        assert data_skills[0].name == "skill1"
    
    def test_enable_disable(self, registry):
        """测试启用/禁用技能"""
        registry.register(
            name="test_skill",
            class_name="TestNode",
            category=SkillCategory.UTILITY_TOOLS,
            description="测试技能",
            module_path="test.module"
        )
        
        assert registry.disable("test_skill") is True
        skill = registry.get_skill("test_skill")
        assert skill.enabled is False
        
        assert registry.enable("test_skill") is True
        assert skill.enabled is True
    
    def test_get_stats(self, registry):
        """测试统计信息"""
        registry.register(
            name="test_skill",
            class_name="TestNode",
            category=SkillCategory.UTILITY_TOOLS,
            description="测试技能",
            module_path="test.module"
        )
        
        stats = registry.get_stats()
        assert "total_skills" in stats
        assert "enabled_skills" in stats
        assert "total_executions" in stats


class TestDefaultSkills:
    """默认技能测试"""
    
    @pytest.fixture
    def registry_with_defaults(self):
        """创建带默认技能的注册表"""
        SkillRegistry._instance = None
        SkillRegistry._initialized = False
        register_default_skills()
        return get_registry()
    
    def test_default_skills_registered(self, registry_with_defaults):
        """测试默认技能已注册"""
        skills = registry_with_defaults.list_skills()
        assert len(skills) > 0
        
        skill_names = [s.name for s in skills]
        expected_skills = [
            "data_analysis",
            "deep_research",
            "image_generation",
            "coding_agent",
            "weather"
        ]
        
        for skill in expected_skills:
            assert skill in skill_names
    
    def test_skills_by_category(self, registry_with_defaults):
        """测试按类别筛选技能"""
        data_skills = registry_with_defaults.list_skills(
            category=SkillCategory.DATA_PROCESSING
        )
        assert len(data_skills) > 0
        
        content_skills = registry_with_defaults.list_skills(
            category=SkillCategory.CONTENT_GENERATION
        )
        assert len(content_skills) > 0


class TestNodeExecution:
    """节点执行测试"""
    
    @pytest.mark.asyncio
    async def test_execute_nonexistent_skill(self):
        """测试执行不存在的技能"""
        registry = get_registry()
        result = await registry.execute("nonexistent_skill", {})
        
        assert result.result.status == NodeStatus.FAILED
        assert "技能不存在" in result.result.error
    
    @pytest.mark.asyncio
    async def test_execute_with_missing_params(self):
        """测试执行缺少参数的技能"""
        registry = get_registry()
        
        # 注册一个需要必需参数的技能
        registry.register(
            name="test_skill",
            class_name="TestNode",
            category=SkillCategory.UTILITY_TOOLS,
            description="测试技能",
            module_path="test.module"
        )
        
        # 模拟节点验证
        with patch.object(registry, 'get_node') as mock_get_node:
            mock_node = MagicMock()
            mock_node.validate_input.return_value = (False, "缺少必需参数")
            mock_get_node.return_value = mock_node
            
            result = await registry.execute("test_skill", {})
            
            assert result.result.status == NodeStatus.FAILED
            assert "缺少必需参数" in result.result.error


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
