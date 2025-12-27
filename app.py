from __future__ import annotations

import uuid
from pathlib import Path
from typing import Tuple

import cv2
import numpy as np
from flask import Flask, jsonify, render_template, request
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
OUTPUT_DIR = BASE_DIR / "static" / "outputs"

ALLOWED_EXT = {"png", "jpg", "jpeg", "bmp", "webp"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024  # 12 MB


def allowed_file(filename: str) -> bool:
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXT


def read_image_bgr(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Gagal membaca gambar (format tidak didukung atau file rusak).")
    return img


def clamp_int(v: str, vmin: int, vmax: int, default: int) -> int:
    try:
        x = int(v)
    except Exception:
        return default
    return max(vmin, min(vmax, x))


def clamp_float(v: str, vmin: float, vmax: float, default: float) -> float:
    try:
        x = float(v)
    except Exception:
        return default
    return max(vmin, min(vmax, x))


def downsample(img_bgr: np.ndarray, factor: int, antialias: bool) -> np.ndarray:
    h, w = img_bgr.shape[:2]
    new_w = max(1, w // factor)
    new_h = max(1, h // factor)
    if antialias:
        # INTER_AREA acts like low-pass for downscaling
        return cv2.resize(img_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)
    # aliasing: take every Nth pixel
    return img_bgr[::factor, ::factor].copy()


def upsample(img_bgr: np.ndarray, scale: int, method: str) -> np.ndarray:
    h, w = img_bgr.shape[:2]
    new_w = max(1, w * scale)
    new_h = max(1, h * scale)

    interp = cv2.INTER_NEAREST
    if method == "bilinear":
        interp = cv2.INTER_LINEAR
    elif method == "bicubic":
        interp = cv2.INTER_CUBIC
    return cv2.resize(img_bgr, (new_w, new_h), interpolation=interp)


def unsharp_mask(img_bgr: np.ndarray, amount: float, radius: int) -> np.ndarray:
    # amount: 0..3, radius: 1..15
    blur = cv2.GaussianBlur(img_bgr, (0, 0), sigmaX=radius, sigmaY=radius)
    sharpened = cv2.addWeighted(img_bgr, 1.0 + amount, blur, -amount, 0)
    return np.clip(sharpened, 0, 255).astype(np.uint8)


def adjust_contrast(img_bgr: np.ndarray, alpha: float, beta: int) -> np.ndarray:
    # alpha: contrast multiplier, beta: brightness shift
    return cv2.convertScaleAbs(img_bgr, alpha=alpha, beta=beta)


def process_image(img_bgr: np.ndarray, op: str, params: dict) -> Tuple[np.ndarray, dict]:
    """Return (processed_bgr, meta)."""
    meta = {"operation": op}

    if op == "downsampling":
        factor = clamp_int(params.get("factor", "2"), 2, 32, 8)
        antialias = params.get("antialias", "1") == "1"
        meta.update({"factor": factor, "antialias": antialias})
        out = downsample(img_bgr, factor=factor, antialias=antialias)

    elif op == "upsampling":
        scale = clamp_int(params.get("scale", "2"), 2, 8, 2)
        method = params.get("method", "nearest")
        if method not in {"nearest", "bilinear", "bicubic"}:
            method = "nearest"
        meta.update({"scale": scale, "method": method})
        out = upsample(img_bgr, scale=scale, method=method)

    elif op == "aliasing":
        # Demonstrate aliasing: downsample without antialias then upsample
        factor = clamp_int(params.get("factor", "8"), 2, 32, 8)
        method = params.get("method", "nearest")
        if method not in {"nearest", "bilinear", "bicubic"}:
            method = "nearest"
        meta.update({"factor": factor, "method": method})
        small = downsample(img_bgr, factor=factor, antialias=False)
        # bring back to original size to make aliasing visible
        out = cv2.resize(
            small,
            (img_bgr.shape[1], img_bgr.shape[0]),
            interpolation={
                "nearest": cv2.INTER_NEAREST,
                "bilinear": cv2.INTER_LINEAR,
                "bicubic": cv2.INTER_CUBIC,
            }[method],
        )

    elif op == "sharpen":
        amount = clamp_float(params.get("amount", "1.0"), 0.0, 3.0, 1.0)
        radius = clamp_int(params.get("radius", "3"), 1, 15, 3)
        meta.update({"amount": amount, "radius": radius})
        out = unsharp_mask(img_bgr, amount=amount, radius=radius)

    elif op == "contrast":
        alpha = clamp_float(params.get("alpha", "1.3"), 0.5, 3.0, 1.3)
        beta = clamp_int(params.get("beta", "0"), -100, 100, 0)
        meta.update({"alpha": alpha, "beta": beta})
        out = adjust_contrast(img_bgr, alpha=alpha, beta=beta)

    else:
        raise ValueError("Operasi tidak dikenal.")

    return out, meta


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/process")
def api_process():
    if "image" not in request.files:
        return jsonify({"ok": False, "error": "File gambar tidak ditemukan."}), 400

    f = request.files["image"]
    if not f or f.filename == "":
        return jsonify({"ok": False, "error": "Nama file kosong."}), 400

    if not allowed_file(f.filename):
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "Format file tidak didukung. Gunakan PNG/JPG/JPEG/BMP/WEBP.",
                }
            ),
            400,
        )

    op = request.form.get("operation", "").strip()
    params = {
        "factor": request.form.get("factor", ""),
        "antialias": request.form.get("antialias", ""),
        "scale": request.form.get("scale", ""),
        "method": request.form.get("method", ""),
        "amount": request.form.get("amount", ""),
        "radius": request.form.get("radius", ""),
        "alpha": request.form.get("alpha", ""),
        "beta": request.form.get("beta", ""),
    }

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    safe_name = secure_filename(f.filename)
    uid = uuid.uuid4().hex
    in_path = UPLOAD_DIR / f"{uid}_{safe_name}"
    f.save(in_path)

    try:
        img_bgr = read_image_bgr(in_path)
        out_bgr, meta = process_image(img_bgr, op=op, params=params)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

    out_name = f"{uid}_{op}.png"
    out_path = OUTPUT_DIR / out_name
    cv2.imwrite(str(out_path), out_bgr)

    return jsonify(
        {
            "ok": True,
            "meta": meta,
            "input_url": f"/static/uploads/{in_path.name}",
            "output_url": f"/static/outputs/{out_name}",
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
