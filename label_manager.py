"""
Label Manager — Per-slice etiket verisi yönetimi.

Her slice için, her etiket sınıfı için poligon listesi tutar.
Poligonlardan 3D binary mask ve birleşik label volume üretir.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

import config
from polygon_tool import PolygonData, polygon_to_mask


class LabelManager:
    """Per-slice poligon etiketlerini yönetir ve 3D mask üretir.

    data yapısı:
        _data[slice_idx] = [PolygonData, PolygonData, ...]
    """

    def __init__(self, volume_shape: Optional[tuple[int, int, int]] = None):
        """
        Args:
            volume_shape: (num_slices, H, W) — 3D hacim boyutu.
        """
        self._volume_shape = volume_shape  # (slices, H, W)
        self._data: dict[int, list[PolygonData]] = {}
        self._cache_dirty = True
        self._cached_label_volume: Optional[np.ndarray] = None

    def set_volume_shape(self, shape: tuple[int, int, int]):
        """Volume boyutunu günceller."""
        self._volume_shape = shape
        self._invalidate_cache()

    @property
    def volume_shape(self) -> Optional[tuple[int, int, int]]:
        return self._volume_shape

    # ----- Per-slice poligon yönetimi -----

    def add_polygon(self, slice_idx: int, polygon: PolygonData):
        """Belirtilen slice'a bir poligon ekler."""
        if slice_idx not in self._data:
            self._data[slice_idx] = []
        self._data[slice_idx].append(polygon)
        self._invalidate_cache()

    def remove_polygon(self, slice_idx: int, polygon_idx: int):
        """Belirtilen slice'dan bir poligonu siler."""
        if slice_idx in self._data and 0 <= polygon_idx < len(self._data[slice_idx]):
            self._data[slice_idx].pop(polygon_idx)
            if not self._data[slice_idx]:
                del self._data[slice_idx]
            self._invalidate_cache()

    def set_slice_polygons(self, slice_idx: int, polygons: list[PolygonData]):
        """Belirtilen slice'ın tüm poligonlarını değiştirir."""
        if polygons:
            self._data[slice_idx] = list(polygons)
        elif slice_idx in self._data:
            del self._data[slice_idx]
        self._invalidate_cache()

    def get_slice_polygons(self, slice_idx: int) -> list[PolygonData]:
        """Belirtilen slice'ın poligonlarını döner."""
        return list(self._data.get(slice_idx, []))

    def get_all_data(self) -> dict[int, list[PolygonData]]:
        """Tüm verilerin kopyasını döner."""
        return {k: list(v) for k, v in self._data.items()}

    def clear(self):
        """Tüm verileri temizler."""
        self._data.clear()
        self._invalidate_cache()

    def has_annotations(self) -> bool:
        """Herhangi bir etiket var mı?"""
        return bool(self._data)

    def get_labeled_slice_indices(self) -> set[int]:
        """Etiketlenmiş slice indekslerini döner."""
        return set(self._data.keys())

    # ----- 3D Mask üretimi -----

    def _invalidate_cache(self):
        self._cache_dirty = True
        self._cached_label_volume = None

    def get_mask_3d(self, label_name: str) -> np.ndarray:
        """Belirli bir etiket sınıfı için 3D binary mask döner.

        Returns:
            (slices, H, W) bool numpy array.
        """
        if self._volume_shape is None:
            raise RuntimeError("Volume boyutu ayarlanmamış.")

        num_slices, H, W = self._volume_shape
        mask = np.zeros((num_slices, H, W), dtype=bool)

        for slice_idx, polygons in self._data.items():
            if slice_idx >= num_slices:
                continue
            for poly in polygons:
                if poly.label_name == label_name:
                    slice_mask = polygon_to_mask(poly.points, (H, W))
                    mask[slice_idx] |= slice_mask

        return mask

    def get_combined_label_volume(self) -> np.ndarray:
        """Tüm etiketleri birleştiren 3D label volume döner.

        Her voxel, etiket indeksini içerir (0 = arka plan).
        Çakışmalarda son yazılan etiket kazanır.

        Returns:
            (slices, H, W) uint8 numpy array.
        """
        if not self._cache_dirty and self._cached_label_volume is not None:
            return self._cached_label_volume

        if self._volume_shape is None:
            raise RuntimeError("Volume boyutu ayarlanmamış.")

        num_slices, H, W = self._volume_shape
        label_vol = np.zeros((num_slices, H, W), dtype=np.uint8)

        for slice_idx, polygons in self._data.items():
            if slice_idx >= num_slices:
                continue
            for poly in polygons:
                label_idx = config.LABEL_INDICES.get(poly.label_name, 0)
                if label_idx == 0:
                    continue
                slice_mask = polygon_to_mask(poly.points, (H, W))
                label_vol[slice_idx][slice_mask] = label_idx

        self._cached_label_volume = label_vol
        self._cache_dirty = False
        return label_vol

    # ----- Serileştirme -----

    def to_dict(self) -> dict:
        """Tüm verileri serileştirilebilir dict'e dönüştürür."""
        result = {}
        for slice_idx, polygons in self._data.items():
            result[str(slice_idx)] = [p.to_dict() for p in polygons]
        return result

    def from_dict(self, data: dict):
        """Dict'ten verileri yükler."""
        self._data.clear()
        for slice_key, poly_list in data.items():
            idx = int(slice_key)
            self._data[idx] = [PolygonData.from_dict(d) for d in poly_list]
        self._invalidate_cache()

    # ----- İstatistik -----

    def get_stats(self) -> dict:
        """Etiketleme istatistikleri."""
        total_polygons = sum(len(v) for v in self._data.values())
        labeled_slices = len(self._data)

        per_label = {}
        for polygons in self._data.values():
            for poly in polygons:
                per_label[poly.label_name] = per_label.get(poly.label_name, 0) + 1

        return {
            "total_polygons": total_polygons,
            "labeled_slices": labeled_slices,
            "per_label": per_label,
        }
