#!/usr/bin/env python3
"""
外部 Skills 快速入门示例

演示如何使用统一的 SkillExecutor 调用 12 个外部 Skills。
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from src.skill_executor import SkillExecutor, SkillType


async def demo_weather():
    """演示天气查询"""
    print("\n" + "="*60)
    print("🌤️  演示：天气查询")
    print("="*60)
    
    executor = SkillExecutor()
    result = await executor.execute(SkillType.WEATHER, {"location": "Beijing"})
    
    if result.status.value == "completed":
        print(f"✅ 北京天气查询成功")
        print(f"   数据：{str(result.output)[:200]}...")
    else:
        print(f"❌ 查询失败：{result.error}")


async def demo_research():
    """演示深度研究"""
    print("\n" + "="*60)
    print("🔍 演示：深度研究")
    print("="*60)
    
    executor = SkillExecutor()
    result = await executor.execute(
        SkillType.DEEP_RESEARCH,
        {
            "query": "AI 技术发展趋势",
            "max_sources": 3,
            "include_answer": True
        }
    )
    
    if result.status.value == "completed":
        print(f"✅ 深度研究完成")
        print(f"   找到 {result.output.get('total_results', 0)} 个来源")
        if result.output.get('answer'):
            print(f"   AI 总结：{result.output['answer'][:200]}...")
    else:
        print(f"❌ 研究失败：{result.error}")


async def demo_batch():
    """演示批量执行"""
    print("\n" + "="*60)
    print("⚡ 演示：批量执行（并行查询多个城市天气）")
    print("="*60)
    
    executor = SkillExecutor()
    results = await executor.execute_batch([
        {"skill_type": SkillType.WEATHER, "input_data": {"location": "Beijing"}},
        {"skill_type": SkillType.WEATHER, "input_data": {"location": "Shanghai"}},
        {"skill_type": SkillType.WEATHER, "input_data": {"location": "Guangzhou"}},
    ], parallel=True)
    
    success_count = sum(1 for r in results if r.status.value == "completed")
    print(f"✅ 批量执行完成：{success_count}/{len(results)} 成功")
    
    for i, result in enumerate(results, 1):
        if result.status.value == "completed":
            print(f"   城市 {i}: 成功")
        else:
            print(f"   城市 {i}: 失败 - {result.error}")


async def demo_cache():
    """演示缓存功能"""
    print("\n" + "="*60)
    print("💾 演示：缓存功能")
    print("="*60)
    
    executor = SkillExecutor(configs=[
        {"skill_type": SkillType.WEATHER, "cache_enabled": True}
    ])
    
    # 第一次执行
    print("   第一次查询（无缓存）...")
    result1 = await executor.execute(SkillType.WEATHER, {"location": "Beijing"})
    
    # 第二次执行（使用缓存）
    print("   第二次查询（使用缓存）...")
    result2 = await executor.execute(SkillType.WEATHER, {"location": "Beijing"})
    
    if result2.metadata.get("cached", False):
        print(f"✅ 缓存命中！第二次查询使用了缓存结果")
    else:
        print(f"⚠️  缓存未命中")


async def demo_stats():
    """演示统计功能"""
    print("\n" + "="*60)
    print("📊 演示：执行统计")
    print("="*60)
    
    executor = SkillExecutor()
    
    # 执行几个任务
    await executor.execute(SkillType.WEATHER, {"location": "Beijing"})
    await executor.execute(SkillType.WEATHER, {"location": "Shanghai"})
    
    # 获取统计
    stats = executor.get_stats()
    
    print(f"✅ 执行统计:")
    print(f"   总执行次数：{stats['total_executions']}")
    print(f"   缓存大小：{stats['cache_size']}")
    print(f"   各技能执行情况:")
    for skill_name, skill_stats in stats['skills'].items():
        print(f"     - {skill_name}: {skill_stats['successful']}/{skill_stats['total']} 成功")


async def main():
    """主函数"""
    print("\n" + "🚀 " * 20)
    print("AgentM 外部 Skills 快速入门演示")
    print("🚀 " * 20)
    
    demos = [
        ("天气查询", demo_weather),
        ("深度研究", demo_research),
        ("批量执行", demo_batch),
        ("缓存功能", demo_cache),
        ("执行统计", demo_stats),
    ]
    
    for name, demo_func in demos:
        try:
            await demo_func()
        except Exception as e:
            print(f"\n❌ {name} 演示失败：{e}")
    
    print("\n" + "="*60)
    print("✅ 所有演示完成！")
    print("="*60)
    print("\n📖 更多信息请查看：SKILLS_INTEGRATION_GUIDE.md")
    print("🔧 运行测试：python test_skills_integration.py\n")


if __name__ == "__main__":
    asyncio.run(main())
