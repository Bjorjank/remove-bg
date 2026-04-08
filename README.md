# Remove BG Batch Starter

Starter project sederhana untuk membangun tool penghapus background otomatis dengan dukungan batch upload.

Dashboard web sekarang tersedia di `/` agar proses upload batch bisa dilakukan lewat browser.

## Stack

- Python
- FastAPI
- rembg
- Pillow
- onnxruntime

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

## Instalasi

```bash
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Menjalankan API

```bash
uvicorn app.main:app --reload
```

Endpoint utama:

- `GET /`
- `GET /health`
- `POST /remove-batch`

Contoh upload banyak file lewat `curl`:

```bash
curl -X POST "http://127.0.0.1:8000/remove-batch" ^
  -H "accept: application/zip" ^
  -H "Content-Type: multipart/form-data" ^
  -F "files=@foto1.jpg" ^
  -F "files=@foto2.png" ^
  --output hasil.zip
```

## Menjalankan Batch dari Folder

```bash
py tools/process_folder.py .\input .\output
```

Semua hasil akan disimpan sebagai PNG transparan di folder output.

## Catatan Pengembangan Lanjutan

- Jika batch mulai besar, pindahkan pemrosesan ke Celery + Redis.
- Jika ada GPU NVIDIA, ganti `onnxruntime` ke `onnxruntime-gpu`.
- Jika ingin kualitas tepi yang lebih halus, Anda bisa ganti model `u2net` ke model lain yang didukung `rembg` atau integrasikan RMBG-1.4.
