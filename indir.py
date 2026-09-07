"""
PROSTATEx DICOM Indirme Scripti
Kullanim: python indir.py

- Sadece ProstateX-0001 indirir (test)
- ALL = True yaparak tum koleksiyonu indirebilirsin
"""
from nbiatoolkit import NBIAClient
import os

COLLECTION  = "PROSTATEx"
PATIENT_ID  = "ProstateX-0001"
ALL         = False

DOWNLOAD_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "sample_data", "dicom"
)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

client = NBIAClient()
print(f"Koleksiyon: {COLLECTION}")
print(f"Indirme klasoru: {DOWNLOAD_DIR}\n")

if PATIENT_ID and not ALL:
    series = client.getSeries(collection=COLLECTION, patientID=PATIENT_ID)
    print(f"'{PATIENT_ID}' icin {len(series)} seri bulundu.")
else:
    series = client.getSeries(collection=COLLECTION)
    print(f"Toplam {len(series)} seri.")

for i, s in enumerate(series[:8]):
    print(f"  [{i}] {s.get('Modality','?'):4s}  {s.get('SeriesDescription','?')}")

print()
print("Indirme basliyor...\n")
for i, s in enumerate(series):
    uid     = s["SeriesInstanceUID"]
    desc    = s.get("SeriesDescription", "seri")
    patient = s.get("PatientID", "unknown")
    pdir    = os.path.join(DOWNLOAD_DIR, patient)
    os.makedirs(pdir, exist_ok=True)
    print(f"[{i+1}/{len(series)}] {patient} / {desc} ...", end=" ", flush=True)
    try:
        client.downloadSeries(seriesInstanceUID=uid, downloadDir=pdir)
        print("OK")
    except Exception as e:
        print(f"HATA: {e}")

print(f"\nTamamlandi!\n  {DOWNLOAD_DIR}")
