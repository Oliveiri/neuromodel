1. 打开终端（PowerShell 或 CMD），进入项目目录
bash
cd C:\Users\29698\PycharmProjects\M1-resnet
2. 激活虚拟环境
bash
venv\Scripts\activate
成功后会看到终端前面出现 (venv)。

3. 启动 BentoML 服务
bash
bentoml serve service:ResNet18Service --port 5001
看到 Service ResNet18Service initialized 就表示启动成功，监听在 http://localhost:5001。

4. 停止服务
在启动服务的终端窗口中，按下 Ctrl + C 即可安全停止。

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/predict` | POST multipart | 单张 256x256 tile 四分类 |
| `/clam/tissue-coords` | POST JSON | CLAM 组织分割，返回 contour + 有效 tile 坐标 |
| `/healthz` | GET | 健康检查 |

### `/clam/tissue-coords` 请求示例

```json
{
  "wsiPath": "/data/wsi/10/original.svs",
  "targetLevel": 2,
  "patchSize": 256,
  "stepSize": 256,
  "segLevel": 0,
  "sthresh": 8,
  "mthresh": 7,
  "close": 4,
  "useOtsu": false,
  "aT": 100,
  "aH": 16,
  "maxNHoles": 8
}
```

### 响应示例

```json
{
  "contours": [[[x1,y1],[x2,y2],...], ...],
  "validCoords": [[0,0],[256,0],...],
  "totalTiles": 1500,
  "segLevel": 0,
  "targetLevel": 2
}
```

下次重新启动时，只需重复以上步骤即可。如果需要修改并发等参数，记得先修改 service.py 中的 @bentoml.service(...) 装饰器。