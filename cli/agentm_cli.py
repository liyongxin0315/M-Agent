#!/usr/bin/env python3
"""
AgentM CLI - 命令行工具

提供快速访问 AgentM 功能的命令行接口
"""

import argparse
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


def cmd_status(args):
    """查看系统状态"""
    from config.config import get_config
    from src.circuit_breaker import get_circuit_breaker_manager
    
    config = get_config()
    print("AgentM 状态")
    print("=" * 40)
    print(f"环境：{config.environment.value}")
    print(f"日志级别：{config.log.level}")
    print(f"WebUI 端口：{config.webui.port}")
    print()
    
    # 熔断器状态
    try:
        cb = get_circuit_breaker_manager()
        status = cb.get_all_status()
        print(f"熔断器：{status['summary']['total_breakers']} 个")
        print(f"  - 打开：{status['summary']['open_count']}")
        print(f"  - 半开：{status['summary']['half_open_count']}")
    except Exception:
        print("熔断器：未初始化")


def cmd_run(args):
    """运行工作流"""
    print(f"运行工作流：{args.workflow}")
    # TODO: 实现工作流运行逻辑


def cmd_search(args):
    """搜索知识库"""
    import asyncio
    from tools.kb_manager import KnowledgeBaseManager
    
    async def search():
        kb = KnowledgeBaseManager()
        await kb.initialize()
        results = await kb.search(args.query, top_k=args.top_k)
        
        print(f"\n搜索结果 ({len(results)} 条):\n")
        for i, r in enumerate(results, 1):
            print(f"[{i}] 分数：{r['score']:.4f}")
            print(f"    {r['content'][:150]}...\n")
        
        await kb.close()
    
    asyncio.run(search())


def cmd_skills(args):
    """管理 Skills"""
    from src.skill_integration import get_registry, register_builtin_skills
    
    registry = get_registry()
    register_builtin_skills(registry)
    
    if args.command == 'list':
        skills = registry.list_skills()
        print(f"\n已注册 Skills ({len(skills)}):\n")
        for skill in skills:
            status = "✅" if skill.enabled else "❌"
            print(f"  {status} {skill.name}")


def cmd_health(args):
    """健康检查"""
    import urllib.request
    import json
    
    url = f"http://localhost:{args.port}/health"
    
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            data = json.loads(response.read())
            print(f"状态：{data['status']}")
            print(f"运行时间：{data['uptime_human']}")
            print(f"版本：{data['version']}")
            
            for check, info in data['checks'].items():
                status = "✅" if info['status'] == 'pass' else "❌"
                print(f"  {status} {check}: {info['message']}")
    except Exception as e:
        print(f"健康检查失败：{e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='AgentM CLI - 命令行工具',
        prog='agentm'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='命令')
    
    # status 命令
    status_parser = subparsers.add_parser('status', help='查看系统状态')
    status_parser.set_defaults(func=cmd_status)
    
    # run 命令
    run_parser = subparsers.add_parser('run', help='运行工作流')
    run_parser.add_argument('workflow', help='工作流名称')
    run_parser.set_defaults(func=cmd_run)
    
    # search 命令
    search_parser = subparsers.add_parser('search', help='搜索知识库')
    search_parser.add_argument('query', help='搜索查询')
    search_parser.add_argument('-k', '--top-k', type=int, default=5, help='返回数量')
    search_parser.set_defaults(func=cmd_search)
    
    # skills 命令
    skills_parser = subparsers.add_parser('skills', help='管理 Skills')
    skills_parser.add_argument('command', choices=['list', 'info'], help='子命令')
    skills_parser.set_defaults(func=cmd_skills)
    
    # health 命令
    health_parser = subparsers.add_parser('health', help='健康检查')
    health_parser.add_argument('-p', '--port', type=int, default=5000, help='WebUI 端口')
    health_parser.set_defaults(func=cmd_health)
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        sys.exit(1)
    
    args.func(args)


if __name__ == '__main__':
    main()
