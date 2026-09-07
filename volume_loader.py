"""
Volume Loader — 3D hacim verisini farklı formatlardan yükler.

Desteklenen formatlar:
  • NIfTI  (.nii, .nii.gz)
  • DICOM serisi (klasördeki .dcm dosyaları) — multi-seri desteği ile
  • DICOM-SEG (.dcm, Modality=SEG) — pydicom-seg ile
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
        # Derinlemesine (recursive) dosya taraması — DICOM dosyaları
        # alt klasörlere gömülü olabilir (örn. PROSTATEx hasta dizinleri)
        all_files = [f for f in p.rglob("*") if f.is_file()]

        # NIfTI dosyası var mı?
        nifti_files = [
            f for f in all_files
            if f.name.lower().endswith(".nii.gz") or f.name.lower().endswith(".nii")
        ]
        if nifti_files:
            return "nifti"

        # DICOM dosyaları var mı?
        dicom_files = [
            f for f in all_files
            if f.suffix.lower() in config.DICOM_EXTENSIONS
        ]
        if dicom_files:
            return "dicom"

        # Uzantısız DICOM dosyalarını kontrol et (hastane formatı)
        no_ext_files = [f for f in all_files if f.suffix == ""]
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
            f for f in all_files
            if f.suffix.lower() in config.IMAGE_EXTENSIONS
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


# ---------------------------------------------------------------------------
# DICOM yardımcıları — seri tarama + sınıflandırma
# ---------------------------------------------------------------------------

def _scan_dicom_series(folder: str) -> dict:
    """Bir klasördeki tüm DICOM dosyalarını SeriesInstanceUID bazında gruplar.

    Returns:
        {
          "<SeriesInstanceUID>": {
            "files":       [pydicom.Dataset, ...],  # piksel dahil okunmuş
            "description": str,                     # SeriesDescription
            "modality":    str,                     # Modality tag (MR / SEG / ...)
            "role":        str,                     # Tahmin edilen rol (T2W, ADC, DWI, SEG, ...)
          }, ...
        }
    """
    import pydicom
    from collections import defaultdict

    # Adim 1: header'ları oku (hızlı), seri UID'ye göre grupla
    header_map: dict = defaultdict(list)
    for f in sorted(Path(folder).rglob("*")):
        if not f.is_file():
            continue
        if f.suffix.lower() not in config.DICOM_EXTENSIONS and f.suffix != "":
            continue
        try:
            ds = pydicom.dcmread(str(f), stop_before_pixels=True)
            uid = str(getattr(ds, "SeriesInstanceUID", "unknown"))
            header_map[uid].append((f, ds))
        except Exception:
            continue

    if not header_map:
        raise FileNotFoundError("Klasörde DICOM dosyası bulunamadı.")

    # Adim 2: her seri için tam okuma yap
    series_map: dict = {}
    for uid, entries in header_map.items():
        # Seri bilgilerini ilk header'dan al
        first_ds = entries[0][1]
        description = str(getattr(first_ds, "SeriesDescription", "")).strip()
        modality    = str(getattr(first_ds, "Modality", "MR")).strip().upper()

        role = _classify_series(description, modality)

        # SEG dosyalarını full okumaya gerek yok; pixel_array için pydicom-seg kullanır
        if modality == "SEG":
            series_map[uid] = {
                "files":       [str(p) for p, _ in entries],
                "description": description,
                "modality":    modality,
                "role":        role,
            }
            continue

        # Normal MR seri: piksellerle birlikte oku
        full_datasets = []
        for f, _ in entries:
            try:
                ds_full = pydicom.dcmread(str(f), stop_before_pixels=False)
                if hasattr(ds_full, "pixel_array"):
                    full_datasets.append(ds_full)
            except Exception:
                continue

        if not full_datasets:
            continue

        series_map[uid] = {
            "files":       full_datasets,
            "description": description,
            "modality":    modality,
            "role":        role,
        }

    return series_map


def _classify_series(description: str, modality: str = "MR") -> str:
    """SeriesDescription ve Modality'den seri rolünü tahmin eder.

    Returns: "T2W" | "ADC" | "DWI" | "DCE" | "KTRANS" | "SEG" | "OTHER"
    """
    if modality == "SEG":
        return "SEG"

    desc_lower = description.lower()

    # ADC önce kontrol edilmeli (çünkü DWI keyword'leri içerebilir)
    for kw in config.SERIES_ROLE_KEYWORDS.get("ADC", []):
        if kw in desc_lower:
            return "ADC"

    for role, keywords in config.SERIES_ROLE_KEYWORDS.items():
        if role == "ADC":
            continue  # zaten kontrol ettik
        for kw in keywords:
            if kw in desc_lower:
                return role

    return "OTHER"


def _sort_dicom_slices(datasets: list) -> list:
    """Dataset listesini uzaysal Z pozisyonuna göre sıralar.

    Önce ImagePositionPatient[2] dener, sonra SliceLocation, son çare InstanceNumber.
    """
    try:
        return sorted(datasets, key=lambda d: float(d.ImagePositionPatient[2]))
    except (AttributeError, IndexError, ValueError):
        pass
    try:
        return sorted(datasets, key=lambda d: float(d.SliceLocation))
    except (AttributeError, ValueError):
        pass
    try:
        return sorted(datasets, key=lambda d: float(d.InstanceNumber))
    except (AttributeError, ValueError):
        pass
    return datasets  # sıralama yapılamadıysa as-is


def _load_dicom_series(datasets: list) -> tuple[np.ndarray, tuple[float, float, float]]:
    """Tek bir DICOM seri listesini (Dataset listesi) volume'a dönüştürür."""
    datasets = _sort_dicom_slices(datasets)

    slices = []
    for ds in datasets:
        arr = ds.pixel_array.astype(np.float64)
        slope     = float(getattr(ds, "RescaleSlope",     1.0))
        intercept = float(getattr(ds, "RescaleIntercept", 0.0))
        arr = arr * slope + intercept
        slices.append(arr)

    volume = np.stack(slices, axis=0)  # (slices, H, W)

    # Spacing
    try:
        last_ds = datasets[-1]
        ps = last_ds.PixelSpacing
        st = float(getattr(last_ds, "SliceThickness",
                           getattr(last_ds, "SpacingBetweenSlices", 1.0)))
        spacing = (st, float(ps[0]), float(ps[1]))
    except (AttributeError, IndexError):
        spacing = (1.0, 1.0, 1.0)

    return _normalize_to_uint8(volume), spacing


def _load_dicom(folder: str) -> tuple[
    np.ndarray,
    tuple[float, float, float],
    dict,   # available_series bilgisi (role -> {desc, uid, slice_count})
    dict,   # seg_masks (label_name -> ndarray)
]:
    """Bir DICOM klasöründen T2W volume'u yükler, diğer serileri ve SEG'i raporlar.

    Returns:
        (volume, spacing, series_info, seg_masks)
    """
    series_map = _scan_dicom_series(folder)

    if not series_map:
        raise FileNotFoundError("Klasörde geçerli DICOM serisi bulunamadı.")

    # SEG dosyalarını ayır
    seg_uids = [uid for uid, info in series_map.items() if info["role"] == "SEG"]
    img_uids = [uid for uid, info in series_map.items() if info["role"] != "SEG"]

    # Sıralama öncelik sırası ile yüklenecek ana seriyi seç
    PRIORITY = ["T2W", "ADC", "DWI", "DCE", "OTHER"]
    selected_uid = None
    for role in PRIORITY:
        for uid in img_uids:
            if series_map[uid]["role"] == role:
                selected_uid = uid
                break
        if selected_uid:
            break
    if not selected_uid and img_uids:
        selected_uid = img_uids[0]

    if not selected_uid:
        raise FileNotFoundError("Yuklenebilir MR serisi bulunamadı.")

    # Seçilen seriyi yükle
    vol, sp = _load_dicom_series(series_map[selected_uid]["files"])

    # Series bilgisini özetle (UI için)
    series_info = {}
    for uid in img_uids:
        info = series_map[uid]
        role = info["role"]
        # Her rol için ilk seriyi al
        if role not in series_info:
            files = info["files"]
            series_info[role] = {
                "uid":         uid,
                "description": info["description"],
                "slice_count": len(files),
                "selected":    (uid == selected_uid),
                "role":        role,
            }

    # SEG mask'lerini yükle
    seg_masks = {}
    for uid in seg_uids:
        paths = series_map[uid]["files"]  # string listesi
        for path in paths:
            try:
                masks = _load_dicom_seg(path)
                seg_masks.update(masks)
            except Exception as e:
                print(f"SEG yüklenemedi ({path}): {e}")

    return vol, sp, series_info, seg_masks


def _load_dicom_seg(path: str) -> dict:
    """DICOM-SEG dosyasını okur ve segment mask'lerini döner.

    highdicom kullanır (numpy 2.x uyumlu). pydicom-seg fallback olarak denenir.

    Returns:
        {"Peripheral Zone": ndarray(Z, H, W, dtype=uint8), ...}
    """
    # --- highdicom yolu (tercihli) ---
    try:
        import highdicom as hd
        import pydicom

        dcm = pydicom.dcmread(path)
        seg = hd.seg.segread(dcm)

        masks = {}
        for seg_num in range(1, len(seg.SegmentSequence) + 1):
            seg_info  = seg.SegmentSequence[seg_num - 1]
            raw_label = str(getattr(seg_info, "SegmentDescription", f"Segment {seg_num}")).strip()
            label     = config.DICOM_SEG_LABEL_MAP.get(raw_label, raw_label)

            # highdicom: get_pixels_by_source_frame veya direct pixel array
            arr = seg.pixel_array  # (frames, H, W) veya (H, W)
            if arr.ndim == 2:
                arr = arr[np.newaxis, ...]   # (1, H, W)

            # Çok segmentli dosyada segment sayısına göre frame slice al
            total_segs  = len(seg.SegmentSequence)
            total_frames = arr.shape[0]
            if total_segs > 1:
                frames_per_seg = total_frames // total_segs
                start = (seg_num - 1) * frames_per_seg
                end   = start + frames_per_seg
                arr   = arr[start:end]

            masks[label] = (arr > 0).astype(np.uint8)

        return masks

    except Exception as hd_err:
        # --- pydicom-seg fallback ---
        try:
            import pydicom
            import pydicom_seg

            dcm    = pydicom.dcmread(path)
            reader = pydicom_seg.SegmentReader()
            result = reader.read(dcm)

            masks = {}
            for seg_num in result.available_segments:
                seg_info  = result.segment_infos[seg_num]
                raw_label = str(getattr(seg_info, "SegmentDescription",
                                         f"Segment {seg_num}")).strip()
                label = config.DICOM_SEG_LABEL_MAP.get(raw_label, raw_label)
                arr   = result.segment_data(seg_num)
                masks[label] = (arr > 0).astype(np.uint8)

            return masks

        except ImportError:
            raise ImportError(
                f"DICOM-SEG yüklemek için 'highdicom' veya 'pydicom-seg' kurulu olmalı. "
                f"highdicom hatası: {hd_err}. "
                f"Kurmak için: pip install highdicom"
            )
        except Exception as seg_err:
            raise RuntimeError(
                f"DICOM-SEG okunamadı. highdicom: {hd_err} | pydicom-seg: {seg_err}"
            )



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
        # Multi-seri DICOM bilgisi
        self._available_series: dict = {}   # role -> {uid, description, slice_count, selected}
        self._selected_role: str = ""
        self._series_map_cache: dict = {}   # uid -> {files, description, modality, role}
        # DICOM-SEG
        self._seg_masks: dict = {}          # label_name -> ndarray(Z, H, W)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

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

    @property
    def available_series(self) -> dict:
        """Tespit edilen DICOM serileri (role -> bilgi sözlüğü)."""
        return self._available_series

    @property
    def selected_series_role(self) -> str:
        """Aktif olarak gösterilen serinin rolü (T2W / ADC / DWI / ...)."""
        return self._selected_role

    @property
    def seg_masks(self) -> dict:
        """DICOM-SEG'den yüklenen segment mask'leri {label: ndarray}."""
        return self._seg_masks

    # ------------------------------------------------------------------
    # Yükleme
    # ------------------------------------------------------------------

    def load(self, path: str) -> np.ndarray:
        """Verilen yoldan 3D hacim verisini yükler.

        Args:
            path: Dosya veya klasör yolu.

        Returns:
            3D numpy array (slices, H, W), dtype=uint8.
        """
        fmt = _detect_format(path)
        self._format = fmt
        self._available_series = {}
        self._selected_role = ""
        self._seg_masks = {}
        self._series_map_cache = {}

        if fmt == "nifti":
            vol, sp = _load_nifti(path)
        elif fmt == "dicom":
            vol, sp, series_info, seg_masks = _load_dicom(path)
            self._available_series = series_info
            self._seg_masks = seg_masks
            # Seçili rolü tespit et
            for role, info in series_info.items():
                if info.get("selected"):
                    self._selected_role = role
                    break
        elif fmt == "images":
            vol, sp = _load_images(path)
        else:
            raise ValueError(f"Bilinmeyen format: {fmt}")

        self._volume = vol
        self._spacing = sp
        self._source_path = path
        return vol

    def load_series(self, role: str) -> np.ndarray:
        """Farklı bir seriyi yükler (yalnızca DICOM format için).

        Args:
            role: "T2W", "ADC", "DWI" gibi seri rolü.

        Returns:
            3D numpy array (slices, H, W), dtype=uint8.

        Raises:
            ValueError: Seri mevcut değilse veya format DICOM değilse.
        """
        if self._format != "dicom":
            raise ValueError("Seri değiştirme yalnızca DICOM format için geçerlidir.")
        if role not in self._available_series:
            available = list(self._available_series.keys())
            raise ValueError(f"Seri bulunamadı: {role!r}. Mevcut seriler: {available}")

        # Orijinal klasörü yeniden tara (cache yoksa)
        if not self._series_map_cache:
            self._series_map_cache = _scan_dicom_series(self._source_path)

        # İstenen role ait uid'yi bul
        target_uid = self._available_series[role]["uid"]
        series_entry = self._series_map_cache.get(target_uid)
        if not series_entry:
            raise ValueError(f"{role} serisi bulunamadı.")

        vol, sp = _load_dicom_series(series_entry["files"])
        self._volume = vol
        self._spacing = sp
        self._selected_role = role

        # selected flag güncelle
        for r, info in self._available_series.items():
            info["selected"] = (r == role)

        return vol

    # ------------------------------------------------------------------
    # Erişim
    # ------------------------------------------------------------------

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
