@echo off
chcp 65001 >nul 2>&1
echo ========================================
echo M-Agent Launcher
echo ========================================
echo.

echo [1/4] Checking Ollama...
ollama list >nul 2>&1
if errorlevel 1 (
    echo Ollama not running, starting...
    start /min cmd /c "ollama serve"
    timeout /t 3 /nobreak >nul
)
echo Ollama OK
echo.

echo [2/4] Checking dependencies...
python -c "import agentm" 2>nul
if errorlevel 1 (
    echo Installing dependencies...
    pip install -e D:\agentm -q
)
echo Dependencies OK
echo.

echo [3/4] Starting API on port 8766...
cd /d D:\agentm
start "M-Agent API" cmd /c "python -m agentm.interfaces.api.main"
timeout /t 2 /nobreak >nul
echo API started
echo.

echo [4/4] Opening browser...
start http://localhost:8766

echo.
echo ========================================
echo M-Agent started!
echo API: http://localhost:8766
echo ========================================
pause
