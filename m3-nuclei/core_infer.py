"""
HoVer-Net inference wrapper + Q1/Q2/Q3 nuclei morphology statistics.

Loads HoVer-Net once, keeps model in GPU memory, processes tile batches
via InferManager.process_file_list, reads .mat output, computes ISUP-relevant
metrics from instance segmentation maps.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import scipy.io as sio
import torch
from PIL import Image

# ── HoVer-Net code lives one level up ──────────────────────────────────
HOVER_ROOT = Path(__file__).resolve().parent / "hover_net-master"
sys.path.insert(0, str(HOVER_ROOT))

from infer.tile import InferManager


# ═══════════════════════════════════════════════════════════════════════
# Model
# ═══════════════════════════════════════════════════════════════════════

MODEL_PATH = Path(__file__).resolve().parent / "pretrained" / "hovernet_fast_pannuke_type_tf2pytorch.tar"
TYPE_INFO_PATH = HOVER_ROOT / "type_info.json"

_infer_manager: InferManager | None = None


def load_model(model_path: str | None = None, gpu: str = "0") -> InferManager:
    global _infer_manager
    if _infer_manager is not None:
        return _infer_manager
    os.environ["CUDA_VISIBLE_DEVICES"] = gpu
    mp = model_path or str(MODEL_PATH)
    method_args = {
        "method": {
            "model_args": {"nr_types": 6, "mode": "fast"},
            "model_path": mp,
        },
        "type_info_path": str(TYPE_INFO_PATH),
    }
    _infer_manager = InferManager(**method_args)
    return _infer_manager


def infer_batch(image_paths: list[Path], output_dir: Path, batch_size: int = 64) -> Path:
    """Run HoVer-Net on a directory of tile images. Returns output_dir."""
    infer = load_model()
    run_args = {
        "batch_size": batch_size,
        "nr_inference_workers": 4,
        "nr_post_proc_workers": 4,
        "patch_input_shape": 256,
        "patch_output_shape": 164,
        "input_dir": str(image_paths[0].parent),
        "output_dir": str(output_dir),
        "mem_usage": 0.2,
        "draw_dot": False,
        "save_qupath": False,
        "save_raw_map": False,
    }
    infer.process_file_list(run_args)
    return output_dir


# ═══════════════════════════════════════════════════════════════════════
# .mat → polygon extraction
# ═══════════════════════════════════════════════════════════════════════

def read_inst_map(mat_path: Path) -> np.ndarray:
    """Read instance map from .mat file. Shape: (H, W), int32."""
    mat = sio.loadmat(str(mat_path))
    return mat["inst_map"].astype(np.int32)


def extract_polygons(inst_map: np.ndarray) -> list[dict]:
    """Extract polygon contours for each nucleus instance."""
    polygons = []
    for label in np.unique(inst_map):
        if label == 0:
            continue
        mask = (inst_map == label).astype(np.uint8)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            if len(cnt) < 3:
                continue
            # simplify polygon
            epsilon = 0.005 * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, epsilon, True)
            points = [[int(p[0][0]), int(p[0][1])] for p in approx]
            area = float(cv2.contourArea(cnt))
            if area < 4:  # skip tiny noise
                continue
            (cx, cy), (w, h), angle = cv2.minAreaRect(cnt)
            diameter = float(max(w, h))
            polygons.append({
                "points": points,
                "area": area,
                "diameter": diameter,
            })
    return polygons


# ═══════════════════════════════════════════════════════════════════════
# Q1 / Q2 / Q3  computed from polygon list
# ═══════════════════════════════════════════════════════════════════════

def compute_q_stats(polygons: list[dict], image_w: int, image_h: int,
                    mpp: float) -> tuple[dict, dict, dict]:
    n = len(polygons)
    if n == 0:
        return (
            {"totalNuclei": 0, "meanAreaPx": 0.0, "meanAreaUm2": 0.0, "enlargedCount": 0, "enlargedRatio": 0.0},
            {"meanMajorAxisPx": 0.0, "meanMajorAxisUm": 0.0, "atypiaIndex": 0.0, "majorAxisCv": 0.0, "meanCircularity": 0.0, "meanSolidity": 0.0},
            {"patchAreaMm2": 0.0, "hpfEquivalent": 0.0, "densityPerHpf": 0.0},
        )

    areas_px = [p["area"] for p in polygons]
    areas_um2 = [a * (mpp ** 2) for a in areas_px]
    diameters_px = [p["diameter"] for p in polygons]
    diameters_um = [d * mpp for d in diameters_px]

    # ── Q1 area ──
    mean_area_px = float(np.mean(areas_px))
    mean_area_um2 = float(np.mean(areas_um2))
    enlarged_count = sum(1 for a in areas_um2 if a > 12.0)
    enlarged_ratio = enlarged_count / n

    q1 = {
        "totalNuclei": n,
        "meanAreaPx": round(mean_area_px, 2),
        "meanAreaUm2": round(mean_area_um2, 2),
        "enlargedCount": enlarged_count,
        "enlargedRatio": round(enlarged_ratio, 4),
    }

    # ── Q2 atypia ──
    mean_major_um = float(np.mean(diameters_um)) if diameters_um else 0.0
    # atypiaIndex = ratio of mean major axis to normal reference (5μm)
    atypia_index = round(mean_major_um / 5.0, 2) if mean_major_um > 0 else 0.0
    major_cv = round(float(np.std(diameters_um) / mean_major_um), 4) if mean_major_um > 0 else 0.0

    # circularity = 4πA / P²
    circularities = []
    solidities = []
    for p in polygons:
        area = p["area"]
        pts = np.array(p["points"], dtype=np.float32)
        if len(pts) < 3:
            continue
        perimeter = cv2.arcLength(pts, True)
        if perimeter > 0:
            circularities.append(4 * np.pi * area / (perimeter * perimeter))
        hull = cv2.convexHull(pts)
        hull_area = cv2.contourArea(hull)
        if hull_area > 0:
            solidities.append(area / hull_area)

    mean_circularity = round(float(np.mean(circularities)), 4) if circularities else 0.0
    mean_solidity = round(float(np.mean(solidities)), 4) if solidities else 0.0

    q2 = {
        "meanMajorAxisPx": round(float(np.mean(diameters_px)), 2) if diameters_px else 0.0,
        "meanMajorAxisUm": round(mean_major_um, 2),
        "atypiaIndex": atypia_index,
        "majorAxisCv": major_cv,
        "meanCircularity": mean_circularity,
        "meanSolidity": mean_solidity,
    }

    # ── Q3 density ──
    patch_area_mm2 = (image_w * mpp / 1000) * (image_h * mpp / 1000)
    # 1 HPF = π * (0.275mm)² ≈ 0.2376 mm²
    hpf_area_mm2 = np.pi * (0.275 ** 2)
    hpf_equivalent = patch_area_mm2 / hpf_area_mm2
    density_per_hpf = round(n / hpf_equivalent, 2) if hpf_equivalent > 0 else 0.0

    q3 = {
        "patchAreaMm2": round(patch_area_mm2, 6),
        "hpfEquivalent": round(hpf_equivalent, 4),
        "densityPerHpf": density_per_hpf,
    }

    return q1, q2, q3
