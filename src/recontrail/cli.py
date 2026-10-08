"""Stable command-line entry points; JSON results on stdout, progress on stderr."""
import argparse
import json
import sys
from pathlib import Path
from . import __version__
from .models import Config, ReconError
from .storage import read_json


def parser():
    p = argparse.ArgumentParser(prog="recontrail", description="Local photo inspection and explainable 3D reconstruction.")
    p.add_argument("--version", action="version", version=f"ReconTrail {__version__}")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Inspect runtime and optional backend availability")
    for command in ("run", "check"):
        c = sub.add_parser(command, help="Reconstruct a photo folder" if command == "run" else "Inspect photo quality and connectivity")
        c.add_argument("images", type=Path)
        c.add_argument("-o", "--output", type=Path, required=True)
        c.add_argument("--intrinsics", type=Path, help="Calibrated shared pinhole intrinsics JSON")
        c.add_argument("--backend", choices=["lite", "colmap"], default="lite")
        c.add_argument("--pairing", choices=["auto", "all", "sequence"], default="auto")
        c.add_argument("--max-size", type=int, default=1400)
        c.add_argument("--max-features", type=int, default=4000)
        c.add_argument("--max-images", type=int, default=160)
        c.add_argument("--pair-window", type=int, default=8)
        c.add_argument("--focal-ratio", type=float, default=1.2)
        c.add_argument("--ba-points", type=int, default=2500)
        c.add_argument("--ba-evaluations", type=int, default=25)
        c.add_argument("--no-ba", action="store_true", help="Skip final bundle adjustment (preview only)")
        c.add_argument("--resume", action="store_true", help="Reuse only checksum-verified completed outputs, or retry a matching project")
        c.add_argument("--quiet", action="store_true")
    c = sub.add_parser("demo", help="Create an original multi-depth synthetic capture; optionally reconstruct it")
    c.add_argument("-o", "--output", type=Path, default=Path("recontrail-demo"))
    c.add_argument("--count", type=int, default=8)
    c.add_argument("--run", action="store_true")
    c = sub.add_parser("stereo", help="Calibrated stereo to dense points and open surface mesh (CPU)")
    c.add_argument("left", type=Path)
    c.add_argument("right", type=Path)
    c.add_argument("--calibration", type=Path, required=True)
    c.add_argument("-o", "--output", type=Path, required=True)
    c.add_argument("--max-depth", type=float, default=100.)
    c.add_argument("--stride", type=int, default=2)
    c.add_argument("--resume", action="store_true")
    c.add_argument("--quiet", action="store_true")
    c = sub.add_parser("video", help="Extract the sharpest frame from each time window")
    c.add_argument("input", type=Path)
    c.add_argument("-o", "--output", type=Path, required=True)
    c.add_argument("--interval", type=float, default=.75)
    c.add_argument("--max-frames", type=int, default=160)
    c = sub.add_parser("serve", help="Open the loopback-only browser workbench")
    c.add_argument("--workspace", type=Path, default=Path.home()/".recontrail"/"projects")
    c.add_argument("--port", type=int, default=8765)
    c.add_argument("--no-browser", action="store_true")
    return p


def load_object(path):
    value = read_json(path)
    if not isinstance(value, dict):
        raise ReconError(f"{path.name} must contain a JSON object.")
    return value


def main(argv=None):
    args = parser().parse_args(argv)
    def progress(stage, fraction, message):
        if not getattr(args, "quiet", False):
            print(f"[{stage} {fraction:3.0%}] {message}", file=sys.stderr, flush=True)
    try:
        if args.command == "serve":
            from .server import serve
            serve(args.workspace, args.port, not args.no_browser)
            return 0
        if args.command == "doctor":
            from .pipeline import environment
            import cv2
            result = {"environment": environment(), "sift": hasattr(cv2, "SIFT_create"),
                      "default_backend": "lite-cpu", "network_required_after_install": False,
                      "limits": "Sparse preview is not a mesh. Stereo requires calibration. Browser binds only to 127.0.0.1."}
            result["colmap_available"] = bool(result["environment"]["pycolmap"])
        elif args.command in ("run", "check"):
            from .pipeline import run_photos
            names = ("backend", "pairing", "max_size", "max_features", "max_images", "pair_window",
                     "focal_ratio", "ba_points", "ba_evaluations")
            config = Config(**{name: getattr(args, name) for name in names}, bundle_adjust=not args.no_ba)
            calibration = load_object(args.intrinsics) if args.intrinsics else None
            result = run_photos(args.images, args.output, config, calibration, args.command == "check", args.resume, progress)
        elif args.command == "stereo":
            from .pipeline import run_stereo
            result = run_stereo(args.left, args.right, load_object(args.calibration), args.output,
                                args.max_depth, args.stride, args.resume, progress)
        elif args.command == "video":
            from .video import extract_video
            result = extract_video(args.input, args.output, args.interval, args.max_frames)
        else:
            from .demo import make_demo
            from .pipeline import run_photos
            images = make_demo(args.output, args.count)
            result = {"images": str(images), "kind": "synthetic test capture, not a real-world benchmark"}
            if args.run:
                result["reconstruction"] = run_photos(images, args.output/"result", Config(),
                                                       load_object(args.output/"intrinsics.json"), progress=progress)
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
        return 0
    except KeyboardInterrupt:
        print("Cancelled. Partial files are not completed results; retry with --resume.", file=sys.stderr)
        return 130
    except (ReconError, OSError, ValueError, TypeError, RuntimeError) as exc:
        print(f"ReconTrail: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
