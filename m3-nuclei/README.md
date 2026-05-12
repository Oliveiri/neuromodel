# M3 Nucleus Segmentation Service (Linux Docker 部署指南)

## 1. 服务说明
本服务保持你当前约定的原始输入输出协议不变。

- 接口：`POST /predict_batch`
- 输入：`multipart/form-data`
  - `manifest`（JSON 字符串）
  - 多个图片文件（字段名必须等于 `samples[i].imageRef`）
- 输出：
  - `results[*].nucleiPolygons`
  - `results[*].statsQ1`
  - `results[*].statsQ2`
  - `results[*].statsQ3`
  - 并保留 `tileId, level, x, y, width, height, mpp` 一一对应回传

## 2. 前置条件（Linux）
建议系统：`Ubuntu 22.04+`

需要先安装：
1. Docker Engine 24+
2. Docker Compose Plugin (`docker compose`)
3. (可选，GPU 推理) NVIDIA Driver + NVIDIA Container Toolkit

检查命令：
```bash
docker --version
docker compose version
```

## 3. 目录文件
当前 `m3` 目录包含以下部署文件：
- `Dockerfile`
- `docker-compose.yml`
- `.env.example`
- `.dockerignore`

## 4. 配置步骤

### 4.1 复制环境变量模板
```bash
cd /path/to/model-5.6/m3
cp .env.example .env
```

### 4.2 修改 `.env`（按实际环境）
你最常改的项：
1. `TURING_SEGMENT_PIP_INDEX_URL`
   - 算法团队如果给的是私有 pip 源，这里必须填。
2. `M3_PORT`
   - 主机暴露端口，默认 `5004`。
3. `M3_DOCKER_NETWORK_NAME / M3_DOCKER_SUBNET / M3_DOCKER_GATEWAY / M3_IPV4_ADDRESS`
   - 指定网络部署参数（默认 `m3_infer_net` + `172.29.0.0/24`）。
4. 并发与批处理参数：
   - `M3_MAX_BATCH_SIZE`
   - `M3_MAX_INFLIGHT_PER_REQUEST`
   - `M3_GLOBAL_MAX_INFLIGHT`
   - `M3_SEGMENT_TIMEOUT_SEC`
5. 模型调用参数：
   - `M3_MODEL_TYPE`（默认 `he2`）
   - `M3_CHANNELS`（默认 `0,1,2`）
   - `M3_IMAGE_TYPE`（默认 `cv2`）

## 5. 构建与启动（指定网络）

### 5.1 构建镜像
```bash
docker compose --env-file .env build --no-cache
```

### 5.2 启动服务
```bash
docker compose --env-file .env up -d
```

### 5.3 查看状态
```bash
docker compose ps
docker compose logs -f m3-seg
```

### 5.4 健康检查
```bash
curl http://127.0.0.1:${M3_PORT}/healthz
curl http://127.0.0.1:${M3_PORT}/readyz
```

## 6. 网络部署与联调
`docker-compose.yml` 已创建自定义 bridge 网络并固定容器 IP。

查看网络：
```bash
docker network inspect ${M3_DOCKER_NETWORK_NAME}
```

### 6.1 从主机访问
```text
http://127.0.0.1:${M3_PORT}/predict_batch
```

### 6.2 从同网络内其他容器访问
```text
http://m3-seg:5004/predict_batch
```
说明：如果你的 Spring 服务也在 Docker 中运行，请把 Spring 容器加入 `M3_DOCKER_NETWORK_NAME`，然后用服务名 `m3-seg` 调用。

## 7. 常见失败与处理

### 7.1 `No matching distribution found for turing_segment`
表示镜像构建阶段拉不到该包。

处理：
1. 在 `.env` 设置 `TURING_SEGMENT_PIP_INDEX_URL=<算法团队私有源>`
2. 若还有附加源，设置 `TURING_SEGMENT_PIP_EXTRA_INDEX_URL`
3. 重新构建：
```bash
docker compose --env-file .env build --no-cache
```

### 7.2 容器启动了但推理失败
1. 看日志：`docker compose logs -f m3-seg`
2. 检查传入 `manifest` 的 `imageRef` 与 multipart 文件字段是否完全一致
3. 检查 `mpp > 0`

### 7.3 并发过高导致超时
调小：
- `M3_MAX_INFLIGHT_PER_REQUEST`
- `M3_GLOBAL_MAX_INFLIGHT`
并适当调大 `M3_SEGMENT_TIMEOUT_SEC`

## 8. 停止与清理
```bash
docker compose down
```
如需删除镜像：
```bash
docker rmi ${M3_IMAGE_NAME}:${M3_IMAGE_TAG}
```

## 9. 你可以按实际情况修改的地方（汇总）
1. 包源相关：`.env` 中 `TURING_SEGMENT_PIP_*`
2. 端口：`.env` 中 `M3_PORT`
3. 网络：`.env` 中 `M3_DOCKER_*` 与 `M3_IPV4_ADDRESS`
4. 推理参数：`.env` 中 `M3_MODEL_TYPE/M3_CHANNELS/M3_IMAGE_TYPE`
5. 性能参数：`.env` 中并发和超时参数
6. Uvicorn worker 数量：`Dockerfile` 最后一行 `--workers 2`
