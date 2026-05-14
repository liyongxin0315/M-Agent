#!/bin/bash

# AgentM WebUI 启动脚本

echo "🤖 AgentM WebUI 启动脚本"
echo "========================"
echo ""

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo "❌ 错误：未找到 Node.js"
    echo "请先安装 Node.js (>= 18.0.0)"
    exit 1
fi

NODE_VERSION=$(node -v)
echo "✅ Node.js 版本：$NODE_VERSION"

# 检查 npm
if ! command -v npm &> /dev/null; then
    echo "❌ 错误：未找到 npm"
    echo "请安装 npm"
    exit 1
fi

NPM_VERSION=$(npm -v)
echo "✅ npm 版本：$NPM_VERSION"

echo ""

# 进入项目目录
cd "$(dirname "$0")/vue-project"

# 检查 node_modules
if [ ! -d "node_modules" ]; then
    echo "📦 首次运行，正在安装依赖..."
    npm install
    if [ $? -ne 0 ]; then
        echo "❌ 依赖安装失败"
        exit 1
    fi
    echo "✅ 依赖安装完成"
    echo ""
fi

# 启动开发服务器
echo "🚀 启动开发服务器..."
echo "访问地址：http://localhost:5173"
echo ""

npm run dev
