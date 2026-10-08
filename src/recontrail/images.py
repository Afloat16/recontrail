"""Image preparation, conservative quality checks and feature extraction.

SIFT and image operations are provided by OpenCV; see docs/references.bib.
Quality thresholds are heuristics, not reconstruction probabilities.
"""
from pathlib import Path
import hashlib
import warnings
import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from .models import Config, Frame, ReconError

EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}
PIXEL_LIMIT = 40_000_000
BYTE_LIMIT = 64 * 1024 * 1024


def discover(source: Path, maximum=160):
    source = source.resolve()
    if not source.is_dir():
        raise ReconError("Image input must be an existing directory.")
    paths = sorted((p for p in source.iterdir() if p.is_file() and not p.is_symlink()
                    and p.suffix.lower() in EXTENSIONS), key=lambda p: (p.name.casefold(), p.name))
    if len(paths) > maximum:
        raise ReconError(f"Found {len(paths)} images; limit is {maximum}. Select a smaller set or raise --max-images.")
    if len(paths) < 2:
        raise ReconError("Provide at least two overlapping JPEG, PNG, WebP, TIFF or BMP images.")
    return paths


def read_rgb(path: Path):
    if path.stat().st_size > BYTE_LIMIT:
        raise ReconError("Image exceeds the 64 MiB per-file limit.")
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(path) as raw:
            if raw.width * raw.height > PIXEL_LIMIT:
                raise ReconError("Image exceeds the 40-megapixel decode limit.")
            exif = raw.getexif()
            try:
                photo_exif = exif.get_ifd(34665)
            except (ValueError, KeyError, TypeError):
                photo_exif = {}
            f35 = photo_exif.get(41989, exif.get(41989))
            oriented = ImageOps.exif_transpose(raw).convert("RGB")
            return np.asarray(oriented).copy(), f35


def camera_matrix(width, height, focal_ratio=1.2, f35=None, calibration=None):
    if calibration is not None:
        required = {"width", "height", "fx", "fy", "cx", "cy"}
        if not isinstance(calibration, dict) or not required <= calibration.keys():
            raise ReconError("Intrinsics must contain width, height, fx, fy, cx and cy.")
        if (calibration["width"], calibration["height"]) != (width, height):
            raise ReconError("Calibration dimensions must match the EXIF-oriented input pixels.")
        values = np.array([calibration[k] for k in ["fx", "fy", "cx", "cy"]], dtype=float)
        if not np.isfinite(values).all() or np.any(values[:2] <= 0):
            raise ReconError("Camera focal lengths must be positive and all intrinsics finite.")
        fx, fy, cx, cy = values
        if not 0 <= cx < width or not 0 <= cy < height:
            raise ReconError("Principal point must be inside the input image.")
        return np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1.]], float), "calibrated"
    focal = focal_ratio * max(width, height)
    method = "estimated: focal_ratio"
    try:
        if f35 is not None and 4 <= float(f35) <= 1200:
            focal = float(f35) / 36 * max(width, height)
            method = "estimated: 35mm EXIF"
    except (TypeError, ValueError, ZeroDivisionError):
        pass
    return np.array([[focal, 0, width/2], [0, focal, height/2], [0, 0, 1.]]), method


def prepare(paths, config: Config, progress=lambda *args: None, calibration=None):
    cv2.setNumThreads(2)
    cv2.setRNGSeed(config.seed)
    sift = cv2.SIFT_create(nfeatures=config.max_features, contrastThreshold=.02)
    frames, rejected, seen = [], [], {}
    for ordinal, path in enumerate(paths):
        progress("prepare", ordinal / len(paths), f"Inspecting {path.name}")
        try:
            rgb, f35 = read_rgb(path)
        except (OSError, ValueError, ReconError, UnidentifiedImageError,
                Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
            rejected.append({"name": path.name, "reason": str(exc)[:220]})
            continue
        h, w = rgb.shape[:2]
        sha = hashlib.sha256(rgb.tobytes() + f"{w}x{h}".encode()).hexdigest()
        if sha in seen:
            rejected.append({"name": path.name, "reason": f"Exact decoded-pixel duplicate of {seen[sha]}"})
            continue
        seen[sha] = path.name
        K, method = camera_matrix(w, h, config.focal_ratio, f35, calibration)
        if calibration and "distortion" in calibration:
            d = np.asarray(calibration["distortion"], dtype=float)
            if d.ndim != 1 or len(d) not in (4, 5, 8, 12, 14) or not np.isfinite(d).all():
                raise ReconError("Distortion must contain 4, 5, 8, 12 or 14 finite OpenCV coefficients.")
            rgb = cv2.undistort(rgb, K, d)
        scale = min(1., config.max_size / max(w, h))
        nw, nh = round(w * scale), round(h * scale)
        rgb = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_AREA)
        K[0] *= nw / w
        K[1] *= nh / h
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        thumbnail = cv2.resize(gray, (max(1, round(nw*min(1, 640/nw))),
                                       max(1, round(nh*min(1, 640/nw)))))
        sharpness = float(cv2.Laplacian(thumbnail, cv2.CV_64F).var())
        low = float(np.mean(gray < 10))
        high = float(np.mean(gray > 245))
        keys, descriptors = sift.detectAndCompute(gray, None)
        points = np.array([k.pt for k in keys], dtype=np.float64).reshape(-1, 2)
        if descriptors is None:
            descriptors = np.empty((0, 128), np.float32)
        pixels = np.clip(np.rint(points).astype(int), [0, 0], [nw-1, nh-1])
        colors = rgb[pixels[:, 1], pixels[:, 0]]
        cells = set((min(3, int(x*4/nw)), min(3, int(y*4/nh))) for x, y in points)
        flags = []
        if sharpness < 45:
            flags.append("soft_image")
        if low > .5:
            flags.append("mostly_dark")
        if high > .5:
            flags.append("mostly_bright")
        if len(points) < 150 or len(cells) < 6:
            flags.append("limited_texture")
        audit = {"name": path.name, "width": w, "height": h, "working_width": nw,
                 "working_height": nh, "sharpness": round(sharpness, 2),
                 "dark_fraction": round(low, 4), "bright_fraction": round(high, 4),
                 "features": len(points), "occupied_cells": len(cells),
                 "flags": flags, "intrinsics": method, "pixel_sha256": sha}
        frames.append(Frame(path.name, rgb, K, points, descriptors, colors, audit))
    if len(frames) < 2:
        raise ReconError("Fewer than two distinct readable images remain. Check corrupt or duplicate inputs.")
    return frames, rejected
