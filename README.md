# Neuro Model 5.6 — 模型服务部署

## 目录结构

```
neuro-model-5.6/
├── m1-tumor-cls/        M1 肿瘤四分类 (BentoML)
├── m2-ccrcc/            M2 ccRCC 分割 (BentoML)
├── m2-prcc/             M2 pRCC 分割 (BentoML)
├── m3-nuclei/           M3 细胞核分割 (FastAPI)
├── m4-vstain/           M4 虚拟染色 (FastAPI)
├── embedding/           自建 Embedding 服务 (bge-small-zh-v1.5)
├── deploy/
│   ├── docker-compose.yml  ← 统一编排（需复制到服务器部署根目录）
│   ├── init.sql             ← MySQL 初始化（7 张表）
│   ├── .env.example
│   └── DEPLOY.md
└── README.md
```

## 为什么 compose 在 deploy/ 下但服务器上要放外面

`docker-compose.yml` 引用 `spring-backend` 和 `neuro-models` 使用相对路径：

```yaml
context: ./spring-backend
context: ./neuro-models/m1-tumor-cls
```

这就要求 compose 文件和这两个目录**在同一父目录下**。服务器部署结构为：

```
/opt/docker/
├── neuro-demo/
│   ├── docker-compose.yml    ← 从 deploy/ 复制到此处
│   ├── spring-backend/
│   └── neuro-models/         ← 本仓库 clone 到这里
└── pathology_inference/      ← 独立的 Qwen2.5-VL 项目
```

`deploy/` 只是本地源码中的存放位置，部署时 `cp` 到父目录。

## 部署流程

### 1. 在服务器上创建目录结构

```bash
sudo mkdir -p /opt/docker/neuro-demo
sudo chown -R ubuntu:ubuntu /opt/docker/neuro-demo
```

### 2. 拉取代码

```bash
cd /opt/docker/neuro-demo
git clone <本仓库地址> neuro-models
git clone <Spring 仓库地址> spring-backend
git clone <pathology_inference 仓库地址> pathology_inference   # 如果用到 Qwen-VL
```

### 3. 放置部署文件

```bash
cd /opt/docker/neuro-demo
cp neuro-models/deploy/docker-compose.yml ./
cp neuro-models/deploy/init.sql ./
cp neuro-models/deploy/.env.example ./.env
nano .env   # 填入 DEEPSEEK_API_KEY 和 MYSQL_ROOT_PASSWORD
```

### 4. 构建并启动

```bash
cd /opt/docker/neuro-demo
sudo docker compose build
sudo docker compose up -d
```

### 5. 更新代码后重建

```bash
cd /opt/docker/neuro-demo/neuro-models
git pull
cd /opt/docker/neuro-demo
sudo docker compose build    # 只重建有变更的镜像
sudo docker compose up -d
```

## 更新 compose 时注意

修改 `deploy/docker-compose.yml` 后，服务器上需重新复制到根目录：

```bash
cp /opt/docker/neuro-demo/neuro-models/deploy/docker-compose.yml /opt/docker/neuro-demo/
```

否则 compose 读取的是旧文件。

## 本地启动（Windows 开发用）

各子目录独立启动，见各目录 README。M3 不支持 Windows（依赖 turing_segment Linux 专用包）。
