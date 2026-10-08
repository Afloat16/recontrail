"""Atomic workspace metadata. Never delete or silently reuse unrelated files."""
from contextlib import contextmanager
from pathlib import Path
import hashlib
import json
import os
import tempfile
from filelock import FileLock, Timeout
from .models import ReconError


def atomic_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".rt-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def digest(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def fingerprint(paths, config, calibration=None):
    # Full file hashes: mtime is not a safe cache key. Do not record source absolute paths.
    data = {"inputs": [(p.name, digest(p)) for p in paths], "config": config,
            "calibration": calibration}
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


@contextmanager
def workspace(path: Path, signature: str, resume=False):
    path = path.resolve()
    path.mkdir(parents=True, exist_ok=True)
    try:
        with FileLock(str(path / ".recontrail.lock"), timeout=0):
            marker = path / "project.json"
            if marker.exists():
                old = read_json(marker)
                if not isinstance(old, dict) or old.get("kind") != "recontrail-project" or not resume:
                    raise ReconError("Output already contains a project. Use --resume, or choose a new output.")
                if old.get("signature") != signature:
                    raise ReconError("Input, calibration, dependencies or settings changed. Choose a new output.")
            else:
                if any(p.name != ".recontrail.lock" for p in path.iterdir()):
                    raise ReconError("Output is not empty and is not a ReconTrail project. Choose a new directory.")
                atomic_json(marker, {"kind": "recontrail-project", "signature": signature})
            yield path
    except Timeout as exc:
        raise ReconError("Another process owns this output directory. Stop it or choose a different output.") from exc
