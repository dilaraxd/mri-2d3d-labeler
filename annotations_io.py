"""
Annotations I/O — Etiket verisi kaydetme ve yükleme.

İki format desteklenir:
  1. annotations.json  — Poligon köşe koordinatları (okunabilir)
  2. label_masks.npz   — 3D numpy mask dizisi (model eğitimi)
"""

from __future__ import annotations

import json
import os
from typing import Optional

import numpy as np

import config
from label_manager import LabelManager


def save_annotations(label_manager: LabelManager, folder: str):
    """Etiket verilerini dosyaya kaydeder.

    Args:
        label_manager: LabelManager nesnesi.
        folder: Kayıt klasörü.
    """
    # 1. JSON formatında poligon koordinatları
    json_path = os.path.join(folder, config.ANNOTATIONS_FILENAME)
    data = {
        "version": 2,
        "volume_shape": list(label_manager.volume_shape) if label_manager.volume_shape else None,
        "labels": config.LABELS,
        "label_indices": config.LABEL_INDICES,
        "annotations": label_manager.to_dict(),
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 2. NPZ formatında 3D mask
    if label_manager.volume_shape and label_manager.has_annotations():
        npz_path = os.path.join(folder, config.MASKS_FILENAME)
        masks = {}
        masks["combined"] = label_manager.get_combined_label_volume()
        for label_name in config.LABELS:
            safe_key = label_name.replace(" ", "_").replace("/", "_")
            try:
                masks[safe_key] = label_manager.get_mask_3d(label_name)
            except Exception:
                pass
        np.savez_compressed(npz_path, **masks)


def load_annotations(folder: str, label_manager: LabelManager) -> bool:
    """Etiket verilerini dosyadan yükler.

    Args:
        folder: Kayıt klasörü.
        label_manager: LabelManager nesnesi.

    Returns:
        True başarılıysa, False değilse.
    """
    json_path = os.path.join(folder, config.ANNOTATIONS_FILENAME)
    if not os.path.exists(json_path):
        return False

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return False

    version = data.get("version", 1)
    if version < 2:
        # Eski format (v1) — uyumsuz, atla
        return False

    annotations = data.get("annotations", {})
    label_manager.from_dict(annotations)
    return True
