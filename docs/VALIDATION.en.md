# Validation — 0.1.0

[Home](../README.md) · [Detailed record (中文)](VALIDATION.md) · [Structured evidence](validation-summary.json)

Recorded on 2026-10-08. This page distinguishes executed checks from synthetic geometry checks and unexecuted coverage. Current remote workflow results are available in [GitHub Actions](https://github.com/Afloat16/recontrail/actions); configuration alone is not evidence of passing CI.

## Local test results

The recorded environment was Linux x86_64, Python 3.13.5, NumPy 2.3.5, SciPy 1.17.0, OpenCV 4.13.0, Pillow 12.3.0, filelock 3.29.0, and pytest 9.0.2.

**57 passed, 2 skipped.** Both skipped checks require PyCOLMAP, which was not installed. A pre-upload rerun also returned 57 passed and 2 skipped in 21.05 seconds. Python compilation and JavaScript syntax checks passed in the original validation. Compilation is not linting, type checking, or a security audit.

## Synthetic photo reconstruction

The original demo renders three textured planes at different depths from eight viewpoints, at 720×540 pixels. No external photos or models are used. Reconstruction consumes images and intrinsics, **not ground-truth poses**. Ground truth is used only by independent test assertions.

The saved example uses a CPU lite configuration with 2,000 features/image, a final point budget of 1,200, and 15 optimization evaluations allowed.

| Metric | Saved run |
|---|---:|
| Registered images | 8 / 8 |
| Candidate landmarks before refinement | 3,203 |
| Final retained landmarks | 1,199 |
| Median reprojection error | 0.173775 px |
| 95th-percentile reprojection error | 0.498318 px |
| Objective before / after | 259.772237 / 102.475768 |
| Solver evaluations | 13; accepted and converged |
| Scale | Arbitrary |

Pixel errors refer to normalized working images. Final points come from the long-track budget subset and subsequent filtering, not all candidates. Truth comparisons remove scale/origin freedom using known baseline and first-camera position; tests bound camera-center error and distance to the known depth planes. This simple synthetic scene does not establish general real-world accuracy.

## Calibrated stereo

The saved stereo run uses the first two synthetic views, correct calibration, a roughly 0.235666 m baseline, a 15 m depth limit, and stride 2. It produced **53,735 colored points and 104,790 triangles**, with approximately 55.25% valid disparity pixels.

Tests check finite positive depths, left/right consistency, distance to the known depth planes, OBJ face indices, and rejection of reversed stereo input. Valid-pixel fraction is not accuracy. The result is an open surface, not a watertight or UV-textured object.

## Integration and safety coverage

Executed tests cover invalid configuration, corrupt/blank images, EXIF orientation, exact decoded-pixel duplicates, symlink rejection, unrelated output protection, project locks, changed inputs, altered completion manifests, report escaping, PLY/OBJ structure, and bidirectional COLMAP track consistency. Independent PyCOLMAP reading is an optional skipped check. MJPG video extraction passed; other codecs and precise variable-frame-rate timing were not validated.

The actual local HTTP/worker flow passed: create a job, upload eight images, supply intrinsics, start a real reconstruction subprocess, poll completion, and download the report. Tests also exercise cancellation, token/Host/Origin rejection, invalid paths and names, corrupt/incomplete uploads, and explicit artifact-download restrictions.

Chromium/Playwright interactions with an actual offline report passed, including camera counts, drag rotation, view reset, and a 390-pixel layout without horizontal overflow or JavaScript errors. **The full browser upload flow was not completed:** the validation environment blocked loopback navigation. Static workbench layout and server-side HTTP tests do not replace that missing browser coverage.

## Packaging and remaining gaps

The original wheel was built through the setuptools PEP 517 backend, installed outside the source tree, and checked for packaged web assets and real worker reconstruction. A `pip wheel` frontend attempt timed out; the direct backend build succeeded. Existing runtime dependencies were reused, so this was not a fresh operating-system installation test.

The original local record does not validate real-world datasets, production scale, Windows/macOS execution, GPU behavior, the PyCOLMAP backend, full browser upload interaction, or a third-party security audit. Consult actual remote CI runs for any newer platform evidence rather than inferring it from the matrix.

`metrics.json` records `elapsed_seconds` after geometric processing but before every export completes. It is not full end-to-end wall-clock time and must not be used as a cross-project speed claim. The historical publication fields in `validation-summary.json` describe the original pre-publication check, not the current state of this repository.
