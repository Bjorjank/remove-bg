from __future__ import annotations

import argparse
from pathlib import Path

from app.services.background_removal import BackgroundRemovalService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch remove background dari satu folder.")
    parser.add_argument("input_dir", type=Path, help="Folder berisi gambar sumber")
    parser.add_argument("output_dir", type=Path, help="Folder hasil PNG transparan")
    parser.add_argument(
        "--model",
        default="u2net",
        help="Nama model rembg yang ingin dipakai, default: u2net",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_dir: Path = args.input_dir
    output_dir: Path = args.output_dir

    if not input_dir.exists() or not input_dir.is_dir():
        raise SystemExit(f"Folder input tidak valid: {input_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    service = BackgroundRemovalService(model_name=args.model)
    image_files = [path for path in sorted(input_dir.iterdir()) if path.is_file()]

    if not image_files:
        raise SystemExit("Folder input kosong.")

    processed_count = 0
    for image_path in image_files:
        try:
            processed = service.process_image(image_path.name, image_path.read_bytes())
        except ValueError:
            print(f"[SKIP] {image_path.name} bukan gambar yang bisa diproses")
            continue

        output_path = output_dir / processed.output_name
        output_path.write_bytes(processed.content)
        processed_count += 1
        print(f"[OK] {image_path.name} -> {output_path.name}")

    if processed_count == 0:
        raise SystemExit("Tidak ada file gambar valid yang berhasil diproses.")


if __name__ == "__main__":
    main()
