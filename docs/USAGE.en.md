# Usage and troubleshooting

[Home](../README.md) · [简体中文](USAGE.md)

## Start with a useful capture

Begin with 12–60 overlapping photographs of one static, textured, mostly matte scene. This is a conservative starting suggestion, not a success guarantee. Move the camera to produce parallax rather than only rotating in place. Keep lens, zoom, image dimensions, and exposure consistent; include more than one viewing height and depth. See the [COLMAP capture guidance](https://colmap.github.io/faq.html) for background.

Photo mode reads top-level JPG/JPEG, PNG, WebP, TIFF/TIF, and BMP files. It does not recursively scan, follow symbolic links, or decode HEIC/RAW. CLI images are limited to 64 MiB and 40 million decoded pixels each. Browser uploads are limited to 32 MiB per image, 160 images, and 256 MiB per batch. The CLI defaults to 160 images, with an explicit configurable limit. Working images are resized to `--max-size`; reported pixel errors refer to these working images.

Only unreadable images and exact decoded-pixel duplicates are excluded automatically. Blur, exposure and texture warnings remain advisory. Default heuristics include Laplacian variance below 45 on a common thumbnail scale, more than half the pixels below 10 or above 245 in grayscale, and fewer than 150 SIFT features or fewer than 6 occupied cells of a 4×4 grid. These are not calibrated quality probabilities.

## Shared camera calibration

Use `--intrinsics camera.json` with an actual shared pinhole calibration:

```json
{
  "width": 1920,
  "height": 1080,
  "fx": 1450.0,
  "fy": 1450.0,
  "cx": 960.0,
  "cy": 540.0,
  "distortion": [0, 0, 0, 0, 0]
}
```

The numbers above are **schema examples**, not a calibration for your camera. Dimensions must match the image after EXIF orientation. Intrinsics use pixels and apply to every input image, so do not mix lenses, crops, or image dimensions. Optional distortion coefficients follow OpenCV order and support 4, 5, 8, 12, or 14 values. The model is zero-skew pinhole. Do not supply distortion twice for already-undistorted images.

Without calibration, ReconTrail estimates focal length from EXIF 35mm-equivalent focal length when available, otherwise `focal_ratio × max(width, height)` with a default ratio of 1.2. The lite backend keeps intrinsics fixed. An incorrect focal length can produce distorted geometry despite a small residual. Ordinary photo reconstruction remains at arbitrary scale, including when calibrated intrinsics are supplied.

## Calibrated stereo

The [stereo JSON example](../examples/stereo.example.json) contains `image_size`, `K_left`, `K_right`, `distortion_left`, `distortion_right`, `R`, `t`, and `unit`. Replace all calibration values with measurements for the actual pair.

The transform convention is `X_right = R @ X_left + t`. When the right camera lies to the right of the left camera with aligned axes, `t_x` is usually negative; `t` is not the camera center.

```bash
python -m recontrail stereo left.png right.png --calibration stereo.json -o ../stereo-result --max-depth 15 --stride 2
```

Units may be `m`, `cm`, `mm`, or `arbitrary`. `--max-depth` uses that same unit. Images must be synchronized and the scene static. Predominantly vertical baselines and negative horizontal disparity are rejected. The largest image dimension must not exceed 2560 pixels; rescale images and intrinsics consistently beforehand when necessary.

Outputs use the **original left-camera coordinate system**, not the rectified coordinate system. Bidirectional SGBM uses a 1-pixel consistency threshold, rejects invalid/nonpositive/out-of-range depths, and samples with a default stride of 2. Triangles are added only for cells with valid corners and relative depth span below 4%. Output is an open visible surface, with vertex colors but no UV/MTL texture assets, hole filling, or watertightness guarantee. See [OpenCV StereoSGBM](https://docs.opencv.org/4.x/d2/d85/classcv_1_1StereoSGBM.html).

## Reading the result

`complete` means all usable input images registered; it does **not** mean the object's surface is complete. `partial` means only a subset registered. `points` counts final retained points. For the photo metrics, each landmark's error is its maximum observation reprojection error; the report then summarizes the median and 95th percentile across landmarks. COLMAP `points3D.txt` uses the mean observation error required by that export. Stereo reports valid-pixel fraction, not a fabricated reprojection error.

The final lite bundle-adjustment budget defaults to 2,500 long-track points. An accepted optimization keeps this subset and filters it again. `--ba-points` increases the budget. Solver budget exhaustion is not reported as convergence; inspect the termination reason and objective change.

`--resume` verifies inputs, settings, dependency fingerprints, and completed output hashes. It reuses verified completed results or retries a matching interrupted project. It does not restore a mid-optimization checkpoint. Keep `check` and `run` outputs separate, and never nest input/output folders.

## Optional COLMAP backend

```bash
python -m pip install -e ".[colmap]"
python -m recontrail run ./photos -o ../colmap-result --backend colmap
```

The adapter targets PyCOLMAP 4.2.x. It is not included in the default installation. The recorded local validation did not execute this backend or its independent reader test. Run the optional tests in your own supported environment:

```bash
python -m pip install -e ".[dev,colmap]"
python -m pytest -q -m optional
```

## Troubleshooting

| Symptom | Check | Next action |
|---|---|---|
| Fewer than two usable images | Corruption or exact duplicates | Inspect rejection records and use distinct intact views |
| No reliable initial pair | Weak texture, planar dominance, pure rotation, low parallax | Move around the scene and include varying depths/heights |
| Disconnected matching graph | Missing overlap or missed candidate pairs | Capture bridging views; try `--pairing all` for small sets |
| Unregistered cameras | Insufficient tracks or scene motion | Inspect `unregistered`; do not treat a partial model as complete |
| No stereo depth | Calibration, image order, synchronization or disparity | Verify transform direction, units, dimensions and left/right order |
| Output directory rejected | Unrelated output, changed config or active lock | Preserve existing data and choose a fresh directory |
| Browser returns 403 | Invalid token or Host | Use the exact current `127.0.0.1` URL from the terminal |
| Installation/import failure | Dependency conflicts or multiple OpenCV wheels | Use a clean virtual environment; run `doctor` and retain the error |

## Video and local storage

`video` picks the sharpest frame in each FPS-based time window and omits exact sampled-frame duplicates. Defaults are a 0.75-second interval, 160 output frames, and at most 36,000 decoded frames. Timestamps are derived from frame index/FPS; precise timing of variable-frame-rate video is not guaranteed. Only local files are accepted.

Browser input copies live at `<workspace>/<project-id>/input`; reports live under that project's `output`. Normalized exported images omit EXIF, but uploaded originals may retain metadata. The workbench does not automatically delete photographs. Stop it before archiving/deleting projects. It limits projects to 40 and checks a 4 GiB workspace threshold when creating a project; this is not a strict runtime disk quota.

The server is for a single user on loopback, not public hosting. Review reports, filenames and geometry before sharing. See [security guidance](../SECURITY.md).
