from __future__ import annotations

import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Iterable
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image, UnidentifiedImageError
from rembg import new_session, remove

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass(frozen=True)
class ProcessedImage:
    original_name: str
    output_name: str
    content: bytes


class BackgroundRemovalService:
    def __init__(self, model_name: str = "u2net") -> None:
        self.model_name = model_name
        self._session = None

    @property
    def session(self):
        if self._session is None:
            self._session = new_session(self.model_name)
        return self._session

    def process_batch(self, files: Iterable[tuple[str, bytes]]) -> list[ProcessedImage]:
        return [self.process_image(filename, content) for filename, content in files]

    def process_image(self, filename: str, content: bytes) -> ProcessedImage:
        if not content:
            raise ValueError(f"File kosong tidak bisa diproses: {filename}")

        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
            raise ValueError(f"Format file tidak didukung untuk {filename}. Gunakan: {allowed}")

        try:
            Image.open(BytesIO(content)).verify()
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError(f"File bukan gambar valid: {filename}") from exc

        output = remove(content, session=self.session, force_return_bytes=True)
        safe_name = sanitize_filename(filename)
        return ProcessedImage(
            original_name=filename,
            output_name=f"{safe_name}.png",
            content=output,
        )


def sanitize_filename(filename: str) -> str:
    stem = Path(filename).stem
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._")
    return cleaned or "image"


def build_zip_archive(images: Iterable[ProcessedImage]) -> bytes:
    memory_file = BytesIO()
    with ZipFile(memory_file, mode="w", compression=ZIP_DEFLATED) as archive:
        for image in images:
            archive.writestr(image.output_name, image.content)
    memory_file.seek(0)
    return memory_file.read()

