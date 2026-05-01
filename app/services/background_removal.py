from __future__ import annotations

import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Iterable
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image, ImageOps, UnidentifiedImageError
from rembg import new_session, remove

# Hint format untuk UI. Validasi utama tetap dilakukan dari isi file.
SUPPORTED_INPUT_HINT = (
    ".avif, .bmp, .dib, .gif, .jfif, .jpeg, .jpg, .jpe, .jp2, .png, "
    ".tif, .tiff, .webp"
)


@dataclass(frozen=True)
class ProcessedImage:
    original_name: str
    output_name: str
    content: bytes


@dataclass(frozen=True)
class RemovalOptions:
    alpha_matting: bool = True
    alpha_matting_foreground_threshold: int = 240
    alpha_matting_background_threshold: int = 10
    alpha_matting_erode_size: int = 10
    post_process_mask: bool = True
    padding_ratio: float = 0.08
    max_padding_px: int = 256


class BackgroundRemovalService:
    def __init__(self, model_name: str = "u2net", options: RemovalOptions | None = None) -> None:
        self.model_name = model_name
        self.options = options or RemovalOptions()
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

        try:
            normalized_content, padding = normalize_image_bytes(content, self.options)
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError(f"File bukan gambar valid: {filename}") from exc

        output = remove(
            normalized_content,
            session=self.session,
            alpha_matting=self.options.alpha_matting,
            alpha_matting_foreground_threshold=self.options.alpha_matting_foreground_threshold,
            alpha_matting_background_threshold=self.options.alpha_matting_background_threshold,
            alpha_matting_erode_size=self.options.alpha_matting_erode_size,
            post_process_mask=self.options.post_process_mask,
            force_return_bytes=True,
        )
        if any(padding):
            output = remove_padding(output, padding)

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


def normalize_image_bytes(content: bytes, options: RemovalOptions) -> tuple[bytes, tuple[int, int, int, int]]:
    with Image.open(BytesIO(content)) as image:
        if getattr(image, "is_animated", False):
            image.seek(0)

        oriented = ImageOps.exif_transpose(image)
        converted = oriented.convert("RGB")
        padded, padding = add_context_padding(converted, options)
        output = BytesIO()
        padded.save(output, format="PNG")
        return output.getvalue(), padding


def add_context_padding(image: Image.Image, options: RemovalOptions) -> tuple[Image.Image, tuple[int, int, int, int]]:
    if options.padding_ratio <= 0 or options.max_padding_px <= 0:
        return image, (0, 0, 0, 0)

    width, height = image.size
    padding = min(
        options.max_padding_px,
        max(1, round(min(width, height) * options.padding_ratio)),
    )
    fill = estimate_border_color(image)
    padded = ImageOps.expand(image, border=padding, fill=fill)
    return padded, (padding, padding, padding, padding)


def estimate_border_color(image: Image.Image) -> tuple[int, int, int]:
    width, height = image.size
    points = [
        (0, 0),
        (width - 1, 0),
        (0, height - 1),
        (width - 1, height - 1),
    ]
    channels = list(zip(*(image.getpixel(point)[:3] for point in points)))
    return tuple(sorted(channel)[len(channel) // 2] for channel in channels)


def remove_padding(content: bytes, padding: tuple[int, int, int, int]) -> bytes:
    left, top, right, bottom = padding
    with Image.open(BytesIO(content)) as image:
        width, height = image.size
        cropped = image.crop((left, top, width - right, height - bottom))
        output = BytesIO()
        cropped.save(output, format="PNG")
        return output.getvalue()


def build_zip_archive(images: Iterable[ProcessedImage]) -> bytes:
    memory_file = BytesIO()
    with ZipFile(memory_file, mode="w", compression=ZIP_DEFLATED) as archive:
        for image in images:
            archive.writestr(image.output_name, image.content)
    memory_file.seek(0)
    return memory_file.read()
