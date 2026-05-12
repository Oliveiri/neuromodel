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

下次重新启动时，只需重复以上步骤即可。如果需要修改并发等参数，记得先修改 service.py 中的 @bentoml.service(...) 装饰器。