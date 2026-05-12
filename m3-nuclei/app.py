from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request
from PIL import Image

from schemas import BatchManifest, SampleMeta
from core_infer import run_turing_segment, read_polygons, save_upload_file
from core_geometry import geometries_to_nuclei
from core_stats import compute_q_stats

app = FastAPI(title="M3 Nucleus Segmentation Service", version="1.0.0")

MAX_BATCH_SIZE = int(os.getenv("M3_MAX_BATCH_SIZE", "64"))
MAX_INFLIGHT_PER_REQUEST = int(os.getenv("M3_MAX_INFLIGHT_PER_REQUEST", "8"))
GLOBAL_MAX_INFLIGHT = int(os.getenv("M3_GLOBAL_MAX_INFLIGHT", "32"))
SEGMENT_TIMEOUT_SEC = int(os.getenv("M3_SEGMENT_TIMEOUT_SEC", "120"))

_global_sem = asyncio.Semaphore(GLOBAL_MAX_INFLIGHT)
_pool = ThreadPoolExecutor(max_workers=max(1, MAX_INFLIGHT_PER_REQUEST * 2))


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict[str, str]:
    return {"status": "ready"}


@app.post("/predict_batch")
async def predict_batch(request: Request, manifest: str = Form(...)) -> dict[str, Any]:
    try:
        manifest_obj = BatchManifest.model_validate_json(manifest)
    except Exception as ex:
        raise HTTPException(status_code=400, detail=f"invalid manifest: {ex}")

    if not manifest_obj.samples:
        raise HTTPException(status_code=400, detail="samples is empty")
    if len(manifest_obj.samples) > MAX_BATCH_SIZE:
        raise HTTPException(status_code=400, detail=f"batch size exceeds limit {MAX_BATCH_SIZE}")

    form = await request.form()
    file_map = {k: v for k, v in form.items() if hasattr(v, "filename")}

    # 严格校验每个 sample 的 imageRef 对应存在上传文件
    for s in manifest_obj.samples:
        if s.imageRef not in file_map:
            raise HTTPException(status_code=400, detail=f"missing file for imageRef={s.imageRef}")
        if s.mpp <= 0:
            raise HTTPException(status_code=400, detail=f"invalid mpp for tileId={s.tileId}")

    request_id = manifest_obj.requestId or f"req-{int(time.time() * 1000)}"

    async def run_one(sample: SampleMeta) -> dict[str, Any]:
        async with _global_sem:
            return await _process_one_sample(request_id, sample, file_map[sample.imageRef])

    # 分组限并发执行，保证高并发稳定
    results: list[dict[str, Any]] = []
    tasks = [run_one(s) for s in manifest_obj.samples]
    # 按输入顺序返回，保证一一对应
    for i in range(0, len(tasks), MAX_INFLIGHT_PER_REQUEST):
        chunk = tasks[i:i + MAX_INFLIGHT_PER_REQUEST]
        chunk_results = await asyncio.gather(*chunk, return_exceptions=False)
        results.extend(chunk_results)

    success_count = sum(1 for r in results if "error" not in r)
    failed_count = len(results) - success_count

    return {
        "requestId": request_id,
        "successCount": success_count,
        "failedCount": failed_count,
        "results": results,
    }


async def _process_one_sample(request_id: str, sample: SampleMeta, upload_file) -> dict[str, Any]:
    t0 = time.perf_counter()

    base_payload = {
        "tileId": sample.tileId,
        "imageRef": sample.imageRef,
        "mpp": sample.mpp,
        "level": sample.level,
        "x": sample.x,
        "y": sample.y,
        "width": sample.width,
        "height": sample.height,
    }

    work_dir = Path(tempfile.mkdtemp(prefix=f"m3_{request_id}_{sample.tileId}_"))
    img_path = None
    try:
        content = await upload_file.read()
        suffix = Path(upload_file.filename or "input.png").suffix or ".png"
        img_path = save_upload_file(content, suffix=suffix)

        seg_out = work_dir / "segment_out"

        # CPU 密集/外部进程调用放线程池中执行
        parquet_path = await asyncio.get_running_loop().run_in_executor(
            _pool,
            lambda: run_turing_segment(img_path, seg_out, timeout_sec=SEGMENT_TIMEOUT_SEC),
        )
        geoms = await asyncio.get_running_loop().run_in_executor(_pool, lambda: read_polygons(parquet_path))

        nuclei = geometries_to_nuclei(geoms)

        with Image.open(img_path) as im:
            w, h = im.size

        stats_q1, stats_q2, stats_q3 = compute_q_stats(nuclei, w, h, sample.mpp)

        # 清理内部几何对象，不对外暴露
        for n in nuclei:
            n.pop("_geom", None)

        payload = {
            **base_payload,
            "nucleiPolygons": nuclei,
            "statsQ1": stats_q1,
            "statsQ2": stats_q2,
            "statsQ3": stats_q3,
            "meta": {
                "nucleusCount": len(nuclei),
                "imageWidth": w,
                "imageHeight": h,
                "latencyMs": round((time.perf_counter() - t0) * 1000, 2),
            },
        }
        return payload

    except Exception as ex:
        return {
            **base_payload,
            "error": str(ex),
            "meta": {
                "latencyMs": round((time.perf_counter() - t0) * 1000, 2),
            },
        }
    finally:
        try:
            if img_path and Path(img_path).exists():
                Path(img_path).unlink(missing_ok=True)
        except Exception:
            pass
        shutil.rmtree(work_dir, ignore_errors=True)
