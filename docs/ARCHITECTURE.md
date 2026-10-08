# Architecture and invariants

## Data flow

```text
CLI / loopback browser
       │
       ├── photo discovery → orientation/optional undistortion → bounded SIFT
       │       → candidate pairs → mutual ratio matching → essential verification
       │       → overlap components + input audit
       │       → lite incremental SfM OR optional PyCOLMAP
       │       → reprojection/depth filtering
       │
       └── calibrated stereo → rectification → bidirectional SGBM
               → left/right + depth validity → sampled points + open grid faces
                               │
                     PLY / OBJ / camera JSON / COLMAP text
                               │
                     provenance + offline report + checksummed completion
```

## Modules and ownership

`images.py` controls ingestion and image normalization; `matching.py` controls matching policy and graph diagnostics; `geometry.py` establishes a single pinhole convention. `sfm.py` owns point/feature lookup and conservative registration. `refine.py` constructs the project-specific sparse residual graph and calls SciPy's solver. `stereo.py` owns calibration validation, consistency masks and surface sampling, while OpenCV supplies rectification/SGBM. `colmap_backend.py` is a separately installed, version-bounded adapter, not a vendored solver.

`storage.py` owns locks, fingerprints and atomic JSON. `pipeline.py` owns stage state, artifact creation and reuse. `exports.py` is the only exchange-format writer. `report.py` embeds escaped data into the dependency-free viewer. `server.py` provides the deliberately small local HTTP contract. `video.py` only samples input frames; it does not estimate motion.

## Lite geometry

Features are OpenCV SIFT descriptors, matched using bidirectional FLANN ratio tests. Geometric verification is calibrated essential-matrix RANSAC, pose recovery and positive-depth/reprojection checks. A seed pair must pass a median triangulation-angle threshold and not be strongly homography dominated. Its score favors many verified tracks, useful parallax and lower homography dominance. This is a conservative policy, not a published novelty claim.

The seed camera defines the world origin; the other seed translation has unit length. New images are registered from unambiguous 2D–3D correspondences using OpenCV PnP RANSAC and LM refinement. Tracks are extended only after depth and reprojection checks. Conflicting tracks are not force-merged. New points are triangulated only between registered cameras. The algorithm stops when no eligible camera can be added; only one reconstruction component is exported.

Bundle adjustment has fixed intrinsics, one fixed camera and a baseline-norm residual to constrain scale. Camera rotations use Rodrigues vectors, points use Euclidean xyz, observation residuals use image coordinates, robust loss is soft-L1. Sparse Jacobian structure exposes each observation's camera and point dependency. The default optimization budget chooses up to 2,500 longest tracks, which become the retained point set if optimization is accepted. The result is accepted only for finite parameters and decreased robust cost; convergence is reported separately. No uncertainty covariance or metric-accuracy certificate is computed.

## Coordinate and output invariants

- `X_camera = R @ X_world + t`; x right, y down, z forward. Camera center is `-R.T @ t`.
- Photo geometry has arbitrary scale. Stereo scale is inherited from caller-supplied translation units.
- Every exported photo landmark has at least two observations, finite coordinates, positive depth and bounded reprojection error.
- COLMAP tracks refer to exported image IDs and original feature-array indices; reverse lookup in `images.txt` must agree.
- Exported camera intrinsics correspond to exported normalized images, not unscaled or distorted originals.
- PLY/OBJ face indices refer to sampled valid points; cells crossing invalid regions or substantial depth jumps are not connected.
- The browser preview may subsample, but the final exported point cloud is not subsampled merely for display.

## Persistence and local API

`project.json` identifies owned CLI output directories. A file lock prevents concurrent writers. A signature includes full input file hashes, names, configuration, calibration, package version and dependency environment. SHA-256 is a cache integrity check, not an authenticity signature. `complete.json` is written only after artifact creation and hashes exported files. Failed runs keep a diagnostic report and do not create a completed marker. Matching retries restart computation, with a fresh optional COLMAP database; intermediate optimization is not resumed.

Local workbench endpoints:

```text
GET  /                       static UI; exact Host required
GET  /api/jobs                project history
POST /api/jobs                create owned random-ID directory
POST /api/jobs/{id}/images?name=...    raw bounded image body
POST /api/jobs/{id}/start     {mode: run|check, preset: quick|balanced, intrinsics?: object}
GET  /api/jobs/{id}           persisted state and current stage
POST /api/jobs/{id}/cancel    terminate active worker, escalate after timeout
GET  /api/jobs/{id}/files/{allowlisted_name}   completed artifact download
```

All API routes require `X-ReconTrail-Token`; exact Host and optional Origin checks reject cross-origin access. The token is delivered in the loopback URL fragment, then removed from the address bar and retained in sessionStorage. Browser CSP rejects external scripts/frames; report JSON escapes script delimiters and data is rendered via `textContent`. No user field is interpolated into a shell command; workers are launched with an argument list and `shell=False`.

The server has one active subprocess and a workspace lock, but is not a sandbox, a hardened public server or a multi-user service. Native codecs remain an attack surface. Upload count/bytes/dimensions are bounded; CLI users can raise resource settings and are responsible for memory/disk capacity. Workbench job directories persist across restarts; interrupted tasks are marked as such and are not automatically restarted.
