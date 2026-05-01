from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.services.background_removal import (
    BackgroundRemovalService,
    RemovalOptions,
    SUPPORTED_INPUT_HINT,
    build_zip_archive,
)

MAX_FILES_PER_BATCH = 50
BASE_DIR = Path(__file__).resolve().parent
service = BackgroundRemovalService(
    model_name=os.getenv("REMOVE_BG_MODEL", "isnet-general-use"),
    options=RemovalOptions(
        padding_ratio=float(os.getenv("REMOVE_BG_PADDING_RATIO", "0.08")),
        max_padding_px=int(os.getenv("REMOVE_BG_MAX_PADDING_PX", "256")),
        max_inference_side=int(os.getenv("REMOVE_BG_MAX_INFERENCE_SIDE", "2048")),
        alpha_matting=os.getenv("REMOVE_BG_ALPHA_MATTING", "true").lower() in {"1", "true", "yes", "on"},
        post_process_mask=os.getenv("REMOVE_BG_POST_PROCESS_MASK", "true").lower() in {"1", "true", "yes", "on"},
    ),
)

app = FastAPI(
    title="Remove BG Batch API",
    version="0.1.0",
    description="API sederhana untuk menghapus background banyak gambar sekaligus.",
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {
        "status": "ok",
        "model": service.model_name,
        "alpha_matting": str(service.options.alpha_matting),
        "post_process_mask": str(service.options.post_process_mask),
        "max_inference_side": str(service.options.max_inference_side),
        "padding_ratio": str(service.options.padding_ratio),
        "max_padding_px": str(service.options.max_padding_px),
        "allowed_extensions": SUPPORTED_INPUT_HINT,
        "max_files_per_batch": str(MAX_FILES_PER_BATCH),
    }


@app.post("/remove-batch")
async def remove_batch(files: list[UploadFile] = File(...)) -> StreamingResponse:
    if not files:
        raise HTTPException(status_code=400, detail="Unggah minimal satu file gambar.")

    if len(files) > MAX_FILES_PER_BATCH:
        raise HTTPException(
            status_code=400,
            detail=f"Maksimal {MAX_FILES_PER_BATCH} file per batch.",
        )

    payload: list[tuple[str, bytes]] = []
    for upload in files:
        filename = upload.filename or "image"
        content = await upload.read()
        payload.append((filename, content))

    try:
        processed = await run_in_threadpool(service.process_batch, payload)
        archive_bytes = await run_in_threadpool(build_zip_archive, processed)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=500,
            detail=f"Terjadi kegagalan saat memproses batch: {exc}",
        ) from exc

    response = StreamingResponse(BytesIO(archive_bytes), media_type="application/zip")
    response.headers["Content-Disposition"] = 'attachment; filename="background-removed.zip"'
    return response
