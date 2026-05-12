"""Batch inference for virtual staining models.

Handles: preprocess (PIL → tensor [-1,1]), GPU batch forward, postprocess
(tensor → PIL), and save to disk.
"""

from __future__ import annotations

import os
from pathlib import Path

import torch
import torchvision.transforms.functional as TF
from PIL import Image


# ── preprocessing / postprocessing ──────────────────────────────────────────

def preprocess(img: Image.Image, size: int = 256) -> torch.Tensor:
    """PIL RGB image → normalised tensor (C,H,W) in [-1, 1]."""
    if img.mode != "RGB":
        img = img.convert("RGB")
    img = img.resize((size, size), Image.BILINEAR)
    t = TF.to_tensor(img)              # [0, 1]
    return (t - 0.5) / 0.5             # [-1, 1]


def postprocess(tensor: torch.Tensor) -> Image.Image:
    """Tensor (C,H,W) in [-1, 1] → PIL RGB image."""
    t = (tensor * 0.5 + 0.5).clamp(0, 1)
    return TF.to_pil_image(t.cpu())


# ── batch predictor ─────────────────────────────────────────────────────────

class VirtualStainPredictor:
    """Holds two CycleGAN generators (CD3 / PAX5) and runs batch inference."""

    def __init__(self, checkpoint_dir: str, device: torch.device):
        from model import load_generator

        self.device = device
        self.models: dict[str, torch.nn.Module] = {}
        for model_type in ("CD3", "PAX5"):
            ckpt = Path(checkpoint_dir) / f"cyclegan_{model_type}" / "latest_net_G_A.pth"
            if ckpt.exists():
                self.models[model_type] = load_generator(str(ckpt), device)
            else:
                print(f"[WARN] checkpoint not found: {ckpt}")

    def predict_batch(self, images: list[Image.Image],
                      model_type: str) -> list[Image.Image]:
        """Run virtual staining on a batch of PIL images.

        Args:
            images: list of PIL RGB images (any size, will resize to 256×256).
            model_type: "CD3" or "PAX5".

        Returns:
            list of PIL RGB images (256×256), same order as input.
        """
        if model_type not in self.models:
            raise ValueError(
                f"unknown model_type={model_type}, "
                f"available={list(self.models.keys())}")
        model = self.models[model_type]

        tensors = [preprocess(img) for img in images]
        batch = torch.stack(tensors).to(self.device)

        with torch.no_grad():
            outputs = model(batch)

        return [postprocess(outputs[i]) for i in range(len(images))]

    def save_batch(self, images: list[Image.Image],
                   output_paths: list[str], model_type: str) -> list[dict]:
        """Predict and save each output image to its target path.

        Returns a list of result dicts compatible with the API response.
        """
        out_images = self.predict_batch(images, model_type)

        results: list[dict] = []

        for path_str, out_img in zip(output_paths, out_images):
            p = Path(path_str)
            p.parent.mkdir(parents=True, exist_ok=True)
            out_img.save(p, "PNG")

            results.append({
                "status": "SUCCESS",
                "outputPath": str(p),
            })

        return results

    def has_model(self, model_type: str) -> bool:
        return model_type in self.models
