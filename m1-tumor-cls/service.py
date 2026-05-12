import numpy as np
from PIL import Image
import torch
import torch.nn as nn
from torchvision import transforms
from torchvision.models import resnet18
import bentoml

# ---- 类别定义（严格遵循算法文档） ----
CLASS_NAMES = {
    0: "other",
    1: "tumor_low_grade",
    2: "tumor_high_grade",
    3: "coagulative_necrosis",
}

# ---- 预处理管道（与训练时完全一致） ----
transform = transforms.Compose([
    transforms.Resize((256, 256)),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225],
    ),
])

@bentoml.service(resources={"gpu": 1})
class ResNet18Service:
    """
    病理图像四分类推理服务
    基于算法组提供的 ResNet18 模型，输入 256x256 RGB patch，
    输出 other / tumor_low_grade / tumor_high_grade / coagulative_necrosis 概率。
    """
    def __init__(self):
        # ---- 设备选择 ----
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # ---- 模型结构（与训练时一致） ----
        self.model = resnet18(weights=None)
        self.model.fc = nn.Linear(self.model.fc.in_features, 4)

        # ---- 加载算法组提供的权重 ----
        state_dict = torch.load("best_model.pth", map_location="cpu")
        self.model.load_state_dict(state_dict)
        self.model.to(self.device)
        self.model.eval()

    @bentoml.api
    def predict(self, image: Image.Image) -> dict:
        """
        接收病理 patch 图像，返回四分类结果。
        输入：PIL.Image（RGB格式）
        输出：严格按照文档定义的结构化 JSON
        """
        # ---- 输入预处理 ----
        img = image.convert("RGB")
        x = transform(img).unsqueeze(0).to(self.device)

        # ---- 推理 ----
        with torch.no_grad():
            logits = self.model(x)
            probs = torch.softmax(logits, dim=1)[0].cpu().numpy()

        pred_index = int(np.argmax(probs))
        confidence = float(probs[pred_index])

        # ---- 构建标准输出 ----
        return {
            "pred_index": pred_index,
            "pred_class": CLASS_NAMES[pred_index],
            "confidence": confidence,
            "probs": {
                CLASS_NAMES[i]: float(probs[i]) for i in range(4)
            },
        }