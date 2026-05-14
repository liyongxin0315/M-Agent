"""
M-Agent 环境验证脚本

运行方法：
  python D:\agentm\verify_setup.py

检查内容：
  1. Python 依赖
  2. Ollama 服务
  3. 模型下载
  4. API 可启动
"""

import subprocess
import sys
from pathlib import Path


def check_python_deps():
    """检查 Python 依赖"""
    print("\n[1/4] 检查 Python 依赖...")
    required = [
        "fastapi",
        "uvicorn",
        "loguru",
        "tenacity",
        "chromadb",
        "sentence_transformers",
        "z3-solver",
        "ollama",
        "pydantic",
    ]
    missing = []
    for pkg in required:
        try:
            __import__(pkg.replace("-", "_"))
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"  ❌ 缺少依赖: {', '.join(missing)}")
        print(f"  → 运行: pip install -e D:\\agentm")
        return False
    print("  ✅ 所有依赖已安装")
    return True


def check_ollama():
    """检查 Ollama 服务"""
    print("\n[2/4] 检查 Ollama 服务...")
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            print("  ✅ Ollama 服务正常")
            # 检查模型
            lines = result.stdout.strip().split("\n")
            models = [l for l in lines[1:] if l.strip()]
            print(f"  已安装模型: {len(models)} 个")
            for m in models[:5]:
                print(f"    - {m.split()[0]}")
            return True
        else:
            print("  ❌ Ollama 未运行")
            return False
    except Exception as e:
        print(f"  ❌ Ollama 检查失败: {e}")
        return False


def check_models():
    """检查模型是否下载"""
    print("\n[3/4] 检查模型...")
    required_models = ["qwen3", "deepseek-coder"]
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        installed = result.stdout.lower()
        missing = []
        for m in required_models:
            if m not in installed:
                missing.append(m)

        if missing:
            print(f"  ⚠️  缺少模型: {', '.join(missing)}")
            print(f"  → 运行:")
            for m in missing:
                print(f"      ollama pull {m}")
            return False
        print("  ✅ 所有模型已就绪")
        return True
    except Exception as e:
        print(f"  ❌ 模型检查失败: {e}")
        return False


def check_api():
    """检查 API 能否启动（不阻塞测试）"""
    print("\n[4/4] 检查 API 模块...")
    try:
        # 尝试导入
        from agentm.interfaces.api.main import app
        from fastapi.testclient import TestClient

        # 简单健康检查
        client = TestClient(app)
        response = client.get("/")
        if response.status_code == 200:
            print("  ✅ API 模块正常")
            return True
        else:
            print(f"  ⚠️  API 返回 {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ API 模块异常: {e}")
        return False


def main():
    print("=" * 50)
    print("M-Agent 环境验证")
    print("=" * 50)

    results = {
        "Python 依赖": check_python_deps(),
        "Ollama 服务": check_ollama(),
        "模型": check_models(),
        "API 模块": check_api(),
    }

    print("\n" + "=" * 50)
    print("验证结果")
    print("=" * 50)
    for name, ok in results.items():
        status = "✅" if ok else "❌"
        print(f"  {status} {name}")

    all_ok = all(results.values())
    print()
    if all_ok:
        print("✅ 所有检查通过！可以启动 M-Agent：")
        print("   python -m agentm.interfaces.api.main")
    else:
        print("⚠️  部分检查失败，请先修复上述问题")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
