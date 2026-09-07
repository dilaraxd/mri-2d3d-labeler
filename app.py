"""
MR Labeler — Flask Web Backend.

Mevcut Python modüllerini (volume_loader, label_manager, annotations_io, config)
REST API olarak sunar. Frontend HTML5 Canvas + Three.js ile çalışır.
"""

import io
import os
import gzip
import json
import tempfile
import shutil
import base64
from pathlib import Path

import numpy as np
import nibabel as nib
from PIL import Image
from flask import Flask, render_template, request, jsonify, send_file

import config
from volume_loader import VolumeLoader
from label_manager import LabelManager
from polygon_tool import PolygonData
import annotations_io

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500 MB max upload

# Global state (tek kullanıcılı basit senaryo)
_loader = VolumeLoader()
_label_manager = LabelManager()
_upload_dir: str | None = None


# ---------------------------------------------------------------------------
# Sayfa
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Ana sayfa."""
    return render_template("index.html")


# ---------------------------------------------------------------------------
# Veri seti / ornek API
# ---------------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))

# NIfTI / micro-US örnekleri
_LOCAL_SAMPLES   = os.path.join(_HERE, "sample_data")
_EXTERNAL_SAMPLES = os.path.join(
    _HERE, "..", "data", "Micro_Ultrasound_Prostate_Segmentation_Dataset",
    "test", "micro_ultrasound_scans",
)
SAMPLES_DIR = _LOCAL_SAMPLES if os.path.isdir(_LOCAL_SAMPLES) else _EXTERNAL_SAMPLES

# DICOM örnekleri — her alt-klasör bir hasta/seri temsil eder
_DICOM_SAMPLE_DIRS = [
    os.path.join(_HERE, "sample_data", "dicom"),
    os.path.join(_HERE, "sample_data", "dicom", "prostatex"),   # TCIA Data Retriever çıktısı
    os.path.join(_HERE, "..", "data", "dicom_samples"),
    os.path.join(_HERE, "..", "data", "PROSTATEx"),
    os.path.join(_HERE, "..", "data", "prostatex"),
]


def _nifti_samples():
    """NIfTI örneklerini tara."""
    if not os.path.isdir(SAMPLES_DIR):
        return []
    items = []
    for f in sorted(os.listdir(SAMPLES_DIR)):
        if f.endswith(".nii.gz"):
            sid = f[:-7]
        elif f.endswith(".nii"):
            sid = f[:-4]
        else:
            continue
        items.append({
            "id":    f"nifti::{sid}",
            "label": sid.replace("microUS_", "").replace("_", " "),
            "group": "NIfTI Samples",
            "path":  os.path.join(SAMPLES_DIR, f),
            "type":  "nifti",
        })
    return items


def _dicom_samples():
    """DICOM klasör örneklerini tara. Her klasör bir örnektir."""
    items = []
    seen_paths = set()
    # _DICOM_SAMPLE_DIRS'ın alt-klasörlerini de tara (TCIA çıktısı iç içe olabilir)
    expanded = []
    for base in _DICOM_SAMPLE_DIRS:
        if os.path.isdir(base):
            expanded.append(base)

    for base in expanded:
        for name in sorted(os.listdir(base)):
            full = os.path.join(base, name)
            if not os.path.isdir(full):
                continue
            # Zaten listelenmiş mi?
            norm = os.path.normpath(full)
            if norm in seen_paths:
                continue
            # Bu klasörün kendisi tarama kökü mü? (döngüsel eklemeden kaçın)
            if norm in [os.path.normpath(d) for d in expanded]:
                continue
            # DICOM dosyası içeriyor mu kontrol et (max 3 seviye)
            has_dcm = False
            for root, _, files in os.walk(full):
                depth = root[len(full):].count(os.sep)
                if depth > 3:
                    break
                if any(f.lower().endswith((".dcm", ".dicom", ".ima")) for f in files):
                    has_dcm = True
                    break
            if not has_dcm:
                continue
            seen_paths.add(norm)
            
            # Yolları frontend'e relative olarak gönder (güvenlik ve taşınabilirlik)
            rel_path = os.path.relpath(full, _HERE)
            # Windowstaki ters slashları düzelt
            rel_path = rel_path.replace("\\", "/")
            
            items.append({
                "id":    f"dicom::{rel_path}",
                "label": name,
                "group": "DICOM Dataset",
                "path":  rel_path,
                "type":  "dicom",
            })
    return items



def _all_samples():
    """Tüm örnekleri döner (NIfTI + DICOM)."""
    return _nifti_samples() + _dicom_samples()


# id -> sample bilgisi hızlı erişim
def _sample_by_id(sid: str) -> dict | None:
    for s in _all_samples():
        if s["id"] == sid:
            return s
    return None


@app.route("/api/samples")
def list_samples():
    """Tüm örnekleri grup bilgisiyle döner."""
    items = []
    for s in _all_samples():
        items.append({
            "id":    s["id"],
            "label": s["label"],
            "group": s["group"],
            "type":  s["type"],
        })
    return jsonify({"samples": items})


@app.route("/api/load_sample", methods=["POST"])
def load_sample():
    """Belirtilen örneği yükler (NIfTI veya DICOM klasör)."""
    global _upload_dir
    data = request.get_json() or {}
    sid  = data.get("id")

    sample = _sample_by_id(sid)
    if not sample:
        return jsonify({"error": "Ornek bulunamadi."}), 404

    if _upload_dir and os.path.exists(_upload_dir):
        shutil.rmtree(_upload_dir, ignore_errors=True)

    sample_path = sample["path"]
    sample_type = sample["type"]

    # Eğer yol relative ise (örneğin DICOM), _HERE (proje kökü) ile birleştir
    if not os.path.isabs(sample_path):
        sample_path = os.path.join(_HERE, sample_path)

    if not os.path.exists(sample_path):
        return jsonify({"error": f"Yol bulunamadi: {sample_path}"}), 404

    if sample_type == "nifti":
        # NIfTI: sembolik link ile geçici klasore kopyala
        _upload_dir = tempfile.mkdtemp(prefix="mr_sample_")
        try:
            os.symlink(sample_path, os.path.join(_upload_dir, os.path.basename(sample_path)))
        except (OSError, NotImplementedError):
            shutil.copy2(sample_path, _upload_dir)
    else:
        # DICOM: doğrudan klasörü kullan (kopyalamaya gerek yok)
        _upload_dir = sample_path

    try:
        _loader.load(_upload_dir)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    _label_manager.set_volume_shape(_loader.get_dimensions())
    _label_manager.clear()
    annotations_io.load_annotations(_upload_dir, _label_manager)

    shape = _loader.get_dimensions()
    return jsonify({
        "success":       True,
        "format":        _loader.detected_format or sample_type,
        "shape":         list(shape),
        "num_slices":    _loader.get_slice_count(),
        "spacing":       list(_loader.spacing),
        "series":        _loader.available_series,
        "selected_role": _loader.selected_series_role,
        "seg_available": bool(_loader.seg_masks),
        "seg_labels":    list(_loader.seg_masks.keys()),
    })


# ---------------------------------------------------------------------------
# Config API
# ---------------------------------------------------------------------------

@app.route("/api/config")
def get_config():
    """Etiket listesi, renkleri ve indekslerini döner."""
    label_colors_hex = {}
    for name, rgba in config.LABEL_COLORS.items():
        label_colors_hex[name] = {
            "r": rgba[0], "g": rgba[1], "b": rgba[2], "a": rgba[3],
            "hex": "#{:02x}{:02x}{:02x}".format(rgba[0], rgba[1], rgba[2]),
        }
    return jsonify({
        "labels": config.LABELS,
        "label_colors": label_colors_hex,
        "label_indices": config.LABEL_INDICES,
        "label_mode": config.LABEL_MODE,
    })


# ---------------------------------------------------------------------------
# Upload API
# ---------------------------------------------------------------------------

@app.route("/api/upload", methods=["POST"])
def upload_volume():
    """Dosya veya klasör yükleme.

    Form fields:
        files: birden fazla dosya (multipart)
        upload_type: "nifti" | "dicom" | "images"
    """
    global _upload_dir

    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "Dosya seçilmedi."}), 400

    # Geçici klasör oluştur
    if _upload_dir and os.path.exists(_upload_dir):
        shutil.rmtree(_upload_dir, ignore_errors=True)

    _upload_dir = tempfile.mkdtemp(prefix="mr_labeler_")

    # Dosyaları kaydet
    for f in files:
        # Güvenli dosya adı
        filename = f.filename or "unnamed"
        # Klasör yapısını koru (webkitdirectory ile gelen dosyalar)
        # "folder/subfolder/file.dcm" gibi yollar olabilir
        parts = filename.replace("\\", "/").split("/")
        if len(parts) > 1:
            # İlk klasör adını atla (üst klasör)
            rel_path = os.path.join(*parts[1:]) if len(parts) > 2 else parts[-1]
        else:
            rel_path = parts[-1]

        save_path = os.path.join(_upload_dir, rel_path)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        f.save(save_path)

    # Volume yükle
    try:
        _loader.load(_upload_dir)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    # Label manager ayarla
    shape = _loader.get_dimensions()
    _label_manager.set_volume_shape(shape)
    _label_manager.clear()

    # Mevcut etiketleri yükle
    annotations_io.load_annotations(_upload_dir, _label_manager)

    fmt = _loader.detected_format or "?"
    return jsonify({
        "success": True,
        "format": fmt,
        "shape": list(shape),
        "num_slices": _loader.get_slice_count(),
    })


# ---------------------------------------------------------------------------
# Slice API
# ---------------------------------------------------------------------------

@app.route("/api/volume/info")
def volume_info():
    """Yüklü volume bilgisi."""
    if not _loader.is_loaded:
        return jsonify({"loaded": False})

    shape = _loader.get_dimensions()
    return jsonify({
        "loaded":        True,
        "format":        _loader.detected_format,
        "shape":         list(shape),
        "num_slices":    _loader.get_slice_count(),
        "spacing":       list(_loader.spacing),
        "series":        _loader.available_series,
        "selected_role": _loader.selected_series_role,
        "seg_available": bool(_loader.seg_masks),
        "seg_labels":    list(_loader.seg_masks.keys()),
    })


# ---------------------------------------------------------------------------
# Seri seçimi API (PROSTATEx multi-seri DICOM için)
# ---------------------------------------------------------------------------

@app.route("/api/series")
def list_series():
    """Tespit edilen DICOM serilerini listeler."""
    if not _loader.is_loaded:
        return jsonify({"series": [], "selected_role": ""})

    series = []
    for role, info in _loader.available_series.items():
        series.append({
            "role":        role,
            "description": info.get("description", ""),
            "slice_count": info.get("slice_count", 0),
            "selected":    info.get("selected", False),
        })

    return jsonify({
        "series":        series,
        "selected_role": _loader.selected_series_role,
    })


@app.route("/api/series/select", methods=["POST"])
def select_series():
    """Aktif seriyi değiştirir."""
    if not _loader.is_loaded:
        return jsonify({"error": "Volume yüklenmemiş."}), 400

    data = request.get_json() or {}
    role = data.get("role", "").strip().upper()

    if not role:
        return jsonify({"error": "role alanı zorunlu."}), 400

    try:
        _loader.load_series(role)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    # LabelManager shape'i güncelle
    _label_manager.set_volume_shape(_loader.get_dimensions())
    _label_manager.clear()

    return jsonify({
        "success":       True,
        "role":          role,
        "num_slices":    _loader.get_slice_count(),
        "shape":         list(_loader.get_dimensions()),
        "spacing":       list(_loader.spacing),
    })


@app.route("/api/seg_masks")
def get_seg_masks():
    """DICOM-SEG'den yüklenen zone mask'lerini döner.

    Her segment için overlay bilgisi ve RLE kodlu mask verilir.
    Mask shape: (slices, H, W), dtype uint8.
    """
    if not _loader.is_loaded:
        return jsonify({"masks": {}})

    masks = _loader.seg_masks
    if not masks:
        return jsonify({"masks": {}})

    vol_shape = _loader.get_dimensions()  # (slices, H, W)
    result = {}
    for label, arr in masks.items():
        # Shape uyumsuzluğu kontrol et; gerekirse crop/pad
        z_vol = vol_shape[0]
        z_seg = arr.shape[0]
        if z_vol != z_seg:
            # Z ekseni eşitleme: kısa olanı 0-pad
            if z_seg < z_vol:
                pad = np.zeros((z_vol - z_seg, arr.shape[1], arr.shape[2]), dtype=np.uint8)
                arr = np.concatenate([arr, pad], axis=0)
            else:
                arr = arr[:z_vol]

        # Her slice için voxel sayısını hesapla
        voxel_counts = [int(arr[i].sum()) for i in range(arr.shape[0])]

        # Renk bilgisi
        rgba = config.LABEL_COLORS.get(label, (128, 128, 128, 120))

        # mask'i base64 ile encode et (uint8, flat)
        mask_bytes = arr.astype(np.uint8).tobytes()
        mask_b64   = base64.b64encode(mask_bytes).decode("ascii")

        result[label] = {
            "shape":        list(arr.shape),  # [Z, H, W]
            "voxel_counts": voxel_counts,
            "total_voxels": int(arr.sum()),
            "color": {
                "r": rgba[0] / 255.0,
                "g": rgba[1] / 255.0,
                "b": rgba[2] / 255.0,
                "a": rgba[3] / 255.0,
            },
            "mask_b64":  mask_b64,
        }

    return jsonify({"masks": result})


@app.route("/api/slice/<int:idx>")
def get_slice(idx: int):
    """Tek bir slice'ı PNG olarak döner."""
    if not _loader.is_loaded:
        return jsonify({"error": "Volume yüklenmemiş."}), 400

    try:
        slice_data = _loader.get_slice(idx)
    except (IndexError, RuntimeError) as e:
        return jsonify({"error": str(e)}), 400

    # numpy -> PNG
    img = Image.fromarray(slice_data, mode="L")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    return send_file(buf, mimetype="image/png")


# ---------------------------------------------------------------------------
# Polygon / Annotation API
# ---------------------------------------------------------------------------

@app.route("/api/polygons/<int:idx>", methods=["GET"])
def get_polygons(idx: int):
    """Slice'ın poligon verisini döner."""
    polygons = _label_manager.get_slice_polygons(idx)
    return jsonify({
        "slice_idx": idx,
        "polygons": [p.to_dict() for p in polygons],
    })


@app.route("/api/polygons/<int:idx>", methods=["POST"])
def set_polygons(idx: int):
    """Slice'a poligon kaydeder."""
    data = request.get_json()
    if data is None:
        return jsonify({"error": "JSON verisi gerekli."}), 400

    poly_list = data.get("polygons", [])
    polygons = [PolygonData.from_dict(d) for d in poly_list]
    _label_manager.set_slice_polygons(idx, polygons)

    return jsonify({"success": True, "count": len(polygons)})


@app.route("/api/polygons/<int:idx>", methods=["DELETE"])
def delete_polygons(idx: int):
    """Slice'ın tüm poligonlarını siler."""
    _label_manager.set_slice_polygons(idx, [])
    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# Save API
# ---------------------------------------------------------------------------

@app.route("/api/save", methods=["POST"])
def save_all():
    """Tüm etiketleri dosyaya kaydeder."""
    if not _loader.is_loaded:
        return jsonify({"error": "Volume yüklenmemiş."}), 400

    folder = _upload_dir or ""
    if not folder:
        return jsonify({"error": "Kayıt klasörü yok."}), 400

    try:
        annotations_io.save_annotations(_label_manager, folder)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/download/annotations")
def download_annotations():
    """annotations.json dosyasını indirir."""
    if not _upload_dir:
        return jsonify({"error": "Kayıt yok."}), 400

    json_path = os.path.join(_upload_dir, config.ANNOTATIONS_FILENAME)
    if not os.path.exists(json_path):
        # Önce kaydet
        if _loader.is_loaded:
            annotations_io.save_annotations(_label_manager, _upload_dir)

    if os.path.exists(json_path):
        return send_file(json_path, as_attachment=True, download_name="annotations.json")

    return jsonify({"error": "Dosya bulunamadı."}), 404


# ---------------------------------------------------------------------------
# Stats API
# ---------------------------------------------------------------------------

@app.route("/api/stats")
def get_stats():
    """Etiketleme istatistikleri."""
    stats = _label_manager.get_stats()
    total_slices = _loader.get_slice_count() if _loader.is_loaded else 0
    labeled_slices = len(_label_manager.get_labeled_slice_indices())
    return jsonify({
        "total_polygons": stats["total_polygons"],
        "labeled_slices": labeled_slices,
        "total_slices": total_slices,
        "per_label": stats.get("per_label", {}),
    })


# ---------------------------------------------------------------------------
# 3D API
# ---------------------------------------------------------------------------

@app.route("/api/volume3d")
def get_volume_3d():
    """3D volume verisini base64 olarak döner (downsampled)."""
    if not _loader.is_loaded:
        return jsonify({"error": "Volume yüklenmemiş."}), 400

    vol = _loader.volume
    spacing = _loader.spacing

    # Downsample if too large (max ~128^3 for browser performance)
    max_dim = 128
    shape = vol.shape
    factors = [max(1, s // max_dim) for s in shape]
    if any(f > 1 for f in factors):
        vol_ds = vol[::factors[0], ::factors[1], ::factors[2]]
    else:
        vol_ds = vol

    # float'a dönüştürüp base64 encode
    vol_bytes = vol_ds.astype(np.uint8).tobytes()
    vol_b64 = base64.b64encode(vol_bytes).decode("ascii")

    return jsonify({
        "shape": list(vol_ds.shape),
        "original_shape": list(shape),
        "spacing": list(spacing),
        "data": vol_b64,
        "dtype": "uint8",
    })


@app.route("/api/labels3d")
def get_labels_3d():
    """3D etiket mesh'lerini döner (Marching Cubes)."""
    if not _loader.is_loaded or not _label_manager.has_annotations():
        return jsonify({"meshes": {}})

    try:
        from skimage.measure import marching_cubes
    except ImportError:
        return jsonify({"error": "scikit-image kurulu değil."}), 500

    label_vol = _label_manager.get_combined_label_volume()
    spacing = _loader.spacing
    meshes = {}

    for label_name, label_idx in config.LABEL_INDICES.items():
        binary = (label_vol == label_idx).astype(np.float32)
        if not binary.any():
            continue

        try:
            # Gaussian blur for smoother surface
            from scipy.ndimage import gaussian_filter
            binary_smooth = gaussian_filter(binary, sigma=1.0)

            verts, faces, normals, _ = marching_cubes(
                binary_smooth, level=0.5, spacing=spacing
            )

            # Downsample mesh if too many vertices
            if len(verts) > 50000:
                step = max(1, len(faces) // 15000)
                faces = faces[::step]
                # Renumber vertices
                used = np.unique(faces)
                mapping = np.zeros(len(verts), dtype=int)
                mapping[used] = np.arange(len(used))
                verts = verts[used]
                normals = normals[used]
                faces = mapping[faces]

            rgba = config.LABEL_COLORS.get(label_name, (255, 255, 0, 128))
            meshes[label_name] = {
                "vertices": verts.tolist(),
                "faces": faces.tolist(),
                "normals": normals.tolist(),
                "color": {
                    "r": rgba[0] / 255.0,
                    "g": rgba[1] / 255.0,
                    "b": rgba[2] / 255.0,
                },
            }
        except Exception as e:
            print(f"Mesh hatası ({label_name}): {e}")
            continue

    return jsonify({"meshes": meshes})


# ---------------------------------------------------------------------------
# NIfTI API (NiiVue 3D viewer icin)
# ---------------------------------------------------------------------------

Z_SCALE = 22.0


def _affine():
    sz, sy, sx = (list(_loader.spacing) + [1, 1, 1])[:3]
    return np.diag([sx, sy, sz * Z_SCALE, 1.0])


def _send_nifti(arr):
    img = nib.Nifti1Image(np.ascontiguousarray(np.transpose(arr, (2, 1, 0))), _affine())
    buf = io.BytesIO(gzip.compress(img.to_bytes()))
    return send_file(buf, mimetype="application/gzip", download_name="vol.nii.gz")


@app.route("/api/nifti/volume")
def nifti_volume():
    if not _loader.is_loaded:
        return jsonify({"error": "Volume yuklenmemis."}), 400
    return _send_nifti(_loader.volume.astype(np.uint8))


@app.route("/api/nifti/labels")
def nifti_labels():
    if not _loader.is_loaded:
        return jsonify({"error": "Volume yuklenmemis."}), 400
    if _label_manager.has_annotations():
        lab = (_label_manager.get_combined_label_volume() > 0).astype(np.uint8) * 255
    else:
        lab = np.zeros(_loader.get_dimensions(), dtype=np.uint8)
    return _send_nifti(lab)


# ---------------------------------------------------------------------------
# Giriş noktası
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("MR Labeler Web - http://localhost:5000")
    app.run(debug=True, host="0.0.0.0", port=5000)
