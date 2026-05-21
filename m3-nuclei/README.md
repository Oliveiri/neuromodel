# M3 HoVer-Net 服务

HoVer-Net 细胞核分割 FastAPI 服务，接口兼容现有 `model-m3`。

## 本地启动

```powershell
cd C:\Users\29698\Desktop\model-5.6\5.16-m3-hovernet\m3-segment-hovernet

# 1. 创建 & 激活虚拟环境
python -m venv venv
.\venv\Scripts\activate

# 2. 安装依赖
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 3. 启动服务
uvicorn app:app --host 0.0.0.0 --port 5004
```

> 本地没有 GPU 会走 CPU，速度慢，用于验证流程。性能测试在服务器上用 Docker + GPU 测。

## 测试接口

```powershell
# 健康检查
curl http://localhost:5004/readyz

# 批量推理（2块tile）
curl -X POST http://localhost:5004/predict_batch `
  -F 'manifest={"requestId":"local-test","modelType":"he2","samples":[{"tileId":"t1","imageRef":"img1","mpp":0.25,"level":0,"x":0,"y":0,"width":256,"height":256},{"tileId":"t2","imageRef":"img2","mpp":0.25,"level":0,"x":256,"y":0,"width":256,"height":256}]};type=text/plain' `
  -F 'img1=@path/to/tile1.png;type=image/png' `
  -F 'img2=@path/to/tile2.png;type=image/png'
```

## 接口说明

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/predict_batch` | 批量推理，入参出参同旧 M3 |
| GET | `/readyz` | 就绪探针 |
| GET | `/healthz` | 存活探针 |

## 目录结构

```
m3-segment-hovernet/
├── app.py           ← FastAPI 入口
├── core_infer.py    ← HoVer-Net 封装 + Q1/Q2/Q3 计算
├── requirements.txt
├── Dockerfile
├── pretrained/      ← 模型权重（151MB）
└── README.md
../
├── hover_net-master/ ← HoVer-Net 源码
```

## 与旧 M3 的差异

| | 旧 (turing_segment) | 新 (HoVer-Net) |
|---|-------------------|----------------|
| 模型加载 | 每次请求 subprocess | 启动时一次 |
| Q1/Q2/Q3 | CLI 直接输出 | 从 inst_map 计算 |
| 核分类 | 2类 | 6类（暂不暴露） |
