"""Capture the original app UI through an actual local FastAPI server + Chromium.

Important: tests/support_stubs/rembg is a synthetic model test double.
This script does NOT validate the quality of background removal.
"""
import io
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence"
BASE = "http://127.0.0.1:8874"

def wait_ready(seconds=25):
    for _ in range(seconds*10):
        try:
            with urllib.request.urlopen(BASE + "/health", timeout=2) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(.1)
    raise RuntimeError("Original local app did not pass healthcheck")

def make_synthetic_photo():
    image = Image.new("RGB", (600, 400), "#faf7f2")
    draw = ImageDraw.Draw(image)
    draw.ellipse([175, 40, 425, 290], fill="#1d75b9", outline="#174569", width=7)
    draw.rectangle([280, 220, 345, 370], fill="#ef8157")
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()

def main():
    EVIDENCE.mkdir(exist_ok=True)
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT / "tests" / "support_stubs"), str(ROOT), env.get("PYTHONPATH","")]
    )
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", "8874", "--no-access-log"],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE, text=True
    )
    evidence = {
        "source_repository": "https://github.com/Bjorjank/remove-bg",
        "source_commit": os.getenv("GITHUB_SHA","local-working-tree"),
        "capture_type": "original_app_UI_in_real_Chromium",
        "server": "local FastAPI, source app/main.py",
        "static_assets": "original app/static/index.html, styles.css, app.js",
        "test_fixture": "generated nonpersonal synthetic PNG",
        "rembg_inference": "STUBBED",
        "model_quality_tested": False,
        "business_performance_claim": False
    }
    try:
        wait_ready()
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            desktop = browser.new_page(viewport={"width":1440,"height":960},device_scale_factor=1)
            failures=[]
            desktop.on("pageerror", lambda err: failures.append(str(err)))
            response = desktop.goto(BASE+"/",wait_until="networkidle",timeout=30000)
            assert response.status == 200
            assert desktop.get_by_text("Batch Background Removal",exact=True).count()>=1
            assert desktop.locator("#fileInput").count()==1
            assert desktop.locator("#processButton").count()==1
            assert desktop.locator("#modelName").inner_text(timeout=8000)=="isnet-general-use"
            synthetic = make_synthetic_photo()
            desktop.locator("#fileInput").set_input_files([
                {"name":"example-object-a.png","mimeType":"image/png","buffer":synthetic},
                {"name":"example-object-b.png","mimeType":"image/png","buffer":synthetic},
            ])
            assert desktop.locator("#fileCount").inner_text()=="2"
            assert desktop.locator("#processButton").is_enabled()
            desktop.screenshot(path=str(EVIDENCE/"original-ui-desktop.png"),full_page=True,animations="disabled")
            mobile=browser.new_page(viewport={"width":390,"height":844},device_scale_factor=1)
            mobile.goto(BASE+"/",wait_until="networkidle",timeout=30000)
            assert mobile.locator("#fileInput").count()==1
            assert mobile.locator("#processButton").count()==1
            assert mobile.evaluate("document.documentElement.scrollWidth <= window.innerWidth+2")
            mobile.screenshot(path=str(EVIDENCE/"original-ui-mobile.png"),full_page=True,animations="disabled")
            evidence["browser_checks"]=[
                "Original dashboard HTTP 200",
                "Original stylesheet and JavaScript loaded",
                "Original model identifier shown in dashboard",
                "Two synthetic images selected through original browser interface",
                "Browser count updated to two files",
                "Batch submission button enabled",
                "Mobile 390px viewport: no horizontal overflow",
                "No browser page errors"
            ]
            evidence["page_errors"]=failures
            assert not failures,failures
            evidence["desktop_screenshot"]="original-ui-desktop.png"
            evidence["mobile_screenshot"]="original-ui-mobile.png"
            evidence["status"]="PASS"
            browser.close()
    finally:
        server.terminate()
        try:
            server.communicate(timeout=6)
        except subprocess.TimeoutExpired:
            server.kill()
            server.communicate()
    (EVIDENCE/"browser-verification.json").write_text(
        json.dumps(evidence,indent=2,ensure_ascii=False)+"\n",encoding="utf8"
    )
    print("ORIGINAL_UI_BROWSER_VERIFICATION=PASS; MODEL_INFERENCE=STUBBED")

if __name__=="__main__":
    main()
