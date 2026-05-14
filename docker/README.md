# AgentM Docker 部署配置

## 构建并运行

```bash
# 构建镜像
docker build -t agentm:latest .

# 运行容器
docker run -d \
  --name agentm \
  -p 5000:5000 \
  -v ./agentm_data:/app/agentm_data \
  -v ./config.yaml:/app/config.yaml \
  -e AGENTM_ENVIRONMENT=production \
  agentm:latest

# 查看日志
docker logs -f agentm

# 访问 WebUI
# http://localhost:5000
```

## Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY . .

# 创建数据目录
RUN mkdir -p /app/agentm_data/logs

# 暴露端口
EXPOSE 5000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

# 启动命令
CMD ["python", "-m", "webui.webui"]
```

## Docker Compose

```yaml
version: '3.8'

services:
  agentm:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - ./agentm_data:/app/agentm_data
      - ./config.yaml:/app/config.yaml
    environment:
      - AGENTM_ENVIRONMENT=production
      - AGENTM_LOG_LEVEL=INFO
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # 可选：PostgreSQL 数据库
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: agentm
      POSTGRES_USER: agentm
      POSTGRES_PASSWORD: ${DB_PASSWORD:-changeme}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

volumes:
  postgres_data:
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| AGENTM_ENVIRONMENT | 运行环境 | development |
| AGENTM_LOG_LEVEL | 日志级别 | INFO |
| AGENTM_WEBUI_PORT | WebUI 端口 | 5000 |
| AGENTM_RAG_TOP_K | RAG 检索数量 | 5 |
| DB_PASSWORD | 数据库密码 | changeme |

## 生产部署建议

1. **使用固定版本标签**
   ```bash
   docker build -t agentm:v1.0.0 .
   docker tag agentm:v1.0.0 agentm:latest
   ```

2. **配置持久化**
   ```bash
   # 确保数据目录持久化
   docker volume create agentm_data
   ```

3. **资源限制**
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '2'
         memory: 2G
       reservations:
         cpus: '0.5'
         memory: 512M
   ```

4. **日志轮转**
   ```yaml
   logging:
     driver: "json-file"
     options:
       max-size: "10m"
       max-file: "3"
   ```
