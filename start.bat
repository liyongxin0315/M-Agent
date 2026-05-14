@echo off
rem M-Agent 快速启动脚本
rem 使用方法：双击运行此文件

echo ========================================
echo M-Agent 启动器
echo ========================================
echo.

rem 检查 Ollama 是否运行
echo [1/4] 检查 Ollama 服务...
ollama list >nul 2>&1
if %errorlevel% neq 0 (
    echo Ollama 未运行，正在启动...
    start /min cmd /c "ollama serve"
    timeout /t 3 /nobreak >nul
)
echo Ollama 已就绪
echo.

rem 检查 API 是否已安装依赖
echo [2/4] 检查依赖...
python -c "import agentm" 2>nul
if %errorlevel% neq 0 (
    echo 依赖未安装，正在安装...
    pip install -e D:\agentm -q
)
echo 依赖就绪
echo.

rem 启动 API
echo [3/4] 启动 API 服务 (端口 8766)...
cd /d D:\agentm
start "M-Agent API" cmd /c "python -m agentm.interfaces.api.main"
timeout /t 2 /nobreak >nul
echo API 已启动
echo.

rem 打开浏览器
echo [4/4] 打开浏览器...
start http://localhost:8766

echo.
echo ========================================
echo M-Agent 已启动！
echo API: http://localhost:8766
echo ========================================
pause
