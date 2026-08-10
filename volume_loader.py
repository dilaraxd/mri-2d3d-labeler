"""
Volume Loader — 3D hacim verisini farklı formatlardan yükler.

Desteklenen formatlar:
  • NIfTI  (.nii, .nii.gz)
  • DICOM serisi (klasördeki .dcm dosyaları)
  • Sıralı görüntüler (klasördeki .png/.jpg/.bmp/... dosyaları)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import numpy as np

import config


# ---------------------------------------------------------------------------
# Yardımcı: 3D array'i 0-255 uint8'e normalleştir
# ---------------------------------------------------------------------------

def _normalize_to_uint8(volume: np.ndarray) -> np.ndarray:
    """Volume'u float aralığından 0-255 uint8'e dönüştürür."""
    v = volume.astype(np.float64)
    vmin, vmax = v.min(), v.max()
    if vmax - vmin < 1e-8:
        return np.zeros_like(volume, dtype=np.uint8)
    v = (v - vmin) / (vmax - vmin) * 255.0
    return v.astype(np.uint8)


# ---------------------------------------------------------------------------
# Format algılama
# ---------------------------------------------------------------------------

def _detect_format(path: str) -> str:
    """Verilen yolun formatını algılar.

    Returns:
        "nifti", "dicom", "images", veya ValueError fırlatır.
    """
    p = Path(path)

    # Tek dosya: NIfTI olabilir
    if p.is_file():
        name_lower = p.name.lower()
        if name_lower.endswith(".nii.gz") or name_lower.endswith(".nii"):
            return "nifti"
        raise ValueError(f"Desteklenmeyen dosya formatı: {p.name}")

    # Klasör: DICOM veya sıralı görüntü
    if p.is_dir():
        children = list(p.iterdir())

        # NIfTI dosyası var mı?
        nifti_files = [
            f for f in children
            if f.is_file()
            and (f.name.lower().endswith(".nii.gz") or f.name.lower().endswith(".nii"))
        ]
        if nifti_files:
            return "nifti"

        # DICOM dosyaları var mı?
        dicom_files = [
            f for f in children
            if f.is_file()
            and f.suffix.lower() in config.DICOM_EXTENSIONS
        ]
        if dicom_files:
            return "dicom"

        # Uzantısız DICOM dosyalarını kontrol et (hastane formatı)
        no_ext_files = [f for f in children if f.is_file() and f.suffix == ""]
        if no_ext_files:
            # İlk dosyayı kontrol et
            try:
                import pydicom
                pydicom.dcmread(str(no_ext_files[0]), stop_before_pixels=True)
                return "dicom"
            except Exception:
                pass

        # Sıralı görüntüler
        img_files = [
            f for f in children
            if f.is_file()
            and f.suffix.lower() in config.IMAGE_EXTENSIONS
        ]
        if img_files:
            return "images"

        raise ValueError("Klasörde desteklenen formatta dosya bulunamadı.")

    raise ValueError(f"Yol bulunamadı: {path}")


# ---------------------------------------------------------------------------
# Format yükleyicileri
# ---------------------------------------------------------------------------

def _load_nifti(path: str) -> tuple[np.ndarray, tuple[float, float, float]]:
    """NIfTI dosyasını yükler."""
    import nibabel as nib

    p = Path(path)
    if p.is_dir():
        nii_files = sorted(
            f for f in p.iterdir()
            if f.name.lower().endswith(".nii.gz") or f.name.lower().endswith(".nii")
        )
        if not nii_files:
            raise FileNotFoundError("NIfTI dosyası bulunamadı.")
        filepath = str(nii_files[0])
    else:
        filepath = str(p)

    img = nib.load(filepath)
    data = np.asanyarray(img.dataobj)

    # 4D ise ilk hacmi al
    if data.ndim == 4:
        data = data[:, :, :, 0]
    if data.ndim != 3:
        raise ValueError(f"Beklenmeyen veri boyutu: {data.ndim}D (3D bekleniyor)")

    # Spacing
    header = img.header
    spacing = tuple(float(x) for x in header.get_zooms()[:3])
    if len(spacing) < 3:
        spacing = (1.0, 1.0, 1.0)

    # Eksenleri düzenle: (slices, H, W) yapısına getir
    # NIfTI varsayılan: (W, H, slices) -> transpose
    data = np.transpose(data, (2, 1, 0))

    return _normalize_to_uint8(data), spacing


def _load_dicom(folder: str) -> tuple[np.ndarray, tuple[float, float, float]]:
    """DICOM serisini yükler."""
    import pydicom

    p = Path(folder)
    dcm_files = []

    for f in sorted(p.iterdir()):
        if not f.is_file():
            continue
        try:
            ds = pydicom.dcmread(str(f), stop_before_pixels=False)
            if hasattr(ds, "pixel_array"):
                dcm_files.append(ds)
        except Exception:
            continue

    if not dcm_files:
        raise FileNotFoundError("DICOM dosyaları okunamadı veya piksel verisi yok.")

    # Instance number veya slice location'a göre sırala
    try:
        dcm_files.sort(key=lambda d: float(d.InstanceNumber))
    except (AttributeError, ValueError):
        try:
            dcm_files.sort(key=lambda d: float(d.SliceLocation))
        except (AttributeError, ValueError):
            pass  # dosya adı sırasını koru

    slices = []
    for ds in dcm_files:
        arr = ds.pixel_array.astype(np.float64)
        # Rescale uygula
        slope = getattr(ds, "RescaleSlope", 1.0)
        intercept = getattr(ds, "RescaleIntercept", 0.0)
        arr = arr * float(slope) + float(intercept)
        slices.append(arr)

    volume = np.stack(slices, axis=0)  # (slices, H, W)

    # Spacing
    try:
        ps = ds.PixelSpacing
        st = float(getattr(ds, "SliceThickness", getattr(ds, "SpacingBetweenSlices", 1.0)))
        spacing = (st, float(ps[0]), float(ps[1]))
    except (AttributeError, IndexError):
        spacing = (1.0, 1.0, 1.0)

    return _normalize_to_uint8(volume), spacing


def _load_images(folder: str) -> tuple[np.ndarray, tuple[float, float, float]]:
    """Sıralı görüntü dosyalarını yükler."""
    from PIL import Image

    p = Path(folder)
    img_files = sorted(
        f for f in p.iterdir()
        if f.is_file() and f.suffix.lower() in config.IMAGE_EXTENSIONS
    )

    if not img_files:
        raise FileNotFoundError("Klasörde görüntü dosyası bulunamadı.")

    slices = []
    for f in img_files:
        img = Image.open(str(f)).convert("L")  # Grayscale
        slices.append(np.array(img, dtype=np.uint8))

    volume = np.stack(slices, axis=0)  # (slices, H, W)
    spacing = (1.0, 1.0, 1.0)  # Sıralı görüntülerde spacing bilinmiyor

    return volume, spacing


# ---------------------------------------------------------------------------
# Ana yükleyici sınıf
# ---------------------------------------------------------------------------

class VolumeLoader:
    """3D hacim verisini yükler ve erişim sağlar."""

    def __init__(self):
        self._volume: Optional[np.ndarray] = None  # (slices, H, W) uint8
        self._spacing: tuple[float, float, float] = (1.0, 1.0, 1.0)
        self._source_path: Optional[str] = None
        self._format: Optional[str] = None

    @property
    def is_loaded(self) -> bool:
        return self._volume is not None

    @property
    def volume(self) -> Optional[np.ndarray]:
        return self._volume

    @property
    def spacing(self) -> tuple[float, float, float]:
        return self._spacing

    @property
    def source_path(self) -> Optional[str]:
        return self._source_path

    @property
    def detected_format(self) -> Optional[str]:
        return self._format

    def load(self, path: str) -> np.ndarray:
        """Verilen yoldan 3D hacim verisini yükler.

        Args:
            path: Dosya veya klasör yolu.

        Returns:
            3D numpy array (slices, H, W), dtype=uint8.
        """
        fmt = _detect_format(path)
        self._format = fmt

        if fmt == "nifti":
            vol, sp = _load_nifti(path)
        elif fmt == "dicom":
            vol, sp = _load_dicom(path)
        elif fmt == "images":
            vol, sp = _load_images(path)
        else:
            raise ValueError(f"Bilinmeyen format: {fmt}")

        self._volume = vol
        self._spacing = sp
        self._source_path = path
        return vol

    def get_slice_count(self) -> int:
        if self._volume is None:
            return 0
        return self._volume.shape[0]

    def get_slice(self, index: int) -> np.ndarray:
        """Tek bir 2D slice döner.

        Args:
            index: Slice indeksi (0-based).

        Returns:
            2D numpy array (H, W), dtype=uint8.
        """
        if self._volume is None:
            raise RuntimeError("Hacim verisi yüklenmemiş.")
        if not 0 <= index < self._volume.shape[0]:
            raise IndexError(f"Slice indeksi aralık dışı: {index}")
        return self._volume[index]

    def get_dimensions(self) -> tuple[int, int, int]:
        """(slices, height, width) döner."""
        if self._volume is None:
            return (0, 0, 0)
        return self._volume.shape
