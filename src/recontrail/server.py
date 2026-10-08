"""Single-user loopback workbench. Not an internet-facing web service.

A capability token, exact Host/Origin checks and bounded raw-body uploads keep
unrelated browser sites away from local jobs. Native decoders are not sandboxed;
only open trusted captures. Reconstruction runs in one cancellable subprocess.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
import hmac
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import webbrowser
from filelock import FileLock, Timeout
from .images import EXTENSIONS, read_rgb
from .models import ReconError
from .report import ASSETS
from .storage import atomic_json, read_json

MAX_UPLOAD = 32 * 1024 * 1024
MAX_PROJECT = 256 * 1024 * 1024
MAX_IMAGES = 160
ID = re.compile(r"^[a-f0-9]{24}$")


class JobStore:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.token = secrets.token_urlsafe(32)
        self.mutex = threading.RLock()
        self.process = None
        self.active = None
        self.worker = None
        self.cancelled = set()
        self.lease = FileLock(str(self.root/".server.lock"), timeout=0)
        try:
            self.lease.acquire()
        except Timeout as exc:
            raise ReconError("This browser workspace is already in use.") from exc
        # No automatic restart: distinguish interrupted work from successful results.
        for p in self.root.glob("*/job.json"):
            if p.parent.is_symlink() or not ID.fullmatch(p.parent.name):
                continue
            data = read_json(p)
            if data.get("state") in {"running", "starting"}:
                data.update(state="interrupted", message="Previous server stopped; create a new job to retry.")
                atomic_json(p, data)

    def path(self, ident):
        if not ID.fullmatch(ident):
            raise ReconError("Invalid job identifier.")
        path = self.root/ident
        if path.is_symlink() or not (path/"job.json").is_file():
            raise ReconError("Unknown job.")
        return path

    def create(self):
        with self.mutex:
            if len(list(self.root.glob("*/job.json"))) >= 40:
                raise ReconError("Workspace has 40 jobs. Stop the server and archive old job directories first.")
            if sum(p.stat().st_size for p in self.root.rglob("*") if p.is_file()) > 4*1024**3:
                raise ReconError("Workspace exceeds 4 GiB. Stop the server and archive completed projects.")
            ident = secrets.token_hex(12)
            root = self.root/ident
            (root/"input").mkdir(parents=True)
            atomic_json(root/"job.json", {"id": ident, "state": "uploading", "images": 0,
                                          "bytes": 0, "created": time.time()})
            return read_json(root/"job.json")

    def status(self, ident):
        root = self.path(ident)
        data = read_json(root/"job.json")
        if (root/"output"/"status.json").is_file():
            data["progress"] = read_json(root/"output"/"status.json")
        if data["state"] == "complete":
            data["metrics"] = read_json(root/"output"/"metrics.json")
        data["report_available"] = (root/"output"/"report.html").is_file()
        return data

    def upload(self, ident, name, stream, length):
        with self.mutex:
            root = self.path(ident)
            info = read_json(root/"job.json")
            if info["state"] != "uploading":
                raise ReconError("Uploads are closed for this job.")
            if (not name or len(name) > 140 or any(c in name for c in '/\\\x00')
                    or any(ord(c) < 32 for c in name) or Path(name).suffix.lower() not in EXTENSIONS):
                raise ReconError("Use a supported image filename without path separators.")
            if info["images"] >= MAX_IMAGES or info["bytes"]+length > MAX_PROJECT:
                raise ReconError("Job upload limit: 160 images / 256 MiB.")
            # Prefix preserves browser selection order for sequence matching.
            target = root/"input"/f"{info['images']:04d}_{name}"
            try:
                remaining = length
                with target.open("xb") as f:
                    while remaining:
                        block = stream.read(min(remaining, 1024*1024))
                        if not block:
                            raise ReconError("Incomplete upload.")
                        f.write(block)
                        remaining -= len(block)
                read_rgb(target)  # Check decoded dimensions and actual codec, not just extension.
            except Exception:
                target.unlink(missing_ok=True)
                raise
            info.update(images=info["images"]+1, bytes=info["bytes"]+length)
            atomic_json(root/"job.json", info)
            return info

    def start(self, ident, options):
        with self.mutex:
            if self.active is not None:
                raise ReconError("One reconstruction is already running. Finish or cancel it first.")
            root = self.path(ident)
            info = read_json(root/"job.json")
            if info["state"] != "uploading" or info["images"] < 2:
                raise ReconError("Upload at least two photos to a new job.")
            mode, preset = options.get("mode", "run"), options.get("preset", "balanced")
            if mode not in {"run", "check"} or preset not in {"quick", "balanced"}:
                raise ReconError("Invalid workflow mode or preset.")
            cmd = [sys.executable, "-m", "recontrail", mode, str(root/"input"), "-o", str(root/"output")]
            if preset == "quick":
                cmd += ["--max-size", "1000", "--max-features", "2000", "--ba-points", "1200", "--ba-evaluations", "15"]
            calibration = options.get("intrinsics")
            if calibration is not None:
                if not isinstance(calibration, dict) or len(json.dumps(calibration)) > 8192:
                    raise ReconError("Intrinsics must be a small JSON object.")
                atomic_json(root/"intrinsics.json", calibration)
                cmd += ["--intrinsics", str(root/"intrinsics.json")]
            info.update(state="starting", mode=mode, preset=preset)
            atomic_json(root/"job.json", info)
            env = os.environ.copy()
            for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
                env[key] = "2"
            try:
                log = (root/"worker.log").open("w", encoding="utf-8")
                try:
                    process = subprocess.Popen(cmd, stdout=log, stderr=log, env=env, shell=False)
                finally:
                    log.close()
            except Exception:
                info.update(state="failed", message="Could not launch worker.")
                atomic_json(root/"job.json", info)
                raise
            self.process, self.active = process, ident
            info.update(state="running")
            atomic_json(root/"job.json", info)
            self.worker = threading.Thread(target=self._wait, args=(ident, process), daemon=True)
            self.worker.start()
            return info

    def _wait(self, ident, process):
        code = process.wait()
        with self.mutex:
            root = self.path(ident)
            info = read_json(root/"job.json")
            info.update(state="cancelled" if ident in self.cancelled else ("complete" if code == 0 else "failed"), exit_code=code)
            atomic_json(root/"job.json", info)
            self.process = self.active = None

    def cancel(self, ident):
        with self.mutex:
            if self.active != ident or self.process is None:
                raise ReconError("This job is not running.")
            self.cancelled.add(ident)
            self.process.terminate()
            process = self.process
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        return {"cancel_requested": True}

    def close(self):
        if self.active is not None:
            self.cancel(self.active)
        if self.worker:
            self.worker.join(timeout=8)
        self.lease.release()


class WorkbenchServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, store):
        self.store = store
        super().__init__(address, Handler)
        self.expected_host = f"127.0.0.1:{self.server_port}"
        self.expected_origin = f"http://{self.expected_host}"


class Handler(BaseHTTPRequestHandler):
    server_version = "ReconTrail/0.1"

    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def log_message(self, *args):
        pass  # No tokens, filenames or private capture paths in access logs.

    def allowed(self, auth=False):
        if self.headers.get("Host") != self.server.expected_host:
            self.reply(403, {"error": "Invalid Host."})
            return False
        origin = self.headers.get("Origin")
        if origin is not None and origin != self.server.expected_origin:
            self.reply(403, {"error": "Cross-origin access denied."})
            return False
        if auth and not hmac.compare_digest(self.headers.get("X-ReconTrail-Token", ""), self.server.store.token):
            self.reply(403, {"error": "Missing or invalid local token."})
            return False
        return True

    def reply(self, status, data, content_type="application/json; charset=utf-8"):
        payload = json.dumps(data, ensure_ascii=False, allow_nan=False).encode() if isinstance(data, (dict, list)) else data
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self' blob:; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        path = urlsplit(self.path).path
        if not self.allowed(auth=path.startswith("/api/")):
            return
        try:
            public = {"/": ("workbench.html", "text/html; charset=utf-8"),
                      "/style.css": ("style.css", "text/css; charset=utf-8"),
                      "/app.js": ("app.js", "text/javascript; charset=utf-8")}
            if path in public:
                asset, mime = public[path]
                return self.reply(200, (ASSETS/asset).read_bytes(), mime)
            if path == "/api/jobs":
                ids = [p.parent.name for p in self.server.store.root.glob("*/job.json") if ID.fullmatch(p.parent.name)]
                return self.reply(200, [self.server.store.status(ident) for ident in ids])
            parts = path.strip("/").split("/")
            if len(parts) == 3 and parts[:2] == ["api", "jobs"]:
                return self.reply(200, self.server.store.status(parts[2]))
            if len(parts) == 5 and parts[:2] == ["api", "jobs"] and parts[3] == "files":
                root = self.server.store.path(parts[2])
                allowed = {"report.html": "text/html; charset=utf-8", "cloud.ply": "application/octet-stream",
                           "metrics.json": "application/json", "audit.json": "application/json",
                           "cameras.json": "application/json", "provenance.json": "application/json"}
                name = parts[4]
                info = self.server.store.status(parts[2])
                if name not in allowed or (name != "report.html" and info["state"] != "complete"):
                    raise ReconError("Artifact unavailable for this job.")
                target = root/"output"/name
                if target.is_symlink() or not target.is_file():
                    raise ReconError("Artifact does not exist.")
                # Downloaded reports execute only when the user opens a new blob/file document.
                return self.reply(200, target.read_bytes(), allowed[name])
            return self.reply(404, {"error": "Not found."})
        except (ReconError, OSError, ValueError) as exc:
            self.reply(400, {"error": str(exc)[:500]})

    def do_POST(self):
        if not self.allowed(auth=True):
            return
        try:
            if self.headers.get("Transfer-Encoding"):
                raise ReconError("Chunked uploads are not supported.")
            value = self.headers.get("Content-Length", "")
            if not value.isdigit():
                raise ReconError("Content-Length is required.")
            length = int(value)
            split = urlsplit(self.path)
            parts = split.path.strip("/").split("/")
            is_upload = len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "images"
            if length > (MAX_UPLOAD if is_upload else 16*1024) or (is_upload and length == 0):
                return self.reply(413, {"error": "Request exceeds size limit (32 MiB per image)."})
            if is_upload:
                name = parse_qs(split.query).get("name", [""])[0]
                result = self.server.store.upload(parts[2], name, self.rfile, length)
            else:
                raw = self.rfile.read(length)
                if len(raw) != length:
                    raise ReconError("Incomplete request.")
                data = json.loads(raw) if raw else {}
                if not isinstance(data, dict):
                    raise ReconError("Request must be a JSON object.")
                if split.path == "/api/jobs":
                    result = self.server.store.create()
                elif len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "start":
                    result = self.server.store.start(parts[2], data)
                elif len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "cancel":
                    result = self.server.store.cancel(parts[2])
                else:
                    return self.reply(404, {"error": "Not found."})
            self.reply(200, result)
        except (ReconError, OSError, ValueError, TypeError) as exc:
            self.reply(400, {"error": str(exc)[:500]})


def serve(workspace, port=8765, open_browser=True):
    if not 1 <= port <= 65535:
        raise ReconError("Port must be between 1 and 65535.")
    store = JobStore(workspace)
    server = None
    try:
        server = WorkbenchServer(("127.0.0.1", port), store)
        url = f"http://{server.expected_host}/#token={store.token}"
        print(f"ReconTrail workbench: {url}\nKeep this local access link private. Press Ctrl+C to stop.", flush=True)
        if open_browser:
            webbrowser.open(url)
        server.serve_forever(poll_interval=.25)
    finally:
        if server:
            server.server_close()
        store.close()
