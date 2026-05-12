import argparse
import numpy as np
from PIL import Image
import torch
from torchvision import transforms
import bentoml

from src import UNet

CLASS_NAMES = {
    0: "other",
    1: "ccrcc",
}

# 判定规则：目标类别像素占比 >= 30% 则判定为目标类
TARGET_RATIO_THRESHOLD = 0.20


def mask_to_rle(mask: np.ndarray) -> dict:
    """将二值mask编码为RLE，避免直接返回大数组。"""
    flat = mask.astype(np.uint8).reshape(-1)
    counts = []
    prev = 0
    run_len = 0
    for v in flat:
        if v == prev:
            run_len += 1
        else:
            counts.append(run_len)
            run_len = 1
            prev = int(v)
    counts.append(run_len)
    return {
        "size": [int(mask.shape[0]), int(mask.shape[1])],
        "counts": counts,
    }


@bentoml.service(resources={"gpu": 1})
class CcRccUnetService:
    """M2 ccRCC 分割服务：输入单张RGB patch，输出结构化二分类结果。"""

    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = UNet(in_channels=3, num_classes=2, base_c=32)
        state = self._safe_torch_load("multi_train/model_299.pth")
        state_dict = state["model"] if isinstance(state, dict) and "model" in state else state
        self.model.load_state_dict(state_dict)
        self.model.to(self.device)
        self.model.eval()

        self.transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize(mean=(0.709, 0.381, 0.224), std=(0.127, 0.079, 0.043)),
        ])

    def _safe_torch_load(self, path: str):
        """兼容 PyTorch 2.6+ 默认 weights_only=True 的行为。"""
        try:
            return torch.load(path, map_location="cpu", weights_only=False)
        except TypeError:
            return torch.load(path, map_location="cpu")
        except Exception:
            try:
                torch.serialization.add_safe_globals([argparse.Namespace])
                return torch.load(path, map_location="cpu", weights_only=False)
            except TypeError:
                return torch.load(path, map_location="cpu")

    @bentoml.api
    def predict(self, image: Image.Image) -> dict:
        img = image.convert("RGB")
        x = self.transform(img).unsqueeze(0).to(self.device)

        with torch.no_grad():
            out = self.model(x)
            logits = out["out"] if isinstance(out, dict) else out
            pred_mask = logits.argmax(dim=1)[0].cpu().numpy().astype(np.uint8)

        target_id = 1
        target_mask = (pred_mask == target_id).astype(np.uint8)
        total_pixels = int(target_mask.size)
        target_pixels = int(target_mask.sum())
        target_ratio = float(target_pixels / total_pixels) if total_pixels > 0 else 0.0

        pred_index = target_id if target_ratio >= TARGET_RATIO_THRESHOLD else 0

        return {
            "pred_index": pred_index,
            "pred_class": CLASS_NAMES[pred_index],
            "class_probs": {
                "other": float(1.0 - target_ratio),
                "ccrcc": float(target_ratio),
            },
            "pixelStats": {
                "totalPixels": total_pixels,
                "targetPixels": target_pixels,
                "targetRatio": target_ratio,
            },
            "targetMaskRle": mask_to_rle(target_mask),
            "maskShape": [int(pred_mask.shape[0]), int(pred_mask.shape[1])],
        }

