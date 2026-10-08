"""Self-contained report with safe embedded JSON and no external requests."""
from pathlib import Path
import json
import numpy as np
from .exports import cameras_json

ASSETS = Path(__file__).parent / "web"


def safe_json(data):
    return (json.dumps(data, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


def render_report(path, audit, scene=None, error=None):
    payload = {"audit": audit, "error": error, "metrics": {}, "points": [], "colors": [], "cameras": []}
    if scene is not None:
        # Deterministic bounded preview only. Exports retain the complete cloud.
        ids = np.linspace(0, len(scene.points)-1, min(len(scene.points), 14000), dtype=int)
        payload.update(metrics=scene.metrics, points=np.round(scene.points[ids], 6).tolist(),
                       colors=scene.colors[ids].tolist(), cameras=cameras_json(scene)["cameras"])
    template = (ASSETS / "report.html").read_text(encoding="utf-8")
    template = template.replace("__CSS__", (ASSETS / "style.css").read_text(encoding="utf-8"))
    template = template.replace("__JS__", (ASSETS / "viewer.js").read_text(encoding="utf-8"))
    template = template.replace("__DATA__", safe_json(payload))
    path.write_text(template, encoding="utf-8")
