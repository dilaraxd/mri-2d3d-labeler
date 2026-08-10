"""
Polygon Data & Mask Helpers — Web Backend.

Poligon veri yapıları ve 2D binary mask üretim yardımcıları.
"""

from __future__ import annotations

from typing import Optional
import numpy as np
from PIL import Image, ImageDraw


def polygon_to_mask(
    points: list[tuple[float, float]],
    shape: tuple[int, int],
) -> np.ndarray:
    """Poligon köşe koordinatlarından binary mask üretir.

    Args:
        points: [(x, y), ...] köşe koordinatları.
        shape: (H, W) mask boyutları.

    Returns:
        (H, W) bool numpy array.
    """
    mask_img = Image.new("L", (shape[1], shape[0]), 0)
    draw = ImageDraw.Draw(mask_img)
    if len(points) >= 3:
        xy = [(p[0], p[1]) for p in points]
        draw.polygon(xy, fill=255)
    return np.array(mask_img, dtype=bool)


class PolygonData:
    """Bir poligonun verilerini tutar."""

    def __init__(self, label_name: str, points: Optional[list[tuple[float, float]]] = None):
        self.label_name = label_name
        self.points: list[tuple[float, float]] = points or []

    def to_dict(self) -> dict:
        return {
            "label": self.label_name,
            "points": self.points,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PolygonData":
        return cls(label_name=d["label"], points=[tuple(p) for p in d["points"]])
