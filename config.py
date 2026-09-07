"""
Etiketleme arayüzü ayarları.
Etiket listesini ve modunu buradan değiştir, main.py'ye dokunmana gerek yok.
"""

# ---------------------------------------------------------------------------
# Genel amaçlı etiketler (varsayılan)
# ---------------------------------------------------------------------------

LABELS = [
    "Sağlıklı doku",
    "Şüpheli lezyon",
    "Tümör",
    "Kist",
    "Artefakt / kalite sorunu",
]

# ---------------------------------------------------------------------------
# Prostat bölgesi etiketleri (PROSTATEx / PI-CAI için)
# ---------------------------------------------------------------------------

PROSTATE_LABELS = [
    "Peripheral Zone",
    "Transition Zone",
    "Suspicious Lesion",
    "Benign Tissue",
    "Artifact",
]

# ---------------------------------------------------------------------------
# DICOM-SEG segment isim eşleştirme tablosu
# PROSTATEx Zone Segmentations (dcmqi çıktısı) SNOMED etiket adları → uygulama etiket adları
# ---------------------------------------------------------------------------

DICOM_SEG_LABEL_MAP = {
    # SNOMED CID 7151 / dcmqi standart etiketleri
    "Peripheral zone of prostate":      "Peripheral Zone",
    "Transition zone of prostate":      "Transition Zone",
    "Fibromuscular stroma of prostate": "Fibromuscular Stroma",
    "Distal prostatic urethra":         "Distal Urethra",
    # Alternatif / kısa yazımlar
    "peripheral zone":   "Peripheral Zone",
    "transition zone":   "Transition Zone",
    "PZ":                "Peripheral Zone",
    "TZ":                "Transition Zone",
    "CG":                "Transition Zone",   # Central Gland
    "PZ_segmentation":   "Peripheral Zone",
    "TZ_segmentation":   "Transition Zone",
}

# ---------------------------------------------------------------------------
# PROSTATEx seri tanımlama anahtar kelimeleri
# SeriesDescription tag içinde bu kelimeler geçiyorsa ilgili role atanır
# ---------------------------------------------------------------------------

SERIES_ROLE_KEYWORDS = {
    "T2W": [
        "t2", "t2_tse", "t2w", "tse_tra", "tse_sag", "tse_cor",
        "t2_weighted", "t2 tse", "t2_tra",
    ],
    "ADC": [
        "adc", "apparent diffusion", "apprdiff",
        "_adc", "adc_map",
    ],
    "DWI": [
        "dwi", "diff", "diffusion", "ep2d_diff", "dyndist",
        "dti", "b800", "b1000",
    ],
    "KTRANS": [
        "ktrans", "k_trans",
    ],
    "DCE": [
        "dce", "dynamic", "perfusion", "tfl_3d",
    ],
}

# ---------------------------------------------------------------------------
# "multi"  -> kullanıcı aynı görüntüde birden fazla etiket seçebilir (checkbox)
# "single" -> kullanıcı sadece bir etiket seçebilir (radio button)
# ---------------------------------------------------------------------------
LABEL_MODE = "multi"

# Desteklenen görüntü uzantıları (klasörden yüklenirken filtrelenir)
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")

# Etiketlerin kaydedileceği dosya adı (seçilen klasörün içine yazılır)
ANNOTATIONS_FILENAME = "annotations.json"

# Etiket mask dosya adı
MASKS_FILENAME = "label_masks.npz"

# Etiket renkleri (RGBA, 0-255) — 3D ve 2D overlay'de kullanılır
LABEL_COLORS = {
    # Genel etiketler
    "Sağlıklı doku":             (76, 175, 80, 128),
    "Şüpheli lezyon":            (255, 193, 7, 128),
    "Tümör":                     (244, 67, 54, 160),
    "Kist":                      (33, 150, 243, 128),
    "Artefakt / kalite sorunu":  (158, 158, 158, 100),
    # Prostat zonu etiketleri
    "Peripheral Zone":           (33, 150, 243, 140),    # mavi
    "Transition Zone":           (76, 175, 80, 140),     # yeşil
    "Fibromuscular Stroma":      (255, 152, 0, 120),     # turuncu
    "Distal Urethra":            (156, 39, 176, 120),    # mor
    "Suspicious Lesion":         (244, 67, 54, 160),     # kırmızı
    "Benign Tissue":             (0, 188, 212, 120),     # cyan
    "Artifact":                  (158, 158, 158, 100),   # gri
}

# Etiket indeksleri (3D mask'ta kullanılır, 0 = arka plan)
LABEL_INDICES = {name: idx + 1 for idx, name in enumerate(LABELS)}

# Prostat etiket indeksleri
PROSTATE_LABEL_INDICES = {name: idx + 1 for idx, name in enumerate(PROSTATE_LABELS)}

# 3D render ayarları
VTK_BACKGROUND = (0.04, 0.06, 0.08)
VOLUME_OPACITY = 0.3
LABEL_SURFACE_OPACITY = 0.7

# NIfTI / DICOM desteklenen uzantılar
NIFTI_EXTENSIONS = (".nii", ".nii.gz")
DICOM_EXTENSIONS = (".dcm", ".dicom", ".ima")
