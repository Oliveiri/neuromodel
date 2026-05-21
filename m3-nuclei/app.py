"""
M3 Nuclei Segmentation Service — HoVer-Net backend.

POST /predict_batch   — batch inference, returns nuclei polygons + Q1/Q2/Q3
GET  /readyz          — readiness probe
GET  /healthz         — liveness probe

Interface compatible with the turing_segment-based model-m3 container.
Spring requires zero changes.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from PIL import Image

from core_infer import compute_q_stats, extract_polygons, infer_batch, load_model, read_inst_map

app = FastAPI(title="M3 HoVer-Net Service")

# ── config from env ────────────────────────────────────────────────────
MODEL_PATH = os.getenv("M3_MODEL_PATH", None)
GPU_ID = os.getenv("M3_GPU", "0")
SEGMENT_TIMEOUT_SEC = int(os.getenv("M3_SEGMENT_TIMEOUT_SEC", "300"))
MAX_BATCH_SIZE = int(os.getenv("M3_MAX_BATCH_SIZE", "64"))


@app.on_event("startup")
def startup():
    t0 = time.time()
    load_model(model_path=MODEL_PATH, gpu=GPU_ID)
    print(f"[startup] HoVer-Net loaded in {time.time() - t0:.1f}s", flush=True)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    return {"status": "ready"}


@app.post("/predict_batch")
async def predict_batch(request: Request):
    """
    Expects multipart/form-data with:
      manifest : JSON string (text/plain)
                 { requestId, modelType, samples: [{tileId, imageRef, mpp, level, x, y, width, height}] }
      img_N    : PNG file for each sample referenced by imageRef
    """
    form = await request.form()

    # ── parse manifest ─────────────────────────────────────────────
    manifest_raw = form.get("manifest")
    if manifest_raw is None:
        raise HTTPException(400, "missing manifest field")
    import json
    try:
        manifest = json.loads(await manifest_raw.read() if hasattr(manifest_raw, "read") else str(manifest_raw))
    except Exception:
        raise HTTPException(400, "invalid manifest JSON")

    samples = manifest.get("samples", [])
    if not samples:
        raise HTTPException(400, "samples is empty")
    if len(samples) > MAX_BATCH_SIZE:
        raise HTTPException(400, f"batch size exceeds limit {MAX_BATCH_SIZE}")

    request_id = manifest.get("requestId", f"req-{int(time.time() * 1000)}")

    # ── write images to shared batch dir ───────────────────────────
    batch_dir = Path(tempfile.mkdtemp(prefix=f"m3hn_{request_id}_"))
    output_dir = Path(tempfile.mkdtemp(prefix=f"m3hn_out_{request_id}_"))
    tile_meta: dict[str, dict] = {}   # tileId → {imageRef, mpp, level, x, y, w, h}

    try:
        for s in samples:
            tile_id = s.get("tileId")
            img_ref = s.get("imageRef")
            if tile_id is None or img_ref is None:
                raise HTTPException(400, "sample missing tileId or imageRef")
            upload = form.get(img_ref)
            if upload is None or not hasattr(upload, "filename"):
                raise HTTPException(400, f"missing file for imageRef={img_ref}")
            content = await upload.read()
            img_path = batch_dir / (tile_id + ".png")
            img_path.write_bytes(content)

            # record metadata
            with Image.open(img_path) as im:
                w, h = im.size
            tile_meta[tile_id] = {
                "imageRef": img_ref,
                "mpp": float(s.get("mpp", 0.25)),
                "level": int(s.get("level", 0)),
                "x": int(s.get("x", 0)),
                "y": int(s.get("y", 0)),
                "width": w,
                "height": h,
            }

        # ── run HoVer-Net batch inference ──────────────────────────
        img_paths = list(batch_dir.glob("*.png"))
        if not img_paths:
            raise HTTPException(400, "no valid images in batch")

        t0 = time.time()
        infer_batch(img_paths, output_dir)
        infer_time = time.time() - t0

        # ── assemble per-sample results ────────────────────────────
        mat_dir = output_dir / "mat"
        results: list[dict[str, Any]] = []
        for s in samples:
            tile_id = s.get("tileId")
            meta = tile_meta.get(tile_id, {})
            base = {
                "tileId": tile_id,
                "imageRef": meta.get("imageRef", ""),
                "mpp": meta.get("mpp", 0.25),
                "level": meta.get("level", 0),
                "x": meta.get("x", 0),
                "y": meta.get("y", 0),
                "width": meta.get("width", 0),
                "height": meta.get("height", 0),
            }
            t1 = time.time()
            mat_path = mat_dir / f"{tile_id}.mat"
            try:
                if not mat_path.exists():
                    raise FileNotFoundError(f"mat file not found: {mat_path}")

                inst_map = read_inst_map(mat_path)
                polygons = extract_polygons(inst_map)
                q1, q2, q3 = compute_q_stats(
                    polygons, meta.get("width", 256), meta.get("height", 256), meta.get("mpp", 0.25)
                )

                # strip points to save bandwidth
                for p in polygons:
                    p.pop("_geom", None)

                results.append({
                    **base,
                    "nucleiPolygons": polygons,
                    "statsQ1": q1,
                    "statsQ2": q2,
                    "statsQ3": q3,
                    "meta": {
                        "nucleusCount": len(polygons),
                        "imageWidth": meta.get("width", 0),
                        "imageHeight": meta.get("height", 0),
                        "latencyMs": round((time.time() - t1) * 1000, 2),
                    },
                })
            except Exception as ex:
                results.append({
                    **base,
                    "error": str(ex),
                    "meta": {"latencyMs": round((time.time() - t1) * 1000, 2)},
                })

        success_count = sum(1 for r in results if "error" not in r)
        return {
            "requestId": request_id,
            "successCount": success_count,
            "failedCount": len(results) - success_count,
            "inferTimeS": round(infer_time, 2),
            "results": results,
        }

    finally:
        shutil.rmtree(batch_dir, ignore_errors=True)
        shutil.rmtree(output_dir, ignore_errors=True)
