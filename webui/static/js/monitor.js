/**
 * AgentM 实时监控模块
 * 使用 WebSocket 实现实时数据推送
 * 使用 Chart.js 实现数据可视化
 */

// ============ 全局变量 ============
let socket = null;
let cpuChart = null;
let memoryChart = null;
let performanceChart = null;
let workflowNodes = [];
let currentNodeId = null;
let logData = [];

// ============ WebSocket 连接 ============
function connectWebSocket() {
    const wsUrl = `ws://${window.location.host}/ws`;
    socket = new WebSocket(wsUrl);
    
    socket.onopen = function() {
        console.log('WebSocket 连接成功');
        updateConnectionStatus(true);
        // 开始订阅系统指标
        socket.send(JSON.stringify({ action: 'subscribe', channels: ['cpu', 'memory', 'workflow'] }));
    };
    
    socket.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            handleWebSocketMessage(data);
        } catch (e) {
            console.error('解析 WebSocket 消息失败:', e);
        }
    };
    
    socket.onclose = function() {
        console.log('WebSocket 连接关闭');
        updateConnectionStatus(false);
        // 5 秒后重连
        setTimeout(connectWebSocket, 5000);
    };
    
    socket.onerror = function(error) {
        console.error('WebSocket 错误:', error);
        updateConnectionStatus(false);
    };
}

function handleWebSocketMessage(data) {
    switch (data.type) {
        case 'cpu':
            updateCpuMetrics(data.value);
            break;
        case 'memory':
            updateMemoryMetrics(data.value);
            break;
        case 'workflow':
            updateWorkflowStats(data.value);
            break;
        case 'log':
            addLogEntry(data.value);
            break;
        case 'circuit':
            updateCircuitStatus(data.value);
            break;
        case 'execution':
            updateExecutionHistory(data.value);
            break;
    }
}

function updateConnectionStatus(connected) {
    const dot = document.getElementById('wsStatus');
    const text = document.getElementById('wsStatusText');
    
    if (connected) {
        dot.classList.remove('disconnected');
        text.textContent = '已连接';
    } else {
        dot.classList.add('disconnected');
        text.textContent = '已断开';
    }
}

// ============ CPU 监控 ============
function initCpuChart() {
    const ctx = document.getElementById('cpuChart').getContext('2d');
    cpuChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'CPU 使用率 (%)',
                data: [],
                borderColor: '#00d2ff',
                backgroundColor: 'rgba(0, 210, 255, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 0 },
            scales: {
                x: { display: false },
                y: { 
                    beginAtZero: true, 
                    max: 100,
                    grid: { color: 'rgba(255,255,255,0.1)' },
                    ticks: { color: '#a0a0a0' }
                }
            },
            plugins: { legend: { display: false } }
        }
    });
}

function updateCpuMetrics(data) {
    const value = data.percent || 0;
    const timestamp = new Date().toLocaleTimeString();
    
    // 更新数值显示
    document.getElementById('cpuValue').textContent = value.toFixed(1) + '%';
    document.getElementById('cpuBar').style.width = value + '%';
    
    // 更新图表
    if (cpuChart) {
        cpuChart.data.labels.push(timestamp);
        cpuChart.data.datasets[0].data.push(value);
        
        // 保持最近 30 个数据点
        if (cpuChart.data.labels.length > 30) {
            cpuChart.data.labels.shift();
            cpuChart.data.datasets[0].data.shift();
        }
        cpuChart.update();
    }
}

// ============ 内存监控 ============
function initMemoryChart() {
    const ctx = document.getElementById('memoryChart').getContext('2d');
    memoryChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: '内存使用率 (%)',
                data: [],
                borderColor: '#f5576c',
                backgroundColor: 'rgba(245, 87, 108, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 0 },
            scales: {
                x: { display: false },
                y: { 
                    beginAtZero: true, 
                    max: 100,
                    grid: { color: 'rgba(255,255,255,0.1)' },
                    ticks: { color: '#a0a0a0' }
                }
            },
            plugins: { legend: { display: false } }
        }
    });
}

function updateMemoryMetrics(data) {
    const percent = data.percent || 0;
    const used = data.used || 0;
    const total = data.total || 0;
    const timestamp = new Date().toLocaleTimeString();
    
    // 更新数值显示
    document.getElementById('memoryValue').textContent = percent.toFixed(1) + '%';
    document.getElementById('memoryUsed').textContent = (used / 1024 / 1024 / 1024).toFixed(2);
    document.getElementById('memoryTotal').textContent = (total / 1024 / 1024 / 1024).toFixed(0);
    document.getElementById('memoryBar').style.width = percent + '%';
    
    // 更新图表
    if (memoryChart) {
        memoryChart.data.labels.push(timestamp);
        memoryChart.data.datasets[0].data.push(percent);
        
        if (memoryChart.data.labels.length > 30) {
            memoryChart.data.labels.shift();
            memoryChart.data.datasets[0].data.shift();
        }
        memoryChart.update();
    }
}

// ============ 性能趋势图表 ============
function initPerformanceChart() {
    const ctx = document.getElementById('performanceChart').getContext('2d');
    performanceChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'CPU (%)',
                    data: [],
                    borderColor: '#00d2ff',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.4,
                    pointRadius: 0
                },
                {
                    label: '内存 (%)',
                    data: [],
                    borderColor: '#f5576c',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.4,
                    pointRadius: 0
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 0 },
            scales: {
                x: { 
                    grid: { color: 'rgba(255,255,255,0.1)' },
                    ticks: { color: '#a0a0a0', maxTicksLimit: 10 }
                },
                y: { 
                    beginAtZero: true, 
                    max: 100,
                    grid: { color: 'rgba(255,255,255,0.1)' },
                    ticks: { color: '#a0a0a0' }
                }
            },
            plugins: { 
                legend: { 
                    labels: { color: '#a0a0a0' }
                }
            }
        }
    });
}

function updatePerformanceChart(cpu, memory) {
    const timestamp = new Date().toLocaleTimeString();
    
    if (performanceChart) {
        performanceChart.data.labels.push(timestamp);
        performanceChart.data.datasets[0].data.push(cpu);
        performanceChart.data.datasets[1].data.push(memory);
        
        if (performanceChart.data.labels.length > 50) {
            performanceChart.data.labels.shift();
            performanceChart.data.datasets[0].data.shift();
            performanceChart.data.datasets[1].data.shift();
        }
        performanceChart.update();
    }
}

// ============ 工作流统计 ============
function updateWorkflowStats(data) {
    document.getElementById('totalExecutions').textContent = data.total || 0;
    document.getElementById('completedCount').textContent = data.completed || 0;
    document.getElementById('failedCount').textContent = data.failed || 0;
    
    const successRate = data.total > 0 ? ((data.completed || 0) / data.total * 100) : 0;
    document.getElementById('successRate').textContent = successRate.toFixed(1) + '%';
    document.getElementById('successBar').style.width = successRate + '%';
    
    document.getElementById('activeWorkflows').textContent = data.active || 0;
    document.getElementById('queuedTasks').textContent = data.queued || 0;
    document.getElementById('avgResponse').textContent = (data.avgResponse || 0).toFixed(0) + 'ms';
}

// ============ 执行历史 ============
function loadExecutionHistory() {
    fetch('/api/executions')
        .then(response => response.json())
        .then(data => {
            updateExecutionHistory(data);
        })
        .catch(error => {
            console.error('加载执行历史失败:', error);
        });
}

function updateExecutionHistory(executions) {
    const tbody = document.getElementById('executionHistoryBody');
    if (!executions || executions.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #666;">暂无执行记录</td></tr>';
        return;
    }
    
    const sorted = executions.slice().sort((a, b) => {
        return new Date(b.start_time) - new Date(a.start_time);
    }).slice(0, 50);
    
    tbody.innerHTML = sorted.map(exec => `
        <tr>
            <td>${exec.id}</td>
            <td>${exec.workflow_name}</td>
            <td><span class="status-badge ${exec.status}">${exec.status}</span></td>
            <td>${new Date(exec.start_time).toLocaleString()}</td>
            <td>${(exec.total_duration || 0).toFixed(2)}s</td>
            <td>
                <button class="btn btn-primary" onclick="viewExecution('${exec.id}')" style="padding: 4px 8px; font-size: 11px;">详情</button>
                <button class="btn btn-success" onclick="rerunExecution('${exec.id}')" style="padding: 4px 8px; font-size: 11px;">重跑</button>
            </td>
        </tr>
    `).join('');
}

function viewExecution(executionId) {
    window.location.href = `/execution/${executionId}`;
}

function rerunExecution(executionId) {
    if (confirm('确定要重新执行这个工作流吗？')) {
        fetch(`/api/execution/${executionId}/rerun`, { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('工作流已重新执行');
                    loadExecutionHistory();
                } else {
                    alert('重跑失败：' + (data.error || '未知错误'));
                }
            })
            .catch(error => {
                alert('重跑失败：' + error);
            });
    }
}

// ============ 错误日志 ============
function loadLogs() {
    fetch('/api/logs?limit=100')
        .then(response => response.json())
        .then(data => {
            logData = data.logs || [];
            renderLogs(logData);
        })
        .catch(error => {
            console.error('加载日志失败:', error);
            document.getElementById('errorLogContainer').innerHTML = 
                '<div style="color: #e74c3c; text-align: center;">加载日志失败</div>';
        });
}

function renderLogs(logs) {
    const container = document.getElementById('errorLogContainer');
    const filter = document.getElementById('logLevelFilter').value;
    
    const filteredLogs = filter === 'all' 
        ? logs 
        : logs.filter(log => log.level === filter);
    
    if (filteredLogs.length === 0) {
        container.innerHTML = '<div style="color: #666; text-align: center;">暂无日志</div>';
        return;
    }
    
    container.innerHTML = filteredLogs.map(log => `
        <div class="log-entry ${log.level.toLowerCase()}">
            <span class="log-timestamp">${new Date(log.timestamp).toLocaleString()}</span>
            <span class="log-level ${log.level}">${log.level}</span>
            <span class="log-message">${escapeHtml(log.message)}</span>
        </div>
    `).join('');
}

function filterLogs() {
    renderLogs(logData);
}

function clearLogs() {
    if (confirm('确定要清空所有日志吗？')) {
        fetch('/api/logs', { method: 'DELETE' })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    logData = [];
                    renderLogs([]);
                }
            })
            .catch(error => {
                console.error('清空日志失败:', error);
            });
    }
}

function addLogEntry(log) {
    logData.push(log);
    if (logData.length > 1000) {
        logData.shift();
    }
    renderLogs(logData);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============ 熔断器状态 ============
function loadCircuitStatus() {
    fetch('/api/circuit-breaker/status')
        .then(response => response.json())
        .then(data => {
            updateCircuitStatus(data);
        })
        .catch(error => {
            console.error('加载熔断器状态失败:', error);
        });
}

function updateCircuitStatus(data) {
    const circuits = data.circuits || {};
    
    for (const [name, status] of Object.entries(circuits)) {
        const element = document.getElementById(`circuit-${name}`);
        const failuresElement = document.getElementById(`failures-${name}`);
        const thresholdElement = document.getElementById(`threshold-${name}`);
        
        if (element) {
            element.className = `circuit-state ${status.state.toLowerCase()}`;
            element.textContent = status.state;
        }
        if (failuresElement) {
            failuresElement.textContent = status.failures || 0;
        }
        if (thresholdElement) {
            thresholdElement.textContent = status.threshold || 5;
        }
    }
}

function saveCircuitConfig() {
    const config = {
        failureThreshold: parseInt(document.getElementById('failureThreshold').value),
        recoveryTimeout: parseInt(document.getElementById('recoveryTimeout').value),
        halfOpenMax: parseInt(document.getElementById('halfOpenMax').value),
        successThreshold: parseInt(document.getElementById('successThreshold').value)
    };
    
    fetch('/api/circuit-breaker/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('配置已保存');
        } else {
            alert('保存失败：' + (data.error || '未知错误'));
        }
    })
    .catch(error => {
        alert('保存失败：' + error);
    });
}

// ============ 工作流编辑器 ============
function initWorkflowEditor() {
    // 拖拽事件
    document.querySelectorAll('.palette-node').forEach(node => {
        node.addEventListener('dragstart', handleDragStart);
    });
}

function handleDragStart(event) {
    event.dataTransfer.setData('nodeType', event.target.dataset.nodeType);
    event.dataTransfer.setData('nodeName', event.target.textContent);
}

function allowDrop(event) {
    event.preventDefault();
}

function dropNode(event) {
    event.preventDefault();
    const nodeType = event.dataTransfer.getData('nodeType');
    const nodeName = event.dataTransfer.getData('nodeName');
    
    const canvas = document.getElementById('workflowCanvas');
    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    
    createCanvasNode(nodeType, nodeName, x, y);
}

function createCanvasNode(type, name, x, y) {
    const canvas = document.getElementById('workflowCanvas');
    const nodeId = 'node_' + Date.now();
    
    const node = document.createElement('div');
    node.className = 'canvas-node';
    node.id = nodeId;
    node.style.left = x + 'px';
    node.style.top = y + 'px';
    node.draggable = true;
    
    node.innerHTML = `
        <div class="node-title">${name}</div>
        <div style="font-size: 11px; color: #ccc;">类型：${type}</div>
        <div class="node-actions">
            <button class="btn-edit" onclick="editNode('${nodeId}')">编辑</button>
            <button class="btn-delete" onclick="deleteNode('${nodeId}')">删除</button>
        </div>
    `;
    
    // 拖拽移动
    node.addEventListener('dragstart', handleNodeDragStart);
    canvas.addEventListener('dragover', handleNodeDragOver);
    canvas.addEventListener('drop', handleNodeDrop);
    
    canvas.appendChild(node);
    workflowNodes.push({ id: nodeId, type, name, x, y, config: {} });
}

let draggedNodeId = null;
let dragOffset = { x: 0, y: 0 };

function handleNodeDragStart(event) {
    draggedNodeId = event.target.id;
    const node = document.getElementById(draggedNodeId);
    const rect = node.getBoundingClientRect();
    dragOffset.x = event.clientX - rect.left;
    dragOffset.y = event.clientY - rect.top;
}

function handleNodeDragOver(event) {
    event.preventDefault();
}

function handleNodeDrop(event) {
    event.preventDefault();
    if (!draggedNodeId) return;
    
    const canvas = document.getElementById('workflowCanvas');
    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left - dragOffset.x;
    const y = event.clientY - rect.top - dragOffset.y;
    
    const node = document.getElementById(draggedNodeId);
    node.style.left = x + 'px';
    node.style.top = y + 'px';
    
    const nodeData = workflowNodes.find(n => n.id === draggedNodeId);
    if (nodeData) {
        nodeData.x = x;
        nodeData.y = y;
    }
    
    draggedNodeId = null;
}

function editNode(nodeId) {
    const node = workflowNodes.find(n => n.id === nodeId);
    if (!node) return;
    
    currentNodeId = nodeId;
    document.getElementById('nodeName').value = node.name;
    document.getElementById('nodeType').value = node.type;
    document.getElementById('nodeConfig').value = JSON.stringify(node.config, null, 2);
    
    document.getElementById('nodeModal').classList.add('active');
}

function closeModal() {
    document.getElementById('nodeModal').classList.remove('active');
    currentNodeId = null;
}

function saveNodeConfig() {
    if (!currentNodeId) return;
    
    const node = workflowNodes.find(n => n.id === currentNodeId);
    if (!node) return;
    
    node.name = document.getElementById('nodeName').value;
    node.type = document.getElementById('nodeType').value;
    
    try {
        node.config = JSON.parse(document.getElementById('nodeConfig').value);
    } catch (e) {
        alert('配置 JSON 格式错误');
        return;
    }
    
    closeModal();
    renderCanvasNodes();
}

function deleteNode(nodeId) {
    if (confirm('确定要删除这个节点吗？')) {
        const node = document.getElementById(nodeId);
        if (node) node.remove();
        
        workflowNodes = workflowNodes.filter(n => n.id !== nodeId);
    }
}

function clearCanvas() {
    if (confirm('确定要清空画布吗？')) {
        const canvas = document.getElementById('workflowCanvas');
        canvas.innerHTML = '<div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: #666;">拖拽节点到此处创建工作流程</div>';
        workflowNodes = [];
    }
}

function renderCanvasNodes() {
    const canvas = document.getElementById('workflowCanvas');
    canvas.innerHTML = '';
    
    workflowNodes.forEach(node => {
        const nodeEl = document.createElement('div');
        nodeEl.className = 'canvas-node';
        nodeEl.id = node.id;
        nodeEl.style.left = node.x + 'px';
        nodeEl.style.top = node.y + 'px';
        nodeEl.draggable = true;
        
        nodeEl.innerHTML = `
            <div class="node-title">${node.name}</div>
            <div style="font-size: 11px; color: #ccc;">类型：${node.type}</div>
            <div class="node-actions">
                <button class="btn-edit" onclick="editNode('${node.id}')">编辑</button>
                <button class="btn-delete" onclick="deleteNode('${node.id}')">删除</button>
            </div>
        `;
        
        canvas.appendChild(nodeEl);
    });
    
    initWorkflowEditor();
}

function saveWorkflow() {
    const workflow = {
        name: prompt('请输入工作流名称:', '未命名工作流'),
        nodes: workflowNodes
    };
    
    if (!workflow.name) return;
    
    fetch('/api/workflow', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(workflow)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('工作流已保存');
        } else {
            alert('保存失败：' + (data.error || '未知错误'));
        }
    })
    .catch(error => {
        alert('保存失败：' + error);
    });
}

function runWorkflow() {
    if (workflowNodes.length === 0) {
        alert('请先添加节点到工作流');
        return;
    }
    
    if (confirm('确定要运行这个工作流吗？')) {
        fetch('/api/workflow/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nodes: workflowNodes })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('工作流已开始执行，ID: ' + data.execution_id);
            } else {
                alert('执行失败：' + (data.error || '未知错误'));
            }
        })
        .catch(error => {
            alert('执行失败：' + error);
        });
    }
}

// ============ 标签页切换 ============
function initTabs() {
    document.querySelectorAll('.nav a').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            
            document.querySelectorAll('.nav a').forEach(l => l.classList.remove('active'));
            this.classList.add('active');
            
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.style.display = 'none';
            });
            
            const tabId = this.dataset.tab;
            document.getElementById(tabId).style.display = 'block';
            
            // 加载对应数据
            if (tabId === 'execution-history') {
                loadExecutionHistory();
            } else if (tabId === 'error-log') {
                loadLogs();
            } else if (tabId === 'circuit-breaker') {
                loadCircuitStatus();
            }
        });
    });
}

// ============ 刷新统计 ============
function refreshStats() {
    fetch('/api/stats')
        .then(response => response.json())
        .then(data => {
            updateCpuMetrics(data.cpu || {});
            updateMemoryMetrics(data.memory || {});
            updateWorkflowStats(data.workflow || {});
        })
        .catch(error => {
            console.error('刷新统计失败:', error);
        });
}

// ============ 页面加载完成 ============
document.addEventListener('DOMContentLoaded', function() {
    // 初始化图表
    initCpuChart();
    initMemoryChart();
    initPerformanceChart();
    
    // 初始化标签页
    initTabs();
    
    // 初始化工作流编辑器
    initWorkflowEditor();
    
    // 连接 WebSocket
    connectWebSocket();
    
    // 初始加载数据
    loadExecutionHistory();
    loadLogs();
    loadCircuitStatus();
    
    // 定时刷新（作为 WebSocket 的备用）
    setInterval(refreshStats, 5000);
});
