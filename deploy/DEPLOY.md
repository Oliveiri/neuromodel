# Neuro Demo 完整部署指南

## 零、部署前的两件事

### ① 确保本地 Spring 能编译

```powershell
cd C:\Users\29698\IdeaProjects\neuro-demo
mvn compile -q
```

### ② 确保 neuro-model-5.6 已推送到 Git

```powershell
cd C:\Users\29698\Desktop\model-5.6\neuro-model-5.6
git init
git add .
git commit -m "init"
git remote add origin <仓库地址>
git push -u origin master
```

---

## 一、服务器首次初始化（只需做一次）

```bash
# SSH 登录
ssh ubuntu@<服务器IP>

# ---- 安装 Docker ----
curl -fsSL https://get.docker.com | sudo bash
sudo usermod -aG docker ubuntu
exit                    # ⬅ 退出然后重新登录

ssh ubuntu@<服务器IP>   # 重新登录

# ---- 安装 NVIDIA Container Toolkit（GPU 支持） ----
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker

# ---- 验证 GPU 在 Docker 中可见 ----
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi

# ---- 创建全局共享网络（NPM 和 Spring 之间的桥梁） ----
docker network create shared_net

# ---- 创建部署目录和数据目录 ----
sudo mkdir -p /opt/docker/neuro-demo
sudo chown -R ubuntu:ubuntu /opt/docker/neuro-demo
sudo mkdir -p /data/wsi /data/tiles /data/artifacts
sudo chmod -R 755 /data/wsi /data/tiles /data/artifacts
```

---

## 二、拉取代码

```bash
cd /opt/docker/neuro-demo

# 模型服务（一个仓库包含 M1-M4 + 部署文件）
git clone <你的 neuro-model-5.6 仓库地址> neuro-models

# Spring 后端（独立仓库）
git clone <你的 Spring 仓库地址> spring-backend
```

---

## 三、准备部署文件

```bash
cd /opt/docker/neuro-demo

# 把 compose 提到根目录
cp neuro-models/deploy/docker-compose.yml ./

# 把 init.sql 提到根目录（MySQL 容器挂载需要）
cp neuro-models/deploy/init.sql ./

# 创建 .env
cp neuro-models/deploy/.env.example ./.env
nano .env
```

`.env` 中**必须填**的值：

```
DEEPSEEK_API_KEY=sk-xxxxxxxxxx    # DeepSeek API Key，必填
MYSQL_ROOT_PASSWORD=你的强密码     # 改掉默认值
```

`.env` 中**如果有**才填的值：

```
TURING_SEGMENT_PIP_INDEX_URL=     # 算法组提供的 turing_segment 私有 pip 源
TURING_SEGMENT_PIP_EXTRA_INDEX_URL=
```

---

## 四、上传 WSI 和瓦片数据

把你的切片文件和预处理好的瓦片放到对应目录：

```bash
# WSI 原文件放这里
ls /data/wsi/        # 应该有你的 .svs 或 .tiff 文件

# 预处理瓦片放这里
ls /data/tiles/      # 应该有 wsi_id/level/tile_x_tile_y.png 结构
```

> 目录结构示例：
> ```
> /data/tiles/6/2/256_7680.png
> /data/tiles/6/2/512_7680.png
> ...
> ```

---

## 五、构建并启动

```bash
cd /opt/docker/neuro-demo

# 构建所有镜像（首次约 15-30 分钟，取决于网速）
docker compose build

# 启动所有服务
docker compose up -d

# 等 1-2 分钟后查看状态
docker compose ps
```

期望输出：9 个容器全部 `running` 或 `healthy`。

---

## 六、验证

```bash
# Spring Boot
curl http://localhost:8080/actuator/health
# 预期: {"status":"UP"}

# M1 BentoML
curl http://localhost:8080/actuator/health
# （M1 在内部网络，从宿主机不能直连。通过 Spring 间接验证：查看日志）
docker compose logs m1-tumor-cls | tail -5
# 预期: 看到 BentoML serving started

# M3 FastAPI
# （同样在内部网络，只能通过日志验证）
docker compose logs m3-nuclei | tail -5
# 预期: Uvicorn running on http://0.0.0.0:5004

# M4 FastAPI
docker compose logs m4-vstain | tail -5

# MySQL
docker compose exec mysql mysql -uroot -p -e "SHOW TABLES FROM neurochat"
# 输入密码，预期看到 7 张表

# Qdrant
docker compose exec qdrant curl http://127.0.0.1:6333/healthz
```

---

## 七、常见问题及解决

| 问题 | 原因 | 解决 |
|------|------|------|
| `Error response from daemon: could not select device driver ... "nvidia"` | 未安装 nvidia-container-toolkit | 重新执行第一步中的 NVIDIA 安装步骤 |
| M3 构建失败 `pip install turing_segment` | 私有 pip 源不可达 | 在 `.env` 中设置正确的 `TURING_SEGMENT_PIP_INDEX_URL` |
| `docker compose build` 下载 PyTorch 镜像很慢 | pytorch/pytorch ~5GB | 等。后续构建会复用缓存，很快 |
| Spring 启动后日志显示 `Connection refused: model-m1:5001` | M1 容器还没准备好 | Spring 会一直重试。等 M1 构建完成后再 `docker compose restart spring` |
| `docker compose ps` 某容器 `unhealthy` | 健康检查失败 | `docker compose logs <服务名>` 查看日志排查 |
| Spring 日志 `Unknown database 'neurochat'` | init.sql 没放对位置或数据库没创建 | 确认 `/opt/docker/neuro-demo/init.sql` 存在；如果 MySQL 已启动但没执行 init.sql，删除 volume 重建：`docker compose down -v && docker compose up -d` |
| 数据库表不存在 | init.sql 未执行 | MySQL 的 init.sql 仅在**首次创建 volume** 时执行。如果已创建过 volume：`docker compose down -v mysql && docker compose up -d mysql` |
| GPU 内存不足 | 多个模型同时加载 | 一机多卡不会有问题；单卡时各模型按需加载，不冲突。如果 OOM，减少并发或分批启动模型 |
| `shared_net` 网络不存在 | 第一步没创建 | `docker network create shared_net` |

---

## 八、日常运维

```bash
cd /opt/docker/neuro-demo

docker compose ps                  # 看状态
docker compose logs -f             # 实时所有日志
docker compose logs -f spring      # 只看 Spring
docker compose restart spring      # 重启 Spring（改代码后）
docker compose up -d --build spring # 重建并重启 Spring
docker compose up -d --build       # 重建全部
docker compose down                # 停止全部
docker compose down -v             # 停止并删除数据卷（⚠ 数据库数据会丢）
```
