<div align="center">

# ReconTrail

### Inspect your photos. Reconstruct in 3D. Share the evidence.

**A local-first, CPU-ready photogrammetry workbench for capture checks, sparse 3D reconstruction, calibrated stereo, and portable offline reports.**

[![Tests and package](https://github.com/Afloat16/recontrail/actions/workflows/ci.yml/badge.svg)](https://github.com/Afloat16/recontrail/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e.svg)](LICENSE)
[![Runs locally](https://img.shields.io/badge/Runtime-local--first-0f766e)](#privacy-and-safety)

**English** · [简体中文](README.zh-CN.md)

[Quick start](#quick-start) · [Try the demo](#try-it-without-taking-photos) · [Usage guide](docs/USAGE.en.md) · [Validation](docs/VALIDATION.en.md) · [Contributing](CONTRIBUTING.md)

</div>

---

## Why ReconTrail?

A reconstruction is more useful when you can inspect the capture, understand what registered, and share the result without asking someone else to install your toolchain.

ReconTrail brings these steps into one small workflow:

```text
Photos or video → Capture checks → Sparse reconstruction → Inspect & export
Calibrated stereo pair ──────────→ Dense visible surface ─→ Inspect & export
```

**Check before you compute.** Inspect blur, exposure, texture, exact duplicates, and geometric connectivity. Warnings explain problems without silently discarding potentially useful views.

**Start on the hardware you have.** The default reconstruction path runs on a CPU. No GPU, account, cloud service, or model-weight download is required. Dependencies need an internet connection for the initial installation; photo processing stays local.

**Keep a result you can inspect.** Export geometry, camera poses, diagnostics, processing parameters, input fingerprints, and a self-contained HTML point-cloud report. Open the report offline and share it deliberately.

ReconTrail is intended for small capture experiments, teaching multi-view geometry, inspecting a photo set before a larger reconstruction, and sharing early geometric results. It complements established reconstruction tools; it is not a replacement for a complete photogrammetry suite.

## What it does

| Workflow | Input | Output | Important distinction |
|---|---|---|---|
| **Capture inspection** | Overlapping photos of a static scene | Per-image checks and a geometric connectivity report | Diagnostics are heuristics, not success probabilities |
| **Photo reconstruction** | Multi-view photos; optional camera intrinsics | Colored sparse PLY, camera poses, COLMAP text model, offline report | Sparse geometry at arbitrary scale, **not a dense mesh** |
| **Calibrated stereo** | Left/right images and a reliable calibration | Dense colored points, open-surface PLY and OBJ | Scale comes from the baseline; no hole filling or UV texture atlas |
| **Video preparation** | A local video | A sharper frame from each time window | Frame extraction is preparation, not a guarantee of useful viewpoints |
| **Optional COLMAP backend** | Multi-view photos | The same inspection/export workflow | PyCOLMAP 4.2.x is optional; see the recorded validation scope |

The browser workbench handles photo inspection and sparse reconstruction. Calibrated stereo and video frame extraction are available through the CLI. The current workbench and report contain both Chinese and English labels.


## Quick start

Requires **Python 3.10+**. Use a virtual environment to keep dependencies separate.

```bash
git clone https://github.com/Afloat16/recontrail.git
cd recontrail
python -m venv .venv
```

Activate it on Linux or macOS:

```bash
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Then install from the checkout and start the workbench:

```bash
python -m pip install .
python -m recontrail serve
```

Open the **complete local URL printed in the terminal**, choose overlapping photos of one static scene, and start processing. Save the resulting offline report and PLY. Keep the access token in the URL private.

The commands above install from this repository. A PyPI package publication is not assumed. `start.sh` and `start.bat` provide convenience launchers; target-platform validation is documented separately.

### Try it without taking photos

```bash
python -m recontrail demo -o ../recontrail-demo --run
```

Open `../recontrail-demo/result/report.html` in a browser. The demo creates an original textured, multi-depth scene and runs real feature matching, camera estimation, triangulation, and optimization. Ground-truth poses are used for tests, **not supplied to the reconstruction**.

## CLI recipes

```bash
# Inspect capture quality and overlap before reconstructing.
python -m recontrail check ./photos -o ../capture-check

# Reconstruct with the default CPU backend.
python -m recontrail run ./photos -o ../capture-result

# Use a shared calibrated camera when available.
python -m recontrail run ./photos -o ../calibrated-result --intrinsics camera.json

# Reuse only a completed result whose inputs, configuration and outputs verify.
python -m recontrail run ./photos -o ../calibrated-result --intrinsics camera.json --resume

# Extract frames, then reconstruct the resulting sequence.
python -m recontrail video ./capture.mp4 -o ../sampled --interval 0.75
python -m recontrail run ../sampled/images -o ../video-result --pairing sequence

# Generate dense geometry from a correctly calibrated stereo pair.
python -m recontrail stereo left.png right.png --calibration stereo.json -o ../stereo-result --max-depth 15

# Inspect the runtime and optional backend availability.
python -m recontrail doctor
```

Input and output directories must be separate and must not contain one another. Use different outputs for `check` and `run`. `--resume` means verified completed-result reuse or a same-configuration retry, not intermediate optimizer checkpointing.

See the [English usage guide](docs/USAGE.en.md) for calibration schemas, capture suggestions, optional backends, and common failure cases. Example JSON files are in [`examples/`](examples/).

## Outputs you can keep

```text
result/
├── report.html          # Self-contained interactive report; no CDN
├── cloud.ply            # All final retained points; stereo can include faces
├── cameras.json         # Camera transforms and centers
├── metrics.json         # Registration, error, scale and optimization status
├── audit.json           # Capture diagnostics and matching graph
├── provenance.json      # Configuration, calibration, versions and input hashes
├── complete.json        # SHA-256 manifest of completed outputs
├── sparse/0/*.txt       # Photo mode: COLMAP cameras/images/points3D
├── images/*.png         # Photo mode: normalized registered images
├── image_mapping.json   # Photo mode: normalized-to-source filename mapping
└── mesh.obj             # Stereo only: open surface with vertex colors
```

The report previews at most 14,000 points; PLY retains all **final** points. The lite backend's default final bundle-adjustment budget is 2,500 long-track points. An accepted optimization retains that subset and filters it again; increase `--ba-points` when appropriate. Neither export is a claim that every original candidate point survived.

Photo poses use `X_camera = R @ X_world + t`. COLMAP export follows the [official text format](https://colmap.github.io/format.html); internal track consistency is tested, while independent PyCOLMAP import is an optional test.

## Scope and validation

The recorded local CPU run completed **57 tests with 2 optional PyCOLMAP tests skipped**. The pre-upload rerun produced the same counts. The CI badge above links to actual workflow status rather than a hard-coded passing claim.

| Recorded synthetic example | Result |
|---|---:|
| Registered photo views | 8 / 8 |
| Final sparse points | 1,199 |
| Median reprojection error | 0.174 px |
| 95th-percentile reprojection error | 0.498 px |
| Calibrated-stereo colored points | 53,735 |
| Calibrated-stereo triangles | 104,790 |

These numbers describe a project-generated synthetic scene, **not a real-world accuracy benchmark**. Low reprojection error does not establish accurate object dimensions. Read the [English validation summary](docs/VALIDATION.en.md) and [detailed validation record](docs/VALIDATION.md) for the environment, independent truth checks, HTTP/worker tests, browser coverage, and remaining gaps.

The lite backend uses fixed intrinsics and reconstructs one connected model. Focal estimates are a preview convenience, not camera self-calibration. Transparent or reflective materials, weak or repetitive texture, motion, pure rotation, rolling shutter, and insufficient parallax can fail. Fisheye support, multiple-component alignment, georeferencing, watertight meshes, and UV texturing are outside this version's scope. Stereo requires standard zero-skew pinhole calibration and predominantly horizontal rectified disparity.

## Privacy and safety

The workbench is **single-user and loopback-only**, with capability-token authentication, Host/Origin checks, bounded uploads, explicit artifact downloads, and one cancellable worker. Input signatures, project locks, and output checksums prevent silent reuse of mismatched results or overwriting unrelated projects.

Do not expose this server to the internet. Native image/video decoders are not sandboxed: use trusted captures and keep dependencies updated. Reports and exports may reveal scene geometry and source filenames; review them before sharing. See [SECURITY.md](SECURITY.md).

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m build

# Optional backend and independent COLMAP-reader tests.
python -m pip install -e ".[colmap]"
python -m pytest -q -m optional
```

Useful starting points: [architecture](docs/ARCHITECTURE.md), [roadmap (中文)](docs/ROADMAP.md), [contribution guide](CONTRIBUTING.md), and [issues](https://github.com/Afloat16/recontrail/issues). Reproducible failures, openly licensed real-world test captures, documentation improvements, and platform checks are especially valuable.

## References and license

ReconTrail's original code is [MIT licensed](LICENSE). OpenCV, NumPy, SciPy, Pillow, filelock, and optional PyCOLMAP retain their own licenses. Standard methods are credited to their authors; no compared project's source implementation or model weights are vendored.

See [third-party notices](THIRD_PARTY_NOTICES.md), [references and their role in this project](docs/REFERENCES.md), [BibTeX](docs/references.bib), and [`CITATION.cff`](CITATION.cff). The [research notes (中文)](docs/RESEARCH.md) explain the comparisons with COLMAP, Meshroom, Open3D, OpenMVG, OpenMVS, WebODM, Nerfstudio, VGGT, and DUSt3R.

---

**Useful to your capture workflow?** Star the repository to bookmark it, try the built-in demo, and share a reproducible result or failure case in an issue.
