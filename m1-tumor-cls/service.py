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
        img = image.convert("RGB")
        x = transform(img).unsqueeze(0).to(self.device)

        with torch.no_grad():
            logits = self.model(x)
            probs = torch.softmax(logits, dim=1)[0].cpu().numpy()

        pred_index = int(np.argmax(probs))
        confidence = float(probs[pred_index])

        return {
            "pred_index": pred_index,
            "pred_class": CLASS_NAMES[pred_index],
            "confidence": confidence,
            "probs": {
                CLASS_NAMES[i]: float(probs[i]) for i in range(4)
            },
        }

    @bentoml.api
    def tissue_coords(self, request: dict) -> dict:
        """
        CLAM 组织分割：对 WSI 做组织区域检测，返回组织轮廓和有效 tile 坐标。
        Java 侧 WsiTileScanService 调用此接口替代全图均匀网格 + isBlankTile。
        输入：{"wsiPath":"...", "targetLevel":2, "patchSize":256, "stepSize":256,
               "segLevel":0, "sthresh":8, "mthresh":7, "close":4, "useOtsu":false,
               "aT":100, "aH":16, "maxNHoles":8}
        输出：{"contours":[[[x,y],...]], "validCoords":[[x,y],...], "totalTiles":N}
        """
        import sys, os

        # CLAM 内部使用 from wsi_core.xxx / from utils.xxx 的相对导入
        _app_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, os.path.join(_app_dir, "CLAM"))
        sys.path.insert(0, _app_dir)

        from CLAM.wsi_core.WholeSlideImage import WholeSlideImage

        wsi_path = request["wsiPath"]
        target_level = request.get("targetLevel", 2)
        patch_size = request.get("patchSize", 256)
        step_size = request.get("stepSize", 256)
        seg_level = request.get("segLevel", 0)
        sthresh = request.get("sthresh", 8)
        mthresh = request.get("mthresh", 7)
        close = request.get("close", 4)
        use_otsu = request.get("useOtsu", False)
        a_t = request.get("aT", 100)
        a_h = request.get("aH", 16)
        max_n_holes = request.get("maxNHoles", 8)

        wsi = WholeSlideImage(wsi_path)
        wsi.segmentTissue(
            seg_level=seg_level,
            sthresh=sthresh,
            mthresh=mthresh,
            close=close,
            use_otsu=use_otsu,
            filter_params={"a_t": a_t, "a_h": a_h, "max_n_holes": max_n_holes},
        )

        # 组织轮廓（多边形顶点数组，供前端渲染边界）
        contours = []
        for c in wsi.contours_tissue:
            contours.append(c.reshape(-1, 2).tolist())

        # 有效 tile 坐标（Java 侧直接使用）
        all_coords = []
        for cont_idx, contour in enumerate(wsi.contours_tissue):
            holes = wsi.holes_tissue[cont_idx] if cont_idx < len(wsi.holes_tissue) else []
            asset_dict, _ = wsi.process_contour(
                contour, holes,
                patch_level=target_level,
                save_path="",
                patch_size=patch_size,
                step_size=step_size,
                contour_fn="four_pt",
                use_padding=True,
            )
            if len(asset_dict) > 0 and len(asset_dict["coords"]) > 0:
                all_coords.append(asset_dict["coords"])

        coords_list = []
        if all_coords:
            coords_list = np.concatenate(all_coords).tolist()

        return {
            "contours": contours,
            "validCoords": coords_list,
            "totalTiles": len(coords_list),
            "segLevel": seg_level,
            "targetLevel": target_level,
        }

    @bentoml.api
    def healthz(self) -> dict:
        return {"status": "ok"}