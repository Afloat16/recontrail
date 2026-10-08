"""Inspectable workflow with content-addressed completion reuse and atomic status."""
from pathlib import Path
import importlib.metadata
import platform
import time
import cv2
from . import __version__
from .models import Config, ReconError
from .storage import atomic_json, read_json, digest, fingerprint, workspace
from .images import discover, prepare
from .matching import match_all
from .sfm import reconstruct
from .exports import export_scene
from .report import render_report


def environment():
    result = {"recontrail": __version__, "python": platform.python_version(), "platform": platform.system()}
    for package in ["numpy", "scipy", "Pillow", "pycolmap", "filelock"]:
        try:
            result[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            result[package] = None
    result["opencv"] = cv2.__version__
    return result


def status_writer(root, callback):
    def notify(stage, progress, message):
        atomic_json(root / "status.json", {"state": "running", "stage": stage,
                                          "stage_progress": float(progress), "message": message})
        callback(stage, progress, message)
    return notify


def cache_valid(root):
    marker = root / "complete.json"
    if not marker.exists():
        return False
    try:
        manifest = read_json(marker)
        if not isinstance(manifest, dict) or not manifest or not {"report.html", "metrics.json"} <= manifest.keys():
            return False
        for name, sha in manifest.items():
            path = (root / name).resolve()
            if not path.is_relative_to(root.resolve()) or not path.is_file() or digest(path) != sha:
                return False
        return True
    except (OSError, ValueError, TypeError):
        return False


def complete(root):
    excluded = {".recontrail.lock", "project.json", "status.json", "complete.json"}
    files = [p for p in root.rglob("*") if p.is_file() and p.name not in excluded and "backend" not in p.parts]
    atomic_json(root / "complete.json", {str(p.relative_to(root)): digest(p) for p in files})


def run_photos(source, output, config=Config(), calibration=None, check_only=False,
               resume=False, progress=lambda *args: None):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output == source or output.is_relative_to(source) or source.is_relative_to(output):
        raise ReconError("Input and output directories must be separate, not nested.")
    paths = discover(source, config.max_images)
    env = environment()
    signature = fingerprint(paths, {**config.to_dict(), "check_only": check_only, "environment": env}, calibration)
    with workspace(output, signature, resume) as root:
        if resume and cache_valid(root):
            metrics = read_json(root / "metrics.json")
            atomic_json(root / "status.json", {"state": "complete", "stage": "cached", "message": "Verified cached output"})
            return {**metrics, "cached": True}
        (root / "complete.json").unlink(missing_ok=True)
        notify = status_writer(root, progress)
        start = time.monotonic()
        audit = {"images": [], "rejected": [], "notes": []}
        try:
            frames, rejected = prepare(paths, config, notify, calibration)
            audit.update(images=[f.audit for f in frames], rejected=rejected)
            pairs, graph = match_all(frames, config, notify)
            audit.update(graph)
            if any(f.audit["intrinsics"].startswith("estimated") for f in frames):
                audit["notes"].append("Focal lengths are estimates. Supply calibrated intrinsics for reliable geometry; "
                                      "the lite backend does not self-calibrate.")
            audit["notes"].append("Photo reconstruction has arbitrary scale; reprojection error is not metric accuracy.")
            atomic_json(root / "audit.json", audit)
            scene = None
            if check_only:
                metrics = {"backend": "check-only", "input_images": len(frames), "points": 0,
                           "registered_images": 0, "status": "inspected"}
            else:
                if config.backend == "lite":
                    scene = reconstruct(frames, pairs, config, notify)
                else:
                    from .colmap_backend import reconstruct_colmap
                    scene = reconstruct_colmap(frames, config, root, notify)
                scene.metrics["status"] = "complete" if len(scene.poses) == len(frames) else "partial"
                scene.metrics["elapsed_seconds"] = round(time.monotonic()-start, 3)
                metrics = scene.metrics
                export_scene(root, scene, frames)
            metrics.setdefault("elapsed_seconds", round(time.monotonic()-start, 3))
            atomic_json(root / "metrics.json", metrics)
            atomic_json(root / "provenance.json", {"environment": env, "config": config.to_dict(),
                                                   "signature": signature, "calibration": calibration,
                                                   "coordinate_convention": "X_camera = R @ X_world + t",
                                                   "image_metadata_exported": False})
            render_report(root / "report.html", audit, scene)
            complete(root)
            atomic_json(root / "status.json", {"state": "complete", "stage": "done", "message": metrics["status"]})
            return metrics
        except Exception as exc:
            message = str(exc)[:1000]
            atomic_json(root / "audit.json", audit)
            render_report(root / "report.html", audit, error=message)
            atomic_json(root / "status.json", {"state": "failed", "stage": "error", "message": message})
            raise


def run_stereo(left, right, calibration, output, max_depth=100., stride=2, resume=False,
               progress=lambda *args: None):
    from .stereo import reconstruct_stereo
    left, right, output = Path(left).resolve(), Path(right).resolve(), Path(output).resolve()
    if output in [left, right] or left.is_relative_to(output) or right.is_relative_to(output):
        raise ReconError("Stereo output must not contain either source image.")
    settings = {"mode": "stereo", "max_depth": max_depth, "stride": stride, "environment": environment()}
    signature = fingerprint([left, right], settings, calibration)
    with workspace(output, signature, resume) as root:
        if resume and cache_valid(root):
            atomic_json(root / "status.json", {"state": "complete", "stage": "cached", "message": "Verified cached output"})
            return {**read_json(root / "metrics.json"), "cached": True}
        (root / "complete.json").unlink(missing_ok=True)
        notify = status_writer(root, progress)
        audit = {"images": [], "rejected": [], "notes": [
            "Use synchronized, calibrated stereo images of a static scene.",
            "Scale comes from your supplied baseline; this is not a calibration accuracy certificate.",
            "Surface triangulation does not fill holes and does not create a texture atlas."]}
        start = time.monotonic()
        try:
            scene = reconstruct_stereo(left, right, calibration, max_depth, stride, notify)
            scene.metrics.update(status="complete", elapsed_seconds=round(time.monotonic()-start, 3))
            export_scene(root, scene)
            atomic_json(root / "audit.json", audit)
            atomic_json(root / "provenance.json", {**settings, "signature": signature, "calibration": calibration})
            render_report(root / "report.html", audit, scene)
            complete(root)
            atomic_json(root / "status.json", {"state": "complete", "stage": "done", "message": "complete"})
            return scene.metrics
        except Exception as exc:
            render_report(root / "report.html", audit, error=str(exc)[:1000])
            atomic_json(root / "status.json", {"state": "failed", "stage": "error", "message": str(exc)[:1000]})
            raise
