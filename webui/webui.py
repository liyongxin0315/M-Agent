"""
AgentM Web UI - 可视化界面

使用 Flask 提供简单的 Web 界面用于工作流监控和编辑
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template_string, request, jsonify, redirect, url_for

# 导入 AgentM 模块
from config.config import get_config
from src.logging_utils import setup_logging

# 初始化日志
setup_logging()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 内存存储（实际应用中应使用数据库）
workflow_executions: List[Dict[str, Any]] = []
workflow_templates: Dict[str, Dict] = {}

# 应用启动时间
APP_START_TIME = datetime.now()


# ============ HTML 模板 ============

BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ page_title | default('AgentM Web UI') }}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { background: #2c3e50; color: white; padding: 20px; margin-bottom: 20px; }
        .header h1 { font-size: 24px; }
        .nav { display: flex; gap: 20px; margin-bottom: 20px; }
        .nav a { color: #2c3e50; text-decoration: none; padding: 10px 20px; background: white; border-radius: 5px; }
        .nav a.active { background: #3498db; color: white; }
        .card { background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .card h2 { color: #2c3e50; margin-bottom: 15px; font-size: 18px; }
        .status { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: bold; }
        .status.pending { background: #f39c12; color: white; }
        .status.running { background: #3498db; color: white; }
        .status.completed { background: #27ae60; color: white; }
        .status.failed { background: #e74c3c; color: white; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #eee; }
        th { background: #f8f9fa; font-weight: 600; }
        .btn { display: inline-block; padding: 8px 16px; background: #3498db; color: white; border: none; border-radius: 4px; cursor: pointer; text-decoration: none; }
        .btn:hover { background: #2980b9; }
        .btn-success { background: #27ae60; }
        .btn-danger { background: #e74c3c; }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; font-weight: 600; }
        .form-group input, .form-group select, .form-group textarea { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; }
        .form-group textarea { height: 200px; font-family: monospace; }
        .step { padding: 10px; margin: 5px 0; background: #f8f9fa; border-radius: 4px; border-left: 4px solid #3498db; }
        .step.completed { border-left-color: #27ae60; }
        .step.failed { border-left-color: #e74c3c; }
        .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }
        .metric { text-align: center; padding: 20px; background: #f8f9fa; border-radius: 8px; }
        .metric-value { font-size: 32px; font-weight: bold; color: #3498db; }
        .metric-label { color: #7f8c8d; margin-top: 5px; }
    </style>
</head>
<body>
    <div class="header">
        <div class="container">
            <h1>🤖 AgentM Web UI</h1>
        </div>
    </div>
    <div class="container">
        <div class="nav">
            <a href="{{ url_for('index') }}" class="{{ 'active' if request.endpoint == 'index' else '' }}">📊 仪表盘</a>
            <a href="{{ url_for('executions') }}" class="{{ 'active' if request.endpoint == 'executions' else '' }}">📋 执行历史</a>
            <a href="{{ url_for('editor') }}" class="{{ 'active' if request.endpoint == 'editor' else '' }}">✏️ 工作流编辑器</a>
            <a href="{{ url_for('api_docs') }}" class="{{ 'active' if request.endpoint == 'api_docs' else '' }}">📖 API 文档</a>
        </div>
        {% block content %}{{ content | safe }}{% endblock %}
    </div>
</body>
</html>
"""

# 页面标题常量
PAGE_TITLES = {
    'index': '仪表盘 - AgentM',
    'executions': '执行历史 - AgentM',
    'editor': '工作流编辑器 - AgentM',
    'execution_detail': '执行详情 - AgentM',
    'api_docs': 'API 文档 - AgentM'
}

INDEX_TEMPLATE = """
<div class="metrics">
    <div class="metric">
        <div class="metric-value">{{ total_executions }}</div>
        <div class="metric-label">总执行次数</div>
    </div>
    <div class="metric">
        <div class="metric-value">{{ completed_count }}</div>
        <div class="metric-label">成功</div>
    </div>
    <div class="metric">
        <div class="metric-value">{{ failed_count }}</div>
        <div class="metric-label">失败</div>
    </div>
    <div class="metric">
        <div class="metric-value">{{ avg_duration }}s</div>
        <div class="metric-label">平均耗时</div>
    </div>
</div>

<div class="card" style="margin-top: 20px;">
    <h2>🚀 快速启动</h2>
    <div style="display: flex; gap: 10px; flex-wrap: wrap;">
        <a href="{{ url_for('run_workflow', workflow_type='data_sync') }}" class="btn">数据同步</a>
        <a href="{{ url_for('run_workflow', workflow_type='scheduled_report') }}" class="btn">定时报告</a>
        <a href="{{ url_for('run_workflow', workflow_type='api_integration') }}" class="btn">API 集成</a>
        <a href="{{ url_for('run_workflow', workflow_type='ai_assistant') }}" class="btn">AI 辅助</a>
    </div>
</div>

<div class="card">
    <h2>📈 最近执行</h2>
    <table>
        <thead>
            <tr>
                <th>工作流</th>
                <th>状态</th>
                <th>开始时间</th>
                <th>耗时</th>
                <th>操作</th>
            </tr>
        </thead>
        <tbody>
            {% for exec in recent_executions %}
            <tr>
                <td>{{ exec.workflow_name }}</td>
                <td><span class="status {{ exec.status }}">{{ exec.status }}</span></td>
                <td>{{ exec.start_time }}</td>
                <td>{{ exec.total_duration }}s</td>
                <td><a href="{{ url_for('execution_detail', execution_id=exec.id) }}" class="btn">详情</a></td>
            </tr>
            {% else %}
            <tr><td colspan="5" style="text-align: center; color: #999;">暂无执行记录</td></tr>
            {% endfor %}
        </tbody>
    </table>
</div>
"""

EXECUTIONS_TEMPLATE = """
<div class="card">
    <h2>📋 执行历史</h2>
    <table>
        <thead>
            <tr>
                <th>ID</th>
                <th>工作流</th>
                <th>状态</th>
                <th>开始时间</th>
                <th>耗时</th>
                <th>操作</th>
            </tr>
        </thead>
        <tbody>
            {% for exec in executions %}
            <tr>
                <td>{{ exec.id }}</td>
                <td>{{ exec.workflow_name }}</td>
                <td><span class="status {{ exec.status }}">{{ exec.status }}</span></td>
                <td>{{ exec.start_time }}</td>
                <td>{{ exec.total_duration }}s</td>
                <td>
                    <a href="{{ url_for('execution_detail', execution_id=exec.id) }}" class="btn">详情</a>
                    <button onclick="rerunExec('{{ exec.id }}')" class="btn btn-success">重跑</button>
                </td>
            </tr>
            {% else %}
            <tr><td colspan="6" style="text-align: center; color: #999;">暂无执行记录</td></tr>
            {% endfor %}
        </tbody>
    </table>
</div>
"""

EDITOR_TEMPLATE = """
<div class="card">
    <h2>✏️ 工作流编辑器</h2>
    <form method="POST" action="{{ url_for('save_workflow') }}">
        <div class="form-group">
            <label>工作流名称</label>
            <input type="text" name="name" placeholder="输入工作流名称" required>
        </div>
        <div class="form-group">
            <label>工作流类型</label>
            <select name="type">
                <option value="custom">自定义</option>
                <option value="data_sync">数据同步</option>
                <option value="scheduled_report">定时报告</option>
                <option value="api_integration">API 集成</option>
                <option value="ai_assistant">AI 辅助</option>
            </select>
        </div>
        <div class="form-group">
            <label>配置 (JSON)</label>
            <textarea name="config" placeholder='{&#10;  "key": "value"&#10;}'></textarea>
        </div>
        <button type="submit" class="btn btn-success">保存工作流</button>
    </form>
</div>

<div class="card">
    <h2>📁 已保存的工作流</h2>
    <table>
        <thead>
            <tr>
                <th>名称</th>
                <th>类型</th>
                <th>创建时间</th>
                <th>操作</th>
            </tr>
        </thead>
        <tbody>
            {% for wf in workflows %}
            <tr>
                <td>{{ wf.name }}</td>
                <td>{{ wf.type }}</td>
                <td>{{ wf.created_at }}</td>
                <td>
                    <a href="{{ url_for('run_workflow', workflow_type='custom', workflow_id=wf.id) }}" class="btn">运行</a>
                    <button onclick="deleteWorkflow('{{ wf.id }}')" class="btn btn-danger">删除</button>
                </td>
            </tr>
            {% else %}
            <tr><td colspan="4" style="text-align: center; color: #999;">暂无保存的工作流</td></tr>
            {% endfor %}
        </tbody>
    </table>
</div>
"""

EXECUTION_DETAIL_TEMPLATE = """
<div class="card">
    <h2>📊 执行详情</h2>
    <p><strong>工作流:</strong> {{ execution.workflow_name }}</p>
    <p><strong>状态:</strong> <span class="status {{ execution.status }}">{{ execution.status }}</span></p>
    <p><strong>开始时间:</strong> {{ execution.start_time }}</p>
    <p><strong>结束时间:</strong> {{ execution.end_time or '-' }}</p>
    <p><strong>总耗时:</strong> {{ execution.total_duration }}s</p>
    {% if execution.error %}
    <p><strong>错误:</strong> <span style="color: #e74c3c;">{{ execution.error }}</span></p>
    {% endif %}
</div>

<div class="card">
    <h2>📝 步骤详情</h2>
    {% for step in execution.step_results %}
    <div class="step {{ step.status }}">
        <strong>{{ step.step_name }}</strong> - <span class="status {{ step.status }}">{{ step.status }}</span>
        {% if step.duration %}
        <span style="float: right; color: #999;">{{ step.duration }}s</span>
        {% endif %}
        {% if step.error %}
        <div style="color: #e74c3c; margin-top: 5px;">{{ step.error }}</div>
        {% endif %}
    </div>
    {% endfor %}
</div>

<div style="margin-top: 20px;">
    <a href="{{ url_for('executions') }}" class="btn">返回列表</a>
    <button onclick="rerunExec('{{ execution.id }}')" class="btn btn-success">重新执行</button>
</div>
"""

API_DOCS_TEMPLATE = """
<div class="card">
    <h2>📖 API 文档</h2>
    
    <h3 style="margin-top: 20px;">运行工作流</h3>
    <pre style="background: #f8f9fa; padding: 15px; border-radius: 4px; overflow-x: auto;">
POST /api/run
Content-Type: application/json

{
    "workflow_type": "data_sync",
    "config": {
        "source": {"type": "mysql"},
        "target": {"type": "postgres"}
    }
}</pre>

    <h3 style="margin-top: 20px;">获取执行状态</h3>
    <pre style="background: #f8f9fa; padding: 15px; border-radius: 4px; overflow-x: auto;">
GET /api/execution/&lt;id&gt;</pre>

    <h3 style="margin-top: 20px;">获取所有执行</h3>
    <pre style="background: #f8f9fa; padding: 15px; border-radius: 4px; overflow-x: auto;">
GET /api/executions</pre>

    <h3 style="margin-top: 20px;">保存工作流</h3>
    <pre style="background: #f8f9fa; padding: 15px; border-radius: 4px; overflow-x: auto;">
POST /api/workflow
Content-Type: application/json

{
    "name": "my_workflow",
    "type": "custom",
    "config": {}
}</pre>
</div>
"""


# ============ 路由 ============

# ============================================
# 健康检查端点
# ============================================

@app.route('/health')
def health_check():
    """
    健康检查端点
    
    返回系统健康状态，用于监控和负载均衡
    """
    from src.circuit_breaker import get_circuit_breaker_manager, CircuitState
    
    now = datetime.now()
    uptime = now - APP_START_TIME
    
    # 检查配置
    config_status = "healthy"
    try:
        config = get_config()
        config_status = "healthy"
    except Exception as e:
        config_status = f"unhealthy: {str(e)}"
    
    # 检查熔断器状态
    circuit_status = "healthy"
    open_circuits = 0
    try:
        cb_manager = get_circuit_breaker_manager()
        all_status = cb_manager.get_all_status()
        open_circuits = all_status["summary"]["open_count"]
        if open_circuits > 0:
            circuit_status = f"warning: {open_circuits} circuits open"
    except Exception:
        pass  # 熔断器未初始化
    
    # 检查磁盘空间
    disk_status = "healthy"
    try:
        import shutil
        total, used, free = shutil.disk_usage("/")
        free_percent = (free / total) * 100
        if free_percent < 10:
            disk_status = f"warning: {free_percent:.1f}% free"
        elif free_percent < 5:
            disk_status = f"critical: {free_percent:.1f}% free"
    except Exception:
        pass
    
    # 总体健康状态
    overall_status = "healthy"
    if "critical" in str(config_status) or "critical" in str(disk_status):
        overall_status = "critical"
    elif "warning" in str(circuit_status) or "warning" in str(disk_status):
        overall_status = "warning"
    elif "unhealthy" in str(config_status):
        overall_status = "unhealthy"
    
    # HTTP 状态码
    status_code = 200
    if overall_status == "critical":
        status_code = 503
    elif overall_status == "unhealthy":
        status_code = 500
    elif overall_status == "warning":
        status_code = 200  # warning 仍返回 200
    
    response_data = {
        "status": overall_status,
        "timestamp": now.isoformat(),
        "uptime_seconds": uptime.total_seconds(),
        "uptime_human": str(uptime),
        "version": "1.0.0",
        "checks": {
            "config": {
                "status": "pass" if config_status == "healthy" else "fail",
                "message": config_status
            },
            "circuit_breakers": {
                "status": "pass" if open_circuits == 0 else "warn",
                "open_circuits": open_circuits,
                "message": circuit_status
            },
            "disk_space": {
                "status": "pass" if "warning" not in disk_status else "warn",
                "message": disk_status
            }
        },
        "metrics": {
            "workflow_executions": len(workflow_executions),
            "workflow_templates": len(workflow_templates)
        }
    }
    
    return jsonify(response_data), status_code


@app.route('/ready')
def readiness_check():
    """
    就绪检查端点
    
    检查应用是否准备好接收流量
    """
    # 检查必要组件是否就绪
    checks_passed = True
    messages = []
    
    # 检查配置
    try:
        get_config()
        messages.append("config: ok")
    except Exception as e:
        checks_passed = False
        messages.append(f"config: {e}")
    
    # 检查日志
    try:
        logger.info("就绪检查通过")
        messages.append("logging: ok")
    except Exception as e:
        checks_passed = False
        messages.append(f"logging: {e}")
    
    status_code = 200 if checks_passed else 503
    
    return jsonify({
        "ready": checks_passed,
        "timestamp": datetime.now().isoformat(),
        "checks": messages
    }), status_code


@app.route('/live')
def liveness_check():
    """
    存活检查端点
    
    Kubernetes 存活探针使用
    """
    return jsonify({
        "alive": True,
        "timestamp": datetime.now().isoformat()
    }), 200


@app.route('/metrics')
def metrics_endpoint():
    """
    Prometheus 格式指标端点
    
    提供系统性能指标
    """
    from src.circuit_breaker import get_circuit_breaker_manager, CircuitState
    
    metrics = []
    
    # 应用指标
    uptime = (datetime.now() - APP_START_TIME).total_seconds()
    metrics.append(f'agentm_uptime_seconds {uptime}')
    metrics.append(f'agentm_workflow_executions_total {len(workflow_executions)}')
    metrics.append(f'agentm_workflow_templates_total {len(workflow_templates)}')
    
    # 熔断器指标
    try:
        cb_manager = get_circuit_breaker_manager()
        all_status = cb_manager.get_all_status()
        
        metrics.append(f'agentm_circuit_breakers_total {all_status["summary"]["total_breakers"]}')
        metrics.append(f'agentm_circuit_breakers_open {all_status["summary"]["open_count"]}')
        metrics.append(f'agentm_circuit_breakers_half_open {all_status["summary"]["half_open_count"]}')
        
        # 每个熔断器的详细指标
        for level_name, level_data in all_status.items():
            if level_name == "summary":
                continue
            for name, breaker_status in level_data.items():
                safe_name = name.replace('-', '_').replace('.', '_')
                state = breaker_status["state"]
                metrics.append(f'agentm_circuit_breaker_state{{name="{safe_name}",level="{level_name}"}} {1 if state == "closed" else 0}')
    except Exception:
        pass
    
    return '\n'.join(metrics) + '\n', 200, {'Content-Type': 'text/plain'}


# ============================================
# 页面路由
# ============================================

@app.route('/')
def index():
    """仪表盘"""
    total = len(workflow_executions)
    completed = sum(1 for e in workflow_executions if e['status'] == 'completed')
    failed = sum(1 for e in workflow_executions if e['status'] == 'failed')
    avg_duration = sum(e['total_duration'] for e in workflow_executions) / total if total > 0 else 0
    
    recent = sorted(workflow_executions, key=lambda x: x['start_time'], reverse=True)[:10]
    
    return render_template_string(
        BASE_TEMPLATE,
        page_title=PAGE_TITLES['index'],
        content=render_template_string(
            INDEX_TEMPLATE,
            total_executions=total,
            completed_count=completed,
            failed_count=failed,
            avg_duration=round(avg_duration, 2),
            recent_executions=recent
        )
    )


@app.route('/executions')
def executions():
    """执行历史"""
    sorted_execs = sorted(workflow_executions, key=lambda x: x['start_time'], reverse=True)
    return render_template_string(
        BASE_TEMPLATE,
        page_title=PAGE_TITLES['executions'],
        content=render_template_string(EXECUTIONS_TEMPLATE, executions=sorted_execs)
    )


@app.route('/execution/<execution_id>')
def execution_detail(execution_id: str):
    """执行详情"""
    for exec_data in workflow_executions:
        if exec_data['id'] == execution_id:
            return render_template_string(
                BASE_TEMPLATE,
                page_title=PAGE_TITLES['execution_detail'],
                content=render_template_string(EXECUTION_DETAIL_TEMPLATE, execution=exec_data)
            )
    return "执行记录不存在", 404


@app.route('/editor')
def editor():
    """工作流编辑器"""
    workflows_list = list(workflow_templates.values())
    return render_template_string(
        BASE_TEMPLATE,
        page_title=PAGE_TITLES['editor'],
        content=render_template_string(EDITOR_TEMPLATE, workflows=workflows_list)
    )


@app.route('/api-docs')
def api_docs():
    """API 文档"""
    return render_template_string(
        BASE_TEMPLATE,
        page_title=PAGE_TITLES['api_docs'],
        content=render_template_string(API_DOCS_TEMPLATE)
    )


@app.route('/api/run', methods=['POST'])
def api_run():
    """API: 运行工作流"""
    data = request.json
    workflow_type = data.get('workflow_type', 'custom')
    config = data.get('config', {})
    
    # 创建执行记录
    execution = {
        'id': f"exec_{len(workflow_executions) + 1}",
        'workflow_name': workflow_type,
        'status': 'completed',
        'start_time': datetime.now().isoformat(),
        'end_time': datetime.now().isoformat(),
        'total_duration': 0.5,
        'step_results': [
            {'step_name': 'init', 'status': 'completed', 'duration': 0.1},
            {'step_name': 'execute', 'status': 'completed', 'duration': 0.3},
            {'step_name': 'cleanup', 'status': 'completed', 'duration': 0.1}
        ],
        'config': config
    }
    workflow_executions.append(execution)
    
    return jsonify({'success': True, 'execution_id': execution['id']})


@app.route('/api/execution/<execution_id>')
def api_execution(execution_id: str):
    """API: 获取执行状态"""
    for exec_data in workflow_executions:
        if exec_data['id'] == execution_id:
            return jsonify(exec_data)
    return jsonify({'error': 'Not found'}), 404


@app.route('/api/executions')
def api_executions():
    """API: 获取所有执行"""
    return jsonify(workflow_executions)


@app.route('/api/workflow', methods=['POST'])
def api_save_workflow():
    """API: 保存工作流"""
    data = request.json
    workflow_id = f"wf_{len(workflow_templates) + 1}"
    
    workflow_templates[workflow_id] = {
        'id': workflow_id,
        'name': data.get('name', 'Unnamed'),
        'type': data.get('type', 'custom'),
        'config': data.get('config', {}),
        'created_at': datetime.now().isoformat()
    }
    
    return jsonify({'success': True, 'workflow_id': workflow_id})


@app.route('/api/workflow/<workflow_id>', methods=['DELETE'])
def api_delete_workflow(workflow_id: str):
    """API: 删除工作流"""
    if workflow_id in workflow_templates:
        del workflow_templates[workflow_id]
        return jsonify({'success': True})
    return jsonify({'error': 'Not found'}), 404


@app.route('/run/<workflow_type>')
def run_workflow(workflow_type: str):
    """运行工作流"""
    workflow_id = request.args.get('workflow_id')
    config = {}
    
    if workflow_id and workflow_id in workflow_templates:
        config = workflow_templates[workflow_id].get('config', {})
    
    # 创建执行记录
    execution = {
        'id': f"exec_{len(workflow_executions) + 1}",
        'workflow_name': workflow_type,
        'status': 'completed',
        'start_time': datetime.now().isoformat(),
        'end_time': datetime.now().isoformat(),
        'total_duration': 1.0,
        'step_results': [
            {'step_name': 'validate', 'status': 'completed', 'duration': 0.2},
            {'step_name': 'execute', 'status': 'completed', 'duration': 0.6},
            {'step_name': 'verify', 'status': 'completed', 'duration': 0.2}
        ]
    }
    workflow_executions.append(execution)
    
    return redirect(url_for('execution_detail', execution_id=execution['id']))


@app.route('/save_workflow', methods=['POST'])
def save_workflow():
    """保存工作流"""
    name = request.form.get('name', 'Unnamed')
    workflow_type = request.form.get('type', 'custom')
    
    try:
        config = json.loads(request.form.get('config', '{}'))
    except json.JSONDecodeError:
        config = {}
    
    workflow_id = f"wf_{len(workflow_templates) + 1}"
    workflow_templates[workflow_id] = {
        'id': workflow_id,
        'name': name,
        'type': workflow_type,
        'config': config,
        'created_at': datetime.now().isoformat()
    }
    
    return redirect(url_for('editor'))


# ============ 主程序 ============

def main():
    """启动 Web UI"""
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'false').lower() == 'true'
    
    logger.info(f"🚀 启动 AgentM Web UI on http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=debug)


if __name__ == '__main__':
    main()
