from __future__ import annotations

import math
import numpy as np
from shapely.geometry import Polygon

NORMAL_NUCLEUS_AREA_UM2 = 10.0
NORMAL_MAJOR_AXIS_UM = 5.0
HPF_AREA_MM2 = 0.196
REF_MPP_40X = 0.25


def _major_axis_px(poly: Polygon) -> float:
    try:
        rect = poly.minimum_rotated_rectangle
        coords = list(rect.exterior.coords)
        if len(coords) < 4:
            return float("nan")
        sides = []
        for i in range(3):
            dx = coords[i][0] - coords[i + 1][0]
            dy = coords[i][1] - coords[i + 1][1]
            sides.append(math.hypot(dx, dy))
        return float(max(sides))
    except Exception:
        return float("nan")


def compute_q_stats(nuclei: list[dict], image_w: int, image_h: int, mpp: float) -> tuple[dict, dict, dict]:
    if mpp <= 0:
        raise ValueError("mpp must be > 0")

    geoms = [n["_geom"] for n in nuclei]
    n = len(geoms)

    scale = mpp / REF_MPP_40X
    normal_area_um2 = NORMAL_NUCLEUS_AREA_UM2 * (scale ** 2)
    normal_major_axis_um = NORMAL_MAJOR_AXIS_UM * scale

    if n == 0:
        stats_q1 = {
            "totalNuclei": 0,
            "meanAreaPx": 0.0,
            "meanAreaUm2": 0.0,
            "enlargedCount": 0,
            "enlargedRatio": 0.0,
        }
        stats_q2 = {
            "meanMajorAxisPx": 0.0,
            "meanMajorAxisUm": 0.0,
            "atypiaIndex": 0.0,
            "majorAxisCv": 0.0,
            "meanCircularity": 0.0,
            "meanSolidity": 0.0,
        }
    else:
        area_px = np.array([g.area for g in geoms], dtype=float)
        area_um2 = area_px * (mpp ** 2)
        enlarged = area_um2 > normal_area_um2

        major_axis_px = np.array([_major_axis_px(g) for g in geoms], dtype=float)
        major_axis_px = major_axis_px[~np.isnan(major_axis_px)]
        major_axis_um = major_axis_px * mpp if major_axis_px.size else np.array([], dtype=float)

        circularity = []
        solidity = []
        for g in geoms:
            p = g.length if g.length > 0 else 1e-9
            circularity.append(float(max(0.0, min(1.0, (4.0 * math.pi * g.area) / (p ** 2)))))
            hull_area = g.convex_hull.area if g.convex_hull is not None else 0.0
            solidity.append(float(g.area / hull_area) if hull_area > 0 else 0.0)

        mean_major_um = float(np.mean(major_axis_um)) if major_axis_um.size else 0.0
        cv = float(np.std(major_axis_um) / mean_major_um) if major_axis_um.size and mean_major_um > 0 else 0.0

        stats_q1 = {
            "totalNuclei": int(n),
            "meanAreaPx": float(np.mean(area_px)),
            "meanAreaUm2": float(np.mean(area_um2)),
            "enlargedCount": int(np.sum(enlarged)),
            "enlargedRatio": float(np.mean(enlarged)),
        }
        stats_q2 = {
            "meanMajorAxisPx": float(np.mean(major_axis_px)) if major_axis_px.size else 0.0,
            "meanMajorAxisUm": mean_major_um,
            "atypiaIndex": float(mean_major_um / normal_major_axis_um) if normal_major_axis_um > 0 else 0.0,
            "majorAxisCv": cv,
            "meanCircularity": float(np.mean(circularity)) if circularity else 0.0,
            "meanSolidity": float(np.mean(solidity)) if solidity else 0.0,
        }

    patch_area_mm2 = (image_w * mpp / 1000.0) * (image_h * mpp / 1000.0)
    hpf_equivalent = patch_area_mm2 / HPF_AREA_MM2 if HPF_AREA_MM2 > 0 else 0.0
    density_per_hpf = (n / hpf_equivalent) if hpf_equivalent > 0 else 0.0

    stats_q3 = {
        "patchAreaMm2": float(patch_area_mm2),
        "hpfEquivalent": float(hpf_equivalent),
        "densityPerHpf": float(density_per_hpf),
    }

    return stats_q1, stats_q2, stats_q3
