"""Reproducible source-app checks. AI inference is deliberately stubbed.

No external datasets, real client data or model downloads in this suite.
"""
import io
import os
import sys
import zipfile
from pathlib import Path

from PIL import Image, ImageOps
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
STUBS = ROOT / "tests" / "support_stubs"
sys.path.insert(0, str(STUBS))  # intentional: inject a non-inference model test double

from app.main import app, MAX_FILES_PER_BATCH
from app.services.background_removal import (
    RemovalOptions,
    ProcessedImage,
    add_context_padding,
    build_zip_archive,
    normalize_image_bytes,
    resize_for_inference,
    sanitize_filename,
)

client = TestClient(app)

def make_image(*, size=(80, 50), color=(17, 106, 188), exif_orientation=None):
    image = Image.new("RGB", size, color)
    out = io.BytesIO()
    if exif_orientation:
        exif = Image.Exif()
        exif[274] = exif_orientation
        image.save(out, format="JPEG", exif=exif)
    else:
        image.save(out, format="PNG")
    return out.getvalue()

def test_dashboard_is_served_from_original_app():
    page = client.get("/")
    assert page.status_code == 200
    assert "Batch Background Removal" in page.text
    assert "/static/styles.css" in page.text
    assert "/static/app.js" in page.text

def test_static_assets_are_reachable():
    assert client.get("/static/styles.css").status_code == 200
    assert client.get("/static/app.js").status_code == 200

def test_health_returns_real_application_settings():
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert int(payload["max_files_per_batch"]) == MAX_FILES_PER_BATCH == 50

def test_batch_upload_count_limit():
    payload = [("files", (f"sample_{i}.png", make_image(), "image/png")) for i in range(51)]
    response = client.post("/remove-batch", files=payload)
    assert response.status_code == 400
    assert "50" in response.json()["detail"]

def test_rejects_invalid_image_contents_not_just_extension():
    response = client.post("/remove-batch", files=[("files", ("fake.png", b"not-a-real-image", "image/png"))])
    assert response.status_code == 400
    assert "gambar valid" in response.json()["detail"]

def test_rejects_empty_images():
    response = client.post("/remove-batch", files=[("files", ("empty.png", b"", "image/png"))])
    assert response.status_code == 400
    assert "File kosong" in response.json()["detail"]

def test_end_to_end_http_zip_contract_with_mocked_model():
    response = client.post("/remove-batch", files=[
        ("files", ("sample_one.png", make_image(size=(40, 30)), "image/png")),
        ("files", ("sample-two.png", make_image(size=(64, 32)), "image/png")),
    ])
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/zip")
    assert "background-removed.zip" in response.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert sorted(archive.namelist()) == ["sample-two.png", "sample_one.png"]
        for name in archive.namelist():
            with Image.open(io.BytesIO(archive.read(name))) as img:
                assert img.format == "PNG"
                assert img.mode == "RGBA"
                assert img.size in ((40, 30), (64, 32))
    # Alpha pixels here are entirely opaque by design, because model inference is stubbed.

def test_exif_orientation_corrected_by_preprocessing():
    image_bytes = make_image(size=(80, 40), exif_orientation=6)
    normalized, _ = normalize_image_bytes(
        image_bytes, RemovalOptions(max_inference_side=2048, padding_ratio=0)
    )
    with Image.open(io.BytesIO(normalized)) as result:
        assert result.size == (40, 80)

def test_inference_input_resized_to_bound_dimensions():
    image = Image.new("RGB", (500, 200), (12, 34, 56))
    resized = resize_for_inference(image, max_side=100)
    assert resized.size == (100, 40)

def test_context_padding_is_finite_and_reversible():
    image = Image.new("RGB", (100, 80), "white")
    padded, dims = add_context_padding(image, RemovalOptions(padding_ratio=0.1, max_padding_px=16))
    assert dims == (8, 8, 8, 8)
    assert padded.size == (116, 96)

def test_filename_sanitization_removes_pathlike_special_characters():
    assert sanitize_filename("../../confidential?.png") == "confidential"
    assert sanitize_filename("A Product (1).jpg") == "A_Product_1"

def test_zip_builder_keeps_expected_bytes():
    archive = build_zip_archive([ProcessedImage("input", "output.png", b"example")])
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        assert z.namelist() == ["output.png"]
        assert z.read("output.png") == b"example"
