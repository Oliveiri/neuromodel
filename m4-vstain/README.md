# M4 Virtual Staining Service

基于 CycleGAN 的虚拟免疫组化染色服务。将 H&E 染色的 256×256 病理瓦片翻译为虚拟 IHC 染色图像。

- **CD3** — T 淋巴细胞标记物（虚拟 CD3 IHC）
- **PAX5** — B 淋巴细胞标记物（虚拟 PAX5 IHC）

## API

```
POST /predict_batch
GET  /healthz
GET  /readyz
```

详细契约见 Spring 项目文档。

## Windows 本地启动

### 1. 创建虚拟环境

```powershell
cd C:\Users\29698\Desktop\model-5.6\m4
python -m venv venv
.\venv\Scripts\activate
```

### 2. 安装依赖

```powershell
pip install fastapi uvicorn python-multipart Pillow
```

### 3. 安装 PyTorch（CPU 版，本地测试用）

```powershell
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

如果有 NVIDIA GPU 且安装了 CUDA 12.1，将 `cpu` 替换为 `cu121`：

```powershell
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

### 4. 确认模型文件存在

```
checkpoints/
├── cyclegan_CD3/
│   └── latest_net_G_A.pth   (45.5 MB)
└── cyclegan_PAX5/
    └── latest_net_G_A.pth   (45.5 MB)
```

### 5. 启动服务

```powershell
uvicorn app:app --host 0.0.0.0 --port 5005
```

### 6. 验证

```powershell
curl http://localhost:5005/readyz
```

期望返回：

```json
{"status":"ready","models":["CD3","PAX5"]}
```

### 7. 功能测试

```powershell
curl -X POST http://localhost:5005/predict_batch `
  -F "manifest={\"requestId\":\"test-1\",\"modelType\":\"CD3\",\"samples\":[{\"tileId\":\"tile_0\",\"imageRef\":\"img_0\",\"outputPath\":\"C:/Users/29698/Desktop/model-5.6/m4/test_out/test_cd3.png\"}]};type=text/plain" `
  -F "img_0=@C:/path/to/your/256x256_he_tile.png;type=image/png"
```

将输入图片路径替换为实际的 256×256 H&E 瓦片，检查 `test_out/test_cd3.png` 是否生成。

## Docker 部署（Linux 服务器）

```bash
cd /path/to/m4
docker compose up -d
```

需要 NVIDIA Container Toolkit 以使用 GPU：

```bash
sudo apt-get install nvidia-container-toolkit
sudo systemctl restart docker
```
