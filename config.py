"""
Etiketleme arayüzü ayarları.
Etiket listesini ve modunu buradan değiştir, main.py'ye dokunmana gerek yok.
"""

# Kullanıcının işaretleyebileceği etiketler — kendi kategorilerinle değiştir
LABELS = [
    "Sağlıklı doku",
    "Şüpheli lezyon",
    "Tümör",
    "Kist",
    "Artefakt / kalite sorunu",
]

# "multi"  -> kullanıcı aynı görüntüde birden fazla etiket seçebilir (checkbox)
# "single" -> kullanıcı sadece bir etiket seçebilir (radio button)
LABEL_MODE = "multi"

# Desteklenen görüntü uzantıları (klasörden yüklenirken filtrelenir)
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")

# Etiketlerin kaydedileceği dosya adı (seçilen klasörün içine yazılır)
ANNOTATIONS_FILENAME = "annotations.json"

# Etiket mask dosya adı
MASKS_FILENAME = "label_masks.npz"

# Etiket renkleri (RGBA, 0-255) — 3D ve 2D overlay'de kullanılır
LABEL_COLORS = {
    "Sağlıklı doku":          (76, 175, 80, 128),
    "Şüpheli lezyon":         (255, 193, 7, 128),
    "Tümör":                  (244, 67, 54, 160),
    "Kist":                   (33, 150, 243, 128),
    "Artefakt / kalite sorunu": (158, 158, 158, 100),
}

# Etiket indeksleri (3D mask'ta kullanılır, 0 = arka plan)
LABEL_INDICES = {name: idx + 1 for idx, name in enumerate(LABELS)}

# 3D render ayarları
VTK_BACKGROUND = (0.04, 0.06, 0.08)
VOLUME_OPACITY = 0.3
LABEL_SURFACE_OPACITY = 0.7

# NIfTI / DICOM desteklenen uzantılar
NIFTI_EXTENSIONS = (".nii", ".nii.gz")
DICOM_EXTENSIONS = (".dcm", ".dicom", ".ima")
