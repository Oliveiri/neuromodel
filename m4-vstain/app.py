"""M4 Virtual Staining Service – FastAPI application.

POST /predict_batch  – batch virtual staining (CD3 / PAX5).
GET  /healthz        – liveness probe.
GET  /readyz         – readiness probe.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import torch
from fastapi import FastAPI, Form, HTTPException, Request
from PIL import Image

from infer import VirtualStainPredictor

# ── config ──────────────────────────────────────────────────────────────────

CHECKPOINT_DIR = os.getenv("M4_CHECKPOINT_DIR",
                           str(Path(__file__).resolve().parent / "checkpoints"))
MAX_BATCH_SIZE = int(os.getenv("M4_MAX_BATCH_SIZE", "64"))
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

predictor = VirtualStainPredictor(CHECKPOINT_DIR, torch.device(DEVICE))

app = FastAPI(title="M4 Virtual Stain Service", version="1.0.0")


# ── probes ──────────────────────────────────────────────────────────────────

@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    models = [t for t in ("CD3", "PAX5") if predictor.has_model(t)]
    if not models:
        raise HTTPException(503, "no model loaded")
    return {"status": "ready", "models": models}


# ── predict ─────────────────────────────────────────────────────────────────

@app.post("/predict_batch")
async def predict_batch(request: Request,
                        manifest: str = Form(...)) -> dict[str, Any]:
    try:
        manifest_obj = json.loads(manifest)
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"invalid manifest json: {e}")

    request_id = manifest_obj.get("requestId", f"req-{int(time.time()*1000)}")
    model_type = manifest_obj.get("modelType", "")
    samples: list[dict] = manifest_obj.get("samples", [])

    if not samples:
        raise HTTPException(400, "samples is empty")
    if len(samples) > MAX_BATCH_SIZE:
        raise HTTPException(400,
                            f"batch size {len(samples)} exceeds limit {MAX_BATCH_SIZE}")
    if model_type not in ("CD3", "PAX5"):
        raise HTTPException(400,
                            f"modelType must be CD3 or PAX5, got '{model_type}'")
    if not predictor.has_model(model_type):
        raise HTTPException(503, f"model {model_type} not loaded")

    # build imageRef → outputPath map & collect file refs
    file_map: dict[str, bytes] = {}
    output_path_map: dict[str, str] = {}

    form = await request.form()
    for key, value in form.items():
        if hasattr(value, "filename"):
            file_map[key] = await value.read()

    for s in samples:
        ref = s.get("imageRef", "")
        op = s.get("outputPath", "")
        if not ref:
            raise HTTPException(400, "sample missing imageRef")
        if not op:
            raise HTTPException(400, "sample missing outputPath")
        if ref not in file_map:
            raise HTTPException(400, f"missing uploaded file for imageRef={ref}")
        output_path_map[ref] = op

    # run inference
    images: list[Image.Image] = []
    output_paths: list[str] = []
    tile_ids: list[str] = []

    for s in samples:
        ref = s["imageRef"]
        img_bytes = file_map[ref]
        from io import BytesIO

        images.append(Image.open(BytesIO(img_bytes)).convert("RGB"))
        output_paths.append(s["outputPath"])
        tile_ids.append(s.get("tileId", ref))

    t0 = time.perf_counter()

    # save_batch runs model inference and writes PNGs to outputPath
    save_results = predictor.save_batch(images, output_paths, model_type)

    latency_ms = round((time.perf_counter() - t0) * 1000, 2)

    results: list[dict[str, Any]] = []
    for i, tile_id in enumerate(tile_ids):
        sr = save_results[i]
        r = {
            "tileId": tile_id,
            "status": sr["status"],
            "outputPath": sr["outputPath"],
            "meta": {"latencyMs": latency_ms},
        }
        results.append(r)

    success_count = sum(1 for r in results if r["status"] == "SUCCESS")

    return {
        "requestId": request_id,
        "modelType": model_type,
        "successCount": success_count,
        "failedCount": len(results) - success_count,
        "results": results,
    }
