"""Synthetic test-only replacement for rembg inference.

Used to verify the API and image pipeline without downloading model weights.
NEVER treat its output as proof of background-removal quality.
"""
from __future__ import annotations
from io import BytesIO
from PIL import Image

def new_session(model_name: str):
    return {"mock_model": model_name, "inference": "stubbed"}

def remove(content, *, session=None, **kwargs):
    with Image.open(BytesIO(content)) as source:
        rgba = source.convert("RGBA")
        output = BytesIO()
        rgba.save(output, format="PNG")
        return output.getvalue()
