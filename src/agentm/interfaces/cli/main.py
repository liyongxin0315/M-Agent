"""
M-Agent 命令行入口

用法：
  python -m agentm.interfaces.cli.main "帮我写一个快排"
"""

from __future__ import annotations

import sys
import time
from loguru import logger

# 配置日志
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | <level>{message}</level>",
    level="INFO",
)

from agentm.agents import get_executor


def main():
    if len(sys.argv) < 2:
        print("用法: python -m agentm.interfaces.cli.main \"你的任务\"")
        print("示例: python -m agentm.interfaces.cli.main \"帮我写一个快排\"")
        sys.exit(1)

    prompt = " ".join(sys.argv[1:])

    print(f"\n{'='*60}")
    print(f"M-Agent 执行任务")
    print(f"{'='*60}\n")
    print(f"任务: {prompt}\n")

    executor = get_executor()

    # 流式输出
    result = None
    for chunk in executor.execute_stream(prompt):
        if isinstance(chunk, str):
            print(chunk, end="", flush=True)
        else:
            result = chunk

    if result is None:
        logger.error("执行异常，未获得结果")
        sys.exit(1)

    # 最终状态码
    if result.verdict == "pass":
        logger.info("任务完成：代码验证通过")
        sys.exit(0)
    elif result.verdict == "fail":
        logger.warning("任务完成：代码存在缺陷")
        sys.exit(1)
    else:
        logger.warning(f"任务完成：无法判定（{result.verdict}）")
        sys.exit(2)


if __name__ == "__main__":
    main()
