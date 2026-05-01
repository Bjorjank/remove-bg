# Remove BG Batch Starter

Starter project sederhana untuk membangun tool penghapus background otomatis dengan dukungan batch upload.

Dashboard web tersedia di `/` agar proses upload batch bisa dilakukan lewat browser.

## Stack

- Python
- FastAPI
- rembg
- Pillow
- onnxruntime

Tested target:

- Python 3.14

## Struktur

```text
app/
  main.py
  services/background_removal.py
  static/
    index.html
    styles.css
    app.js
tools/
  process_folder.py
requirements.txt
Dockerfile
```

## Cara Menjalankan di Windows PowerShell

1. Buat virtual environment:

```powershell
py -m venv .venv
```

2. Install dependency tanpa perlu aktivasi manual:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Jika `pip` masih tersandung resolver atau wheel lama, upgrade dulu:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

3. Jalankan server:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Atau lebih praktis:

```powershell
.\start.ps1
```

4. Buka dashboard di browser:

```text
http://127.0.0.1:8000/
```

## Endpoint Utama

- `GET /`
- `GET /health`
- `POST /remove-batch`

## Catatan Penting

- `requirements.txt` sudah disesuaikan untuk Python 3.14 dan membiarkan `rembg` memilih versi `Pillow` yang kompatibel.
- Di Windows + Python 3.14, jalankan tanpa `--reload`. Dari audit log, mode `--reload` memicu `PermissionError: [WinError 5] Access is denied` pada `multiprocessing resource_sharer`, sehingga server tampak hidup sebentar lalu koneksi putus.
- Input sekarang divalidasi berdasarkan isi file gambar, bukan hanya ekstensi. File akan dinormalisasi ke PNG sebelum diproses, termasuk menerapkan EXIF Orientation agar foto portrait dari kamera/HP tidak ikut terputar setelah metadata hilang.
- Pipeline menambahkan padding konteks sementara sebelum inference dan membuangnya lagi setelah hasil PNG dibuat. Ini membantu foto yang subjeknya terlalu mepet tepi frame.
- Default model adalah `isnet-general-use` dengan alpha matting dan post-process mask aktif untuk kualitas tepi yang lebih halus. Proses pertama bisa lebih lama karena model baru perlu diunduh oleh `rembg`.
- Untuk gambar animasi seperti GIF, saat ini yang diproses adalah frame pertama.
- Saat pertama kali memproses gambar, `rembg` bisa mengunduh model terlebih dulu, jadi proses awal mungkin sedikit lebih lama.
- Jika PowerShell Anda mengizinkan aktivasi script, Anda juga boleh pakai cara ini:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Menjalankan Batch dari Folder

```powershell
.\.venv\Scripts\python.exe tools\process_folder.py .\input .\output
```

Semua hasil akan disimpan sebagai PNG transparan di folder output.

Untuk membandingkan model dan kualitas:

```powershell
.\.venv\Scripts\python.exe tools\process_folder.py .\input .\output-isnet --model isnet-general-use
.\.venv\Scripts\python.exe tools\process_folder.py .\input .\output-human --model u2net_human_seg
.\.venv\Scripts\python.exe tools\process_folder.py .\input .\output-u2net --model u2net
```

Untuk server, model dan opsi kualitas bisa diatur lewat environment:

```powershell
$env:REMOVE_BG_MODEL = "u2net_human_seg"
$env:REMOVE_BG_PADDING_RATIO = "0.10"
$env:REMOVE_BG_ALPHA_MATTING = "true"
.\start.ps1
```

## Contoh Upload Banyak File Lewat curl

```powershell
curl.exe -X POST "http://127.0.0.1:8000/remove-batch" -H "accept: application/zip" -F "files=@foto1.jpg" -F "files=@download.jfif" -o hasil.zip
```

## Catatan Pengembangan Lanjutan

- Jika batch mulai besar, pindahkan pemrosesan ke Celery + Redis.
- Jika ada GPU NVIDIA, ganti `onnxruntime` ke `onnxruntime-gpu`.
- Jika ingin kualitas tepi yang lebih halus, Anda bisa ganti model `u2net` ke model lain yang didukung `rembg` atau integrasikan RMBG-1.4.
