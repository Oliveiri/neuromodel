from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
import geopandas as gpd


def run_turing_segment(image_path: Path, output_dir: Path, timeout_sec: int = 120) -> Path:
    """单张推理（保留兼容，不再推荐）。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    model_type = os.getenv("M3_MODEL_TYPE", "he2")
    channels = os.getenv("M3_CHANNELS", "0,1,2")
    image_type = os.getenv("M3_IMAGE_TYPE", "cv2")

    cmd = [
        "turing_segment", "infer",
        "--image-path", str(image_path),
        "--image-type", image_type,
        "--model-type", model_type,
        "--channels", channels,
        "--channel-last",
        "--output-dir", str(output_dir),
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, timeout=timeout_sec)
    if proc.returncode != 0:
        raise RuntimeError(f"turing_segment failed: rc={proc.returncode}, stderr={proc.stderr[-800:]}")
    parquet_path = output_dir / "polygons.parquet"
    if not parquet_path.exists():
        raise FileNotFoundError(f"polygons.parquet not found in {output_dir}")
    return parquet_path


def run_turing_segment_batch(image_dir: Path, output_dir: Path,
                              timeout_sec: int = 300) -> dict[str, Path]:
    """
    批量推理：将目录下全部 PNG 一次送入 turing_segment，模型加载一次，
    处理后返回 {tileId: parquet_path} 映射。
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    model_type = os.getenv("M3_MODEL_TYPE", "he2")
    channels = os.getenv("M3_CHANNELS", "0,1,2")
    image_type = os.getenv("M3_IMAGE_TYPE", "cv2")

    cmd = [
        "turing_segment", "infer",
        "--image-dir", str(image_dir),
        "--image-type", image_type,
        "--model-type", model_type,
        "--channels", channels,
        "--channel-last",
        "--output-dir", str(output_dir),
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, timeout=timeout_sec)
    if proc.returncode != 0:
        raise RuntimeError(f"turing_segment batch failed: rc={proc.returncode}, stderr={proc.stderr[-800:]}")

    # 输出结构: output_dir/{image_name}_{channels}_{model_type}/polygons.parquet
    result: dict[str, Path] = {}
    for sub in output_dir.iterdir():
        if not sub.is_dir():
            continue
        pq = sub / "polygons.parquet"
        if not pq.exists():
            continue
        # 目录名格式: tile_xxx_{channels}_{model_type}
        # 提取 tileId（去掉末两次 _he2 之类后缀）
        name = sub.name
        # 从右去掉 _{model_type} 再 _{channels}
        suffix = f"_{model_type}"
        if name.endswith(suffix):
            name = name[: -len(suffix)]
        # 去掉 _{channels} 后缀
        channels_suffix = f"_{channels}"
        if name.endswith(channels_suffix):
            name = name[: -len(channels_suffix)]
        result[name] = pq
    return result


def read_polygons(parquet_path: Path):
    gdf = gpd.read_parquet(parquet_path)
    if "geometry" not in gdf.columns:
        return []
    gdf = gdf[gdf.geometry.notnull() & (~gdf.geometry.is_empty)].copy()
    return list(gdf.geometry)


def save_upload_file(file_bytes: bytes, suffix: str = ".png") -> Path:
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    p = Path(tmp_path)
    p.write_bytes(file_bytes)
    return p
