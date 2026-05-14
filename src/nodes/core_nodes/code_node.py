"""
Code Node - 代码执行节点

执行 Python 或 JavaScript 代码。
"""

import logging
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..base_node import BaseNode, NodeResult, NodeStatus

logger = logging.getLogger(__name__)


@dataclass
class CodeConfig:
    """代码配置"""
    language: str = "python"
    code: str = ""
    timeout: float = 30.0
    sandbox: bool = True


class CodeNode(BaseNode):
    """代码执行节点"""
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.code_config = self._parse_config(config or {})
    
    def _parse_config(self, config: Dict[str, Any]) -> CodeConfig:
        """解析配置"""
        return CodeConfig(
            language=config.get("language", "python"),
            code=config.get("code", ""),
            timeout=config.get("timeout", 30.0),
            sandbox=config.get("sandbox", True)
        )
    
    async def execute(self, context: Dict[str, Any]) -> NodeResult:
        """执行代码"""
        try:
            code = context.get("code", self.code_config.code)
            language = context.get("language", self.code_config.language)
            timeout = context.get("timeout", self.code_config.timeout)
            
            if not code:
                return NodeResult(
                    status=NodeStatus.FAILED,
                    node_name=self.name,
                    error="未提供代码"
                )
            
            if language == "python":
                return await self._execute_python(code, context, timeout)
            elif language == "javascript" or language == "js":
                return await self._execute_javascript(code, context, timeout)
            else:
                return NodeResult(
                    status=NodeStatus.FAILED,
                    node_name=self.name,
                    error=f"不支持的语言：{language}"
                )
        
        except subprocess.TimeoutExpired:
            return NodeResult(
                status=NodeStatus.FAILED,
                node_name=self.name,
                error=f"代码执行超时（{self.code_config.timeout}秒）"
            )
        except Exception as e:
            return NodeResult(
                status=NodeStatus.FAILED,
                node_name=self.name,
                error=f"代码执行失败：{e}"
            )
    
    async def _execute_python(
        self,
        code: str,
        context: Dict[str, Any],
        timeout: float
    ) -> NodeResult:
        """执行 Python 代码"""
        wrapped_code = self._wrap_python_code(code, context)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(wrapped_code)
            script_path = f.name
        
        try:
            result = subprocess.run(
                ["python3", script_path],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if result.returncode != 0:
                return NodeResult(
                    status=NodeStatus.FAILED,
                    node_name=self.name,
                    error=result.stderr.strip()
                )
            
            output = self._parse_python_output(result.stdout)
            
            return NodeResult(
                status=NodeStatus.COMPLETED,
                node_name=self.name,
                output=output
            )
        
        finally:
            import os
            try:
                os.unlink(script_path)
            except Exception:
                pass
    
    async def _execute_javascript(
        self,
        code: str,
        context: Dict[str, Any],
        timeout: float
    ) -> NodeResult:
        """执行 JavaScript 代码"""
        wrapped_code = self._wrap_javascript_code(code, context)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write(wrapped_code)
            script_path = f.name
        
        try:
            result = subprocess.run(
                ["node", script_path],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if result.returncode != 0:
                return NodeResult(
                    status=NodeStatus.FAILED,
                    node_name=self.name,
                    error=result.stderr.strip()
                )
            
            output = self._parse_javascript_output(result.stdout)
            
            return NodeResult(
                status=NodeStatus.COMPLETED,
                node_name=self.name,
                output=output
            )
        
        finally:
            import os
            try:
                os.unlink(script_path)
            except Exception:
                pass
    
    def _wrap_python_code(self, code: str, context: Dict[str, Any]) -> str:
        """包装 Python 代码"""
        context_json = str(context)
        
        return f"""
import json
import sys

# 上下文数据
context = {context_json}

# 用户代码
def main():
{chr(10).join('    ' + line for line in code.split(chr(10)))}

if __name__ == "__main__":
    try:
        result = main()
        if result is not None:
            print(json.dumps(result, ensure_ascii=False, default=str))
    except Exception as e:
        print(f"ERROR: {{e}}", file=sys.stderr)
        sys.exit(1)
"""
    
    def _wrap_javascript_code(self, code: str, context: Dict[str, Any]) -> str:
        """包装 JavaScript 代码"""
        context_json = str(context).replace("'", '"')
        
        return f"""
const context = {context_json};

(async () => {{
    try {{
        {code}
    }} catch (error) {{
        console.error('ERROR:', error.message);
        process.exit(1);
    }}
}})();
"""
    
    def _parse_python_output(self, output: str) -> Any:
        """解析 Python 输出"""
        try:
            return json.loads(output)
        except Exception:
            return {"output": output.strip()}
    
    def _parse_javascript_output(self, output: str) -> Any:
        """解析 JavaScript 输出"""
        try:
            return json.loads(output)
        except Exception:
            return {"output": output.strip()}
    
    def get_schema(self) -> Dict[str, Any]:
        """获取节点 schema"""
        return {
            "name": "code",
            "description": "执行代码",
            "inputs": {
                "language": {
                    "type": "string",
                    "required": True,
                    "enum": ["python", "javascript"],
                    "description": "编程语言"
                },
                "code": {
                    "type": "string",
                    "required": True,
                    "description": "要执行的代码"
                },
                "timeout": {
                    "type": "number",
                    "required": False,
                    "default": 30.0,
                    "description": "超时时间（秒）"
                }
            },
            "outputs": {
                "result": {
                    "type": "any",
                    "description": "执行结果"
                }
            }
        }
