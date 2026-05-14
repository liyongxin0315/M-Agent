"""
Whisper Node - 语音识别节点

集成 openai-whisper 技能，提供语音识别能力。
"""

import logging
from typing import Any, Dict, List, Optional

from ..base_node import BaseNode, NodeResult, NodeStatus

logger = logging.getLogger(__name__)


class WhisperNode(BaseNode):
    """语音识别节点"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("whisper", config)
        self._default_model = config.get("model", "base") if config else "base"
        self._default_language = config.get("language", "zh") if config else "zh"
    
    async def execute(self, context: Dict[str, Any]) -> NodeResult:
        """
        执行语音识别
        
        Args:
            context: 执行上下文，包含:
                - audio_path: 音频文件路径
                - model: Whisper 模型
                - language: 语言代码
                - task: 任务类型 (transcribe/translate)
        
        Returns:
            NodeResult: 识别结果
        """
        try:
            audio_path = context.get("audio_path")
            model = context.get("model", self._default_model)
            language = context.get("language", self._default_language)
            task = context.get("task", "transcribe")
            
            if not audio_path:
                return NodeResult(
                    status=NodeStatus.FAILED,
                    error="缺少必需参数：audio_path",
                    node_name=self.name
                )
            
            # 调用 whisper 技能
            result = await self._transcribe(
                audio_path=audio_path,
                model=model,
                language=language,
                task=task
            )
            
            return NodeResult(
                status=NodeStatus.COMPLETED,
                output=result,
                node_name=self.name
            )
        
        except Exception as e:
            logger.error(f"语音识别失败：{e}")
            return NodeResult(
                status=NodeStatus.FAILED,
                error=str(e),
                node_name=self.name
            )
    
    async def _transcribe(
        self,
        audio_path: str,
        model: str = "base",
        language: str = "zh",
        task: str = "transcribe"
    ) -> Dict[str, Any]:
        """
        转录音频
        """
        from pathlib import Path
        
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"音频文件不存在：{audio_path}")
        
        # 尝试使用 whisper CLI
        try:
            return await self._transcribe_with_cli(str(path), model, language, task)
        except Exception as e:
            logger.warning(f"Whisper CLI 失败：{e}，尝试 Python API")
            return await self._transcribe_with_python(str(path), model, language, task)
    
    async def _transcribe_with_cli(
        self,
        audio_path: str,
        model: str,
        language: str,
        task: str
    ) -> Dict[str, Any]:
        """
        使用 Whisper CLI 转录
        """
        import subprocess
        
        cmd = [
            "whisper",
            audio_path,
            "--model", model,
            "--language", language,
            "--task", task,
            "--output_format", "json"
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 分钟超时
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Whisper CLI 失败：{result.stderr}")
        
        # 读取输出文件
        import json
        output_path = Path(audio_path).with_suffix(".json")
        
        if output_path.exists():
            with open(output_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            return {
                "text": data.get("text", ""),
                "segments": data.get("segments", []),
                "language": data.get("language", language),
                "model": model,
                "task": task
            }
        else:
            return {
                "text": result.stdout,
                "language": language,
                "model": model,
                "task": task
            }
    
    async def _transcribe_with_python(
        self,
        audio_path: str,
        model: str,
        language: str,
        task: str
    ) -> Dict[str, Any]:
        """
        使用 Whisper Python API 转录
        """
        try:
            import whisper
            
            # 加载模型
            wh_model = whisper.load_model(model)
            
            # 转录选项
            options = {
                "language": language,
                "task": task
            }
            
            # 执行转录
            result = wh_model.transcribe(audio_path, **options)
            
            return {
                "text": result.get("text", ""),
                "segments": result.get("segments", []),
                "language": result.get("language", language),
                "model": model,
                "task": task
            }
        
        except ImportError:
            raise RuntimeError("Whisper 未安装，请运行：pip install openai-whisper")
        except Exception as e:
            raise RuntimeError(f"Whisper 转录失败：{e}")
    
    def get_schema(self) -> Dict[str, Any]:
        """返回节点输入输出 schema"""
        return {
            "inputs": {
                "audio_path": {"type": "string", "required": True, "description": "音频文件路径"},
                "model": {
                    "type": "string",
                    "required": False,
                    "default": "base",
                    "enum": ["tiny", "base", "small", "medium", "large"]
                },
                "language": {
                    "type": "string",
                    "required": False,
                    "default": "zh",
                    "description": "语言代码 (zh, en, ja 等)"
                },
                "task": {
                    "type": "string",
                    "required": False,
                    "default": "transcribe",
                    "enum": ["transcribe", "translate"]
                }
            },
            "outputs": {
                "transcription": {"type": "object", "description": "转录结果"}
            }
        }
