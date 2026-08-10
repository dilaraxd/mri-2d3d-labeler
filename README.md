# 🧠 MR Labeler — Web Tabanlı MR Görüntü Etiketleme & 3D Görselleştirme

<p align="center">
  <b>Tıbbi MR ve Hacimsel Görüntüler için 2D Slice Poligon Etiketleme ve Anlık Three.js 3D Yüzey Görselleştirme Aracı</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python Version" />
  <img src="https://img.shields.io/badge/Flask-3.0+-000000?style=flat-square&logo=flask&logoColor=white" alt="Flask" />
  <img src="https://img.shields.io/badge/Three.js-r128-black?style=flat-square&logo=three.js&logoColor=white" alt="Three.js" />
  <img src="https://img.shields.io/badge/HTML5-Canvas-E34F26?style=flat-square&logo=html5&logoColor=white" alt="HTML5 Canvas" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License" />
</p>

---

## 📖 Genel Bakış

**MR Labeler**, manyetik rezonans (MR), BT ve 3D hacimsel tıbbi görüntüleri tarayıcı üzerinden kolayca incelemek, slice bazında piksel hassasiyetinde poligon etiketleri oluşturmak ve bu etiketleri anında **Marching Cubes** algoritması ile 3D mesh modeline dönüştürerek interaktif şekilde görselleştirmek için geliştirilmiş modern bir web uygulamasıdır.

Masaüstü GUI bağımlılıkları (PyQt, VTK vb.) gerektirmez; tamamen hafif bir **Flask REST API** backend ve **HTML5 Canvas + Three.js** frontend mimarisiyle çalışır.

---

## ✨ Temel Özellikler

### 🖼️ 1. Çoklu Format Desteği & Sürükle-Bırak
- **NIfTI** (`.nii`, `.nii.gz`) dosyaları
- **DICOM** (`.dcm`, `.dicom`) serileri ve klasörleri
- **Sıralı Görüntüler** (`.png`, `.jpg`, `.jpeg`, `.bmp`, `.tiff`)
- Tarayıcıya doğrudan dosya veya klasör sürükleyip bırakarak anında yükleme.

### ✏️ 2. 2D Slice Etiketleme & Poligon Aracı
- **HTML5 Canvas** üzerinde yüksek performanslı görüntüleme.
- **Akıcı Pan & Zoom**: Fare tekerleğiyle yakınlaşma, `Space` + sürükleme veya fare orta tuşu ile kaydırma.
- **Poligon Çizimi**: Sol tık ile köşe noktası ekleme, sağ tık veya çift tık ile poligonu kapatma.
- **Hızlı Düzeltme**: `Ctrl+Z` ile son köşeyi/işlemi geri alma, `Delete` ile son poligonu silme.
- **Slice Gezintisi**: Slider çubuğu, `←` / `→` ok tuşları veya `A` / `D` tuşları ile anında geçiş.

### 🧊 3. Anlık 3D Görselleştirme (Three.js)
- 2D üzerinde çizilen tüm poligonlar arka planda **Marching Cubes** algoritması ile 3D yüzey mesh'lerine dönüştürülür.
- **OrbitControls**: 3D uzayda fare ile serbest döndürme, yakınlaştırma ve kaydırma.
- **Katman Yönetimi**: Her etiket sınıfının 3D görünürlüğünü tek tek açıp kapatabilme.
- **Opaklık Ayarları**: Hacim sınırları ve etiket yüzeyleri için bağımsız şeffaflık ayarı.

### 💾 4. Çift Formatlı Veri Dışa Aktarma
1. **`annotations.json`**: Tüm slice'lardaki poligon köşe koordinatlarını içeren, insan tarafından okunabilir ve hafif JSON formatı (tek tıkla indirilebilir).
2. **`label_masks.npz`**: Derin öğrenme ve segmentasyon modelleri (UNet, nnU-Net, V-Net vb.) için hazır 3D NumPy binary maske dizileri.

---

## 🚀 Hızlı Başlangıç

### 1. Gereksinimleri Yükleyin

```bash
pip install -r requirements.txt
```

### 2. Uygulamayı Başlatın

```bash
python app.py
```

### 3. Tarayıcınızda Açın

Tarayıcınızı açıp aşağıdaki adrese gidin:
👉 **[http://localhost:5000](http://localhost:5000)**

---

## ⌨️ Klavye ve Fare Kısayolları

| Eylem | Kısayol |
|---|---|
| **Köşe Noktası Ekle** | Sol Tık |
| **Poligonu Kapat** | Sağ Tık veya Çift Tık |
| **Çizimi İptal Et** | `Esc` |
| **Geri Al (Köşe / Poligon)** | `Ctrl + Z` |
| **Son Poligonu Sil** | `Delete` |
| **Yakınlaş / Uzaklaş (Zoom)** | Fare Tekerleği |
| **Görüntüyü Kaydır (Pan)** | `Space` + Sol Tık Sürükleme veya Fare Orta Tuşu |
| **Sonraki Slice** | `→` (Sağ Ok) veya `D` |
| **Önceki Slice** | `←` (Sol Ok) veya `A` |

---

## ⚙️ Etiketleri ve Renkleri Özelleştirme

Etiket kategorilerini veya renklerini değiştirmek için `config.py` dosyasını düzenlemeniz yeterlidir:

```python
# config.py

# Etiket sınıflarınız
LABELS = [
    "Sağlıklı doku",
    "Şüpheli lezyon",
    "Tümör",
    "Kist",
    "Artefakt / kalite sorunu",
]

# Her etiket için RGBA renk tanımı (0-255)
LABEL_COLORS = {
    "Sağlıklı doku":            (76, 175, 80, 128),   # Yeşil
    "Şüpheli lezyon":           (255, 193, 7, 128),   # Sarı
    "Tümör":                    (244, 67, 54, 160),   # Kırmızı
    "Kist":                     (33, 150, 243, 128),  # Mavi
    "Artefakt / kalite sorunu": (158, 158, 158, 100), # Gri
}
```

---

## 📂 Proje Dizin Yapısı

```text
mr_labeler/
│
├── 🌐 app.py                 # Flask REST API ana web sunucusu
├── ⚙️ config.py              # Etiket listesi, renkler ve genel ayarlar
├── 🧠 volume_loader.py       # NIfTI, DICOM ve görüntü serisi yükleyici
├── 🏷️ label_manager.py       # Per-slice poligon yönetimi ve 3D mask üretimi
├── 📐 polygon_tool.py        # Poligon veri modelleri ve maske dönüştürücü
├── 💾 annotations_io.py      # JSON & NPZ formatında kayıt/yükleme I/O
├── 📦 requirements.txt       # Python bağımlılıkları listesi
│
├── 📁 templates/
│   └── index.html            # Web arayüzü ana HTML sayfası
│
├── 📁 static/
│   ├── 📁 css/
│   │   └── style.css         # Modern koyu tema CSS (Glassmorphism)
│   └── 📁 js/
│       ├── app.js            # Ana web uygulama orkestratörü
│       ├── slice_viewer.js   # Canvas 2D slice görüntüleyici & pan/zoom
│       ├── polygon_tool.js   # 2D Canvas poligon çizim aracı
│       └── viewer3d.js       # Three.js 3D görselleştirme kontrolörü
│
└── 📁 test_volume/           # Test amaçlı örnek MR slice görüntüleri (20 slice)
```

---

## 📊 Çıktı Formatı Örnekleri

### `annotations.json`
```json
{
  "version": 2,
  "volume_shape": [20, 256, 256],
  "labels": ["Sağlıklı doku", "Şüpheli lezyon", "Tümör", "Kist", "Artefakt / kalite sorunu"],
  "annotations": {
    "5": [
      {
        "label": "Tümör",
        "points": [[112.5, 98.0], [135.0, 102.5], [140.0, 125.0], [118.0, 130.0]]
      }
    ]
  }
}
```

---

<p align="center">
  Geliştirici dostu • Tıbbi görüntü işleme & yapay zeka eğitim veri seti hazırlığı için optimize edilmiştir.
</p>
