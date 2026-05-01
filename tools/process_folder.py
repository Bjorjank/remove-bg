from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.background_removal import BackgroundRemovalService, RemovalOptions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch remove background dari satu folder.")
    parser.add_argument("input_dir", type=Path, help="Folder berisi gambar sumber")
    parser.add_argument("output_dir", type=Path, help="Folder hasil PNG transparan")
    parser.add_argument(
        "--model",
        default="isnet-general-use",
        help="Nama model rembg yang ingin dipakai, default: isnet-general-use",
    )
    parser.add_argument(
        "--padding-ratio",
        type=float,
        default=0.08,
        help="Padding konteks sebelum inferensi, default: 0.08",
    )
    parser.add_argument(
        "--max-padding-px",
        type=int,
        default=256,
        help="Batas padding konteks dalam pixel, default: 256",
    )
    parser.add_argument(
        "--max-inference-side",
        type=int,
        default=2048,
        help="Batas sisi terpanjang gambar saat diproses model, default: 2048",
    )
    parser.add_argument(
        "--no-alpha-matting",
        action="store_true",
        help="Matikan alpha matting jika ingin proses lebih cepat.",
    )
    parser.add_argument(
        "--no-post-process-mask",
        action="store_true",
        help="Matikan post-process mask jika ingin output mentah dari model.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_dir: Path = args.input_dir
    output_dir: Path = args.output_dir

    if not input_dir.exists() or not input_dir.is_dir():
        raise SystemExit(f"Folder input tidak valid: {input_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    service = BackgroundRemovalService(
        model_name=args.model,
        options=RemovalOptions(
            alpha_matting=not args.no_alpha_matting,
            post_process_mask=not args.no_post_process_mask,
            max_inference_side=args.max_inference_side,
            padding_ratio=args.padding_ratio,
            max_padding_px=args.max_padding_px,
        ),
    )
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
