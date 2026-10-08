"""Bounded video sampling. Sharpest-per-window is a heuristic, not a geometry guarantee."""
from pathlib import Path
import hashlib
import math
import cv2
from PIL import Image
from .models import ReconError
from .storage import atomic_json, workspace, fingerprint


def extract_video(source, output, interval=.75, max_frames=160):
    source, output = Path(source).resolve(), Path(output).resolve()
    if not source.is_file() or source.is_symlink() or source.is_relative_to(output):
        raise ReconError("Use a local video file outside the output directory.")
    if not isinstance(interval, (int, float)) or not math.isfinite(interval) or not .1 <= interval <= 60:
        raise ReconError("interval must be between 0.1 and 60 seconds.")
    if isinstance(max_frames, bool) or not isinstance(max_frames, int) or not 2 <= max_frames <= 1000:
        raise ReconError("max_frames must be an integer between 2 and 1000.")
    signature = fingerprint([source], {"video_interval": interval, "max_frames": max_frames})
    with workspace(output, signature, False) as root:
        cap = cv2.VideoCapture(str(source))
        if not cap.isOpened():
            cap.release()
            raise ReconError("Cannot decode this video with the installed OpenCV codecs.")
        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            if not math.isfinite(fps) or not 1 <= fps <= 240:
                raise ReconError("Invalid video frame rate. Transcode to a constant-frame-rate MP4 first.")
            width, height = cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            if width*height > 40_000_000 or width <= 0 or height <= 0:
                raise ReconError("Invalid or oversized video dimensions.")
            window = max(1, round(fps*interval))
            target = root/"images"
            target.mkdir()
            records, seen = [], set()
            best = None
            def save_best(item):
                if item is None:
                    return
                score, index, rgb = item
                sha = hashlib.sha256(rgb.tobytes()).hexdigest()
                if sha in seen:
                    return
                name = f"frame_{index:08d}.png"
                Image.fromarray(rgb).save(target/name)
                records.append({"name": name, "frame": index, "approx_seconds": round(index/fps, 5),
                                "sharpness": score, "pixel_sha256": sha})
                seen.add(sha)
            for index in range(36000):
                ok, frame = cap.read()
                if not ok:
                    save_best(best)
                    break
                h, w = frame.shape[:2]
                if h*w > 40_000_000:
                    raise ReconError("Decoded frame exceeds the pixel limit.")
                scale = min(1., 1600/max(w, h))
                frame = cv2.resize(frame, (round(w*scale), round(h*scale)), interpolation=cv2.INTER_AREA)
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray = cv2.resize(gray, (320, max(1, round(320*h/w))))
                score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
                if best is None or score > best[0]:
                    best = (score, index, cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                if (index+1) % window == 0:
                    save_best(best)
                    best = None
                    if len(records) >= max_frames:
                        break
            else:
                save_best(best)
            manifest = {"frames": records, "fps": fps, "interval": interval,
                        "decoded_frame_limit": 36000, "note": "Timestamps use frame index / reported FPS; variable-frame-rate accuracy is not guaranteed."}
            atomic_json(root/"video.json", manifest)
            if len(records) < 2:
                raise ReconError("Fewer than two distinct frames extracted. Use a moving camera and a longer capture.")
            return {"frames": len(records), "images": str(target), "manifest": str(root/"video.json")}
        finally:
            cap.release()
