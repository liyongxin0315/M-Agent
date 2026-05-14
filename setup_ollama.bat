@echo off
chcp 65001 >nul 2>&1
rem M-Agent Ollama Launcher
rem Sets model path and starts Ollama service

set OLLAMA_MODELS=D:\agentm\models
set OLLAMA_HOST=127.0.0.1:11434

echo Starting Ollama (model dir: %OLLAMA_MODELS%)...
ollama serve
