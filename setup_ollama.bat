@echo off
rem M-Agent Ollama 启动脚本
rem 设置模型路径 + 启动 Ollama 服务

set OLLAMA_MODELS=D:\agentm\models
set OLLAMA_HOST=127.0.0.1:11434

echo 启动 Ollama 服务（模型目录：%OLLAMA_MODELS%）...
ollama serve
