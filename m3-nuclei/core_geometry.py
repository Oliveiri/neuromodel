from __future__ import annotations

from shapely.geometry import Polygon, MultiPolygon
from typing import Any


def _polygon_to_points(poly: Polygon) -> list[list[float]]:
    xs, ys = poly.exterior.xy
    points: list[list[float]] = []
    # 去掉最后一个重复点
    for i in range(max(0, len(xs) - 1)):
        points.append([float(xs[i]), float(ys[i])])
    return points


def geometries_to_nuclei(geoms: list[Any]) -> list[dict]:
    nuclei: list[dict] = []
    nid = 0
    for geom in geoms:
        if geom is None or geom.is_empty:
            continue

        if isinstance(geom, MultiPolygon):
            polys = [g for g in geom.geoms if g is not None and not g.is_empty]
        elif isinstance(geom, Polygon):
            polys = [geom]
        else:
            continue

        for poly in polys:
            if poly.is_empty:
                continue
            nid += 1
            minx, miny, maxx, maxy = poly.bounds
            cx, cy = poly.centroid.x, poly.centroid.y
            nuclei.append({
                "nucleusId": f"n-{nid}",
                "polygon": _polygon_to_points(poly),
                "bbox": {
                    "x": float(minx),
                    "y": float(miny),
                    "width": float(maxx - minx),
                    "height": float(maxy - miny),
                },
                "areaPx": float(poly.area),
                "centroid": {"x": float(cx), "y": float(cy)},
                "_geom": poly,
            })
    return nuclei
