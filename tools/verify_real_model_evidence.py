"""Real rembg/ONNX inference on entirely synthetic noncustomer sample imagery.

This path calls BackgroundRemovalService.process_image with a REAL u2netp
inference session (not the integration-test model stub). It records observable
PNG alpha channel results, not human-reviewed segmentation accuracy.
"""
from __future__ import annotations
import hashlib
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.services.background_removal import BackgroundRemovalService, RemovalOptions

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence"
SIZE = (512, 512)

def synthetic_product():
    # Illustrative synthetic source image only; no company/customer photographs.
    canvas = Image.new("RGB", SIZE, "#f2e7dc")
    draw = ImageDraw.Draw(canvas)
    for y in range(SIZE[1]):
        t = y / SIZE[1]
        color = (int(243 - t*25), int(235 - t*33), int(224 - t*36))
        draw.line([(0,y),(SIZE[0],y)],fill=color)
    # Soft contact shadow, bottle/packaging silhouette and edge highlights.
    shade = Image.new("RGBA", SIZE, (0,0,0,0))
    sd = ImageDraw.Draw(shade)
    sd.ellipse((109,380,406,446), fill=(39,36,33,68))
    shade = shade.filter(ImageFilter.GaussianBlur(17))
    canvas = Image.alpha_composite(canvas.convert("RGBA"),shade)
    product = Image.new("RGBA", SIZE,(0,0,0,0))
    d = ImageDraw.Draw(product)
    d.rounded_rectangle((205,81,307,142),radius=15,fill="#283648")
    d.rounded_rectangle((181,128,332,407),radius=30,fill="#2e6881",outline="#19455e",width=4)
    d.rounded_rectangle((188,140,200,391),radius=5,fill="#74bed0")
    d.rounded_rectangle((216,145,296,166),radius=9,fill="#6db8ca")
    d.rounded_rectangle((203,225,310,332),radius=14,fill="#f6ebdf")
    d.line([(225,265),(289,265)],fill="#bd7a61",width=5)
    d.ellipse((244,279,269,305),fill="#d6a17c")
    d.polygon([(310,167),(319,187),(319,376),(308,393)],fill="#24566d")
    canvas=Image.alpha_composite(canvas,product).convert("RGB")
    buf=io.BytesIO()
    canvas.save(buf,"PNG")
    return buf.getvalue()

def sha256(data):
    return hashlib.sha256(data).hexdigest()

def checkerboard(size, tile=24):
    board=Image.new("RGB",size,"white")
    d=ImageDraw.Draw(board)
    for y in range(0,size[1],tile):
        for x in range(0,size[0],tile):
            d.rectangle((x,y,x+tile,y+tile),fill="#e4e8ed" if ((x//tile+y//tile)%2) else "#fafcff")
    return board

def compose(before,after):
    p=30
    panel=Image.new("RGB",(SIZE[0]*2+3*p,SIZE[1]+94),"#f9fafb")
    panel.paste(before,(p,68))
    board=checkerboard(SIZE).convert("RGBA")
    board.alpha_composite(after)
    panel.paste(board.convert("RGB"),(SIZE[0]+2*p,68))
    title=ImageDraw.Draw(panel)
    title.text((p,20),"BEFORE  /  Synthetic source image",fill="#213546")
    title.text((SIZE[0]+2*p,20),"AFTER  /  Real rembg u2netp inference",fill="#213546")
    return panel

def main():
    OUT.mkdir(exist_ok=True)
    inp=synthetic_product()
    options=RemovalOptions(
        alpha_matting=False,
        post_process_mask=True,
        max_inference_side=512,
        padding_ratio=0.08,
        max_padding_px=64,
    )
    service=BackgroundRemovalService(model_name="u2netp",options=options)
    processed=service.process_image("synthetic-packaging.png",inp)
    with Image.open(io.BytesIO(processed.content)) as image:
        rgba=image.convert("RGBA")
        rgba.load()
        if rgba.size!=SIZE: raise AssertionError(f"Wrong output size {rgba.size}")
        alpha=rgba.getchannel("A")
        histogram=alpha.histogram()
    total=SIZE[0]*SIZE[1]
    transparent=sum(histogram[:16])/total
    opaque=sum(histogram[240:])/total
    # Shape-specific accuracy is NOT asserted; only real nonuniform alpha evidence.
    if not (alpha.getextrema()[0]<255 and alpha.getextrema()[1]>0):
        raise AssertionError("AI segmentation alpha output is degenerate; do not publish")
    before=Image.open(io.BytesIO(inp)).convert("RGB")
    (OUT/"real-inference-before.png").write_bytes(inp)
    (OUT/"real-inference-after.png").write_bytes(processed.content)
    comparison=compose(before,rgba)
    comparison.save(OUT/"real-inference-comparison.png","PNG",optimize=True)
    report={
      "status":"PASS",
      "stage":"REAL_MODEL_INFERENCE",
      "execution_utc":datetime.now(timezone.utc).isoformat(timespec="seconds"),
      "source_sha":os.environ.get("GITHUB_SHA","local"),
      "model":"u2netp",
      "model_session_type":"REAL rembg session; ONNX Runtime",
      "implementation":"app/services/background_removal.py::BackgroundRemovalService.process_image",
      "input":"synthetic PNG drawn with Pillow; not a customer photo",
      "model_is_default":False,
      "default_model_used":False,
      "options":{"alpha_matting":False,"post_process_mask":True,"max_inference_side":512,"padding_ratio":0.08},
      "input_size_px":list(SIZE),
      "output_size_px":list(SIZE),
      "output_png_mode":"RGBA",
      "alpha_min_max":list(alpha.getextrema()),
      "alpha_transparent_pixel_ratio_le15":round(transparent,6),
      "alpha_opaque_pixel_ratio_ge240":round(opaque,6),
      "input_sha256":sha256(inp),
      "result_png_sha256":sha256(processed.content),
      "verification":"Real model invocation and valid alpha-bearing PNG; no human-verified segmentation accuracy or benchmarking"
    }
    (OUT/"real-inference-summary.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf8")
    print("REAL_MODEL_INFERENCE=PASS MODEL=u2netp OUTPUT_RGBA=PASS INPUT_SYNTHETIC=True")
    print("ALPHA_RANGE="+str(report["alpha_min_max"]))
    print("TRANSPARENT_PIXEL_RATIO="+str(report["alpha_transparent_pixel_ratio_le15"]))
    print("OPAQUE_PIXEL_RATIO="+str(report["alpha_opaque_pixel_ratio_ge240"]))

if __name__=="__main__":
    main()
