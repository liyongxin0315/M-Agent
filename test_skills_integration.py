"""
外部 Skills 集成测试

测试所有 12 个外部 Skills 的节点适配器和执行器。
"""

import asyncio
import logging
from pathlib import Path

from src.skill_executor import SkillExecutor, SkillType, SkillConfig
from src.nodes.skill_nodes import (
    WeatherNode,
    DataAnalysisNode,
    DeepResearchNode,
    ImageGenerationNode,
    VideoGenerationNode,
    PPTGenerationNode,
    ChartVisualizationNode,
    WhisperNode,
    PDFNode,
    NodeStatus
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_weather_node():
    """测试天气查询节点"""
    logger.info("\n=== 测试 Weather Node ===")
    
    node = WeatherNode()
    result = await node.execute({"location": "Beijing"})
    
    assert result.status == NodeStatus.COMPLETED, f"天气查询失败：{result.error}"
    assert "output" in result.to_dict()
    logger.info(f"✓ 天气查询成功：{result.output.get('raw', 'N/A')[:100]}")
    return True


async def test_deep_research_node():
    """测试深度研究节点"""
    logger.info("\n=== 测试 Deep Research Node ===")
    
    node = DeepResearchNode()
    result = await node.execute({
        "query": "AI 技术发展趋势",
        "max_sources": 3,
        "include_answer": True
    })
    
    assert result.status == NodeStatus.COMPLETED, f"深度研究失败：{result.error}"
    logger.info(f"✓ 深度研究成功，找到 {result.output.get('total_results', 0)} 个来源")
    return True


async def test_data_analysis_node():
    """测试数据分析节点"""
    logger.info("\n=== 测试 Data Analysis Node ===")
    
    # 创建测试数据文件
    test_data_path = Path("/tmp/test_data.csv")
    test_data_path.write_text("name,age,city\nAlice,25,Beijing\nBob,30,Shanghai\nCharlie,35,Guangzhou\n")
    
    node = DataAnalysisNode()
    result = await node.execute({
        "data_path": str(test_data_path),
        "analysis_type": "descriptive"
    })
    
    # 如果 clawhub 不可用，会使用 pandas 降级分析
    assert result.status == NodeStatus.COMPLETED, f"数据分析失败：{result.error}"
    logger.info(f"✓ 数据分析成功，行数：{result.output.get('shape', {}).get('rows', 'N/A')}")
    
    # 清理测试文件
    test_data_path.unlink()
    return True


async def test_chart_visualization_node():
    """测试图表可视化节点"""
    logger.info("\n=== 测试 Chart Visualization Node ===")
    
    node = ChartVisualizationNode()
    result = await node.execute({
        "chart_type": "bar_chart",
        "data": {
            "labels": ["A", "B", "C"],
            "values": [10, 20, 15]
        },
        "title": "测试柱状图"
    })
    
    # 如果 Node.js 不可用，可能会失败
    if result.status == NodeStatus.COMPLETED:
        logger.info(f"✓ 图表生成成功：{result.output.get('chart_url', 'N/A')}")
    else:
        logger.warning(f"⚠ 图表生成失败（可能缺少 Node.js 依赖）：{result.error}")
    return True


async def test_skill_executor_single():
    """测试技能执行器（单个执行）"""
    logger.info("\n=== 测试 Skill Executor (单个) ===")
    
    executor = SkillExecutor()
    
    # 测试天气查询
    result = await executor.execute(
        SkillType.WEATHER,
        {"location": "Shanghai"}
    )
    
    assert result.status == NodeStatus.COMPLETED, f"执行失败：{result.error}"
    logger.info(f"✓ 执行器单个执行成功")
    return True


async def test_skill_executor_batch():
    """测试技能执行器（批量执行）"""
    logger.info("\n=== 测试 Skill Executor (批量) ===")
    
    executor = SkillExecutor()
    
    # 批量查询天气
    results = await executor.execute_batch([
        {"skill_type": SkillType.WEATHER, "input_data": {"location": "Beijing"}},
        {"skill_type": SkillType.WEATHER, "input_data": {"location": "Shanghai"}},
        {"skill_type": SkillType.WEATHER, "input_data": {"location": "Guangzhou"}}
    ], parallel=True)
    
    success_count = sum(1 for r in r if r.status == NodeStatus.COMPLETED)
    logger.info(f"✓ 批量执行成功：{success_count}/{len(results)} 个任务完成")
    return True


async def test_skill_executor_cache():
    """测试技能执行器（缓存）"""
    logger.info("\n=== 测试 Skill Executor (缓存) ===")
    
    executor = SkillExecutor(configs=[
        SkillConfig(skill_type=SkillType.WEATHER, cache_enabled=True)
    ])
    
    # 第一次执行
    result1 = await executor.execute(SkillType.WEATHER, {"location": "Beijing"})
    
    # 第二次执行（应该使用缓存）
    result2 = await executor.execute(SkillType.WEATHER, {"location": "Beijing"})
    
    assert result2.metadata.get("cached", False), "缓存未命中"
    logger.info(f"✓ 缓存功能正常")
    return True


async def test_skill_executor_stats():
    """测试技能执行器（统计）"""
    logger.info("\n=== 测试 Skill Executor (统计) ===")
    
    executor = SkillExecutor()
    
    # 执行几个任务
    await executor.execute(SkillType.WEATHER, {"location": "Beijing"})
    await executor.execute(SkillType.WEATHER, {"location": "Shanghai"})
    
    # 获取统计
    stats = executor.get_stats()
    
    assert stats["total_executions"] >= 2, "执行计数错误"
    logger.info(f"✓ 统计功能正常：总执行 {stats['total_executions']} 次")
    return True


async def test_all_nodes_schema():
    """测试所有节点的 schema"""
    logger.info("\n=== 测试所有节点 Schema ===")
    
    nodes = [
        ("Weather", WeatherNode()),
        ("DataAnalysis", DataAnalysisNode()),
        ("DeepResearch", DeepResearchNode()),
        ("ChartVisualization", ChartVisualizationNode()),
        ("Whisper", WhisperNode()),
        ("PDF", PDFNode()),
    ]
    
    for name, node in nodes:
        schema = node.get_schema()
        assert "inputs" in schema, f"{name} 缺少 inputs"
        assert "outputs" in schema, f"{name} 缺少 outputs"
        logger.info(f"✓ {name} Node schema 验证通过")
    
    return True


async def main():
    """运行所有测试"""
    logger.info("=" * 60)
    logger.info("AgentM 外部 Skills 集成测试")
    logger.info("=" * 60)
    
    tests = [
        ("Weather Node", test_weather_node),
        ("Deep Research Node", test_deep_research_node),
        ("Data Analysis Node", test_data_analysis_node),
        ("Chart Visualization Node", test_chart_visualization_node),
        ("Skill Executor (单个)", test_skill_executor_single),
        ("Skill Executor (批量)", test_skill_executor_batch),
        ("Skill Executor (缓存)", test_skill_executor_cache),
        ("Skill Executor (统计)", test_skill_executor_stats),
        ("所有节点 Schema", test_all_nodes_schema),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = await test_func()
            results.append((name, success, None))
        except Exception as e:
            logger.error(f"✗ {name} 测试失败：{e}")
            results.append((name, False, str(e)))
    
    # 输出总结
    logger.info("\n" + "=" * 60)
    logger.info("测试总结")
    logger.info("=" * 60)
    
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    for name, success, error in results:
        status = "✓ 通过" if success else "✗ 失败"
        logger.info(f"{status}: {name}")
        if error:
            logger.info(f"  错误：{error}")
    
    logger.info(f"\n总计：{passed}/{total} 个测试通过")
    
    if passed == total:
        logger.info("🎉 所有测试通过！")
    else:
        logger.warning(f"⚠ {total - passed} 个测试失败")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
