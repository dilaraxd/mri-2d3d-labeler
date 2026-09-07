import requests, os, zipfile, io, time

BASE = 'https://services.cancerimagingarchive.net/nbia-api/services/v1'
WADO = 'https://services.cancerimagingarchive.net/nbia-api/services/v2/getImage'

# Direkt hasta bazli sorgula
print('ProstateX-0001 serileri sorgulanıyor...')
r = requests.get(f'{BASE}/getSeries',
    params={'Collection': 'PROSTATEx', 'PatientID': 'ProstateX-0001'},
    timeout=30)

print(f'HTTP: {r.status_code}')
if r.ok and r.json():
    series = r.json()
    print(f'{len(series)} seri bulundu:')
    for s in series:
        uid  = s.get('SeriesInstanceUID', '')
        desc = s.get('SeriesDescription', '')
        mod  = s.get('Modality', '')
        imgs = s.get('ImageCount', '')
        print(f'  {mod:4} | {desc:30} | {imgs} image | {uid[:40]}...')
    
    out_base = os.path.join('sample_data', 'dicom', 'ProstateX-0001')
    os.makedirs(out_base, exist_ok=True)

    print()
    for i, s in enumerate(series):
        uid  = s.get('SeriesInstanceUID', '')
        desc = s.get('SeriesDescription', 'seri').replace('/', '_').replace(' ', '_')
        mod  = s.get('Modality', '')
        print(f'[{i+1}/{len(series)}] {mod} | {s.get("SeriesDescription","")} ...', end=' ', flush=True)
        try:
            r2 = requests.get(WADO, params={'SeriesInstanceUID': uid}, timeout=180)
            if r2.status_code == 200:
                z = zipfile.ZipFile(io.BytesIO(r2.content))
                sdir = os.path.join(out_base, desc)
                z.extractall(sdir)
                print(f'OK ({len(z.namelist())} dosya)')
            else:
                print(f'HTTP {r2.status_code}: {r2.text[:100]}')
        except Exception as e:
            print(f'HATA: {e}')
        time.sleep(0.5)

    print(f'Tamamlandi: {out_base}')
    for item in sorted(os.listdir(out_base)):
        count = len(os.listdir(os.path.join(out_base, item))) if os.path.isdir(os.path.join(out_base, item)) else '-'
        print(f'  {item}  ({count} dosya)')
else:
    print(f'Hata: {r.text[:300]}')
