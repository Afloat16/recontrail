# Third-party notices and attribution

Reviewed for the recorded 2026-10-08 implementation. ReconTrail's MIT license covers original project code, original UI, documentation, tests, synthetic fixtures and their generated screenshots. It does **not** replace any dependency's license. Dependencies are installed separately; their source, shared libraries, fonts, weights and license files are not bundled in the ReconTrail wheel.

## Runtime dependencies

| Component | Role | Recorded version | Upstream license / authoritative reference |
|---|---|---|---|
| OpenCV / opencv-python-headless | SIFT, FLANN, essential-matrix estimation, PnP, triangulation, rectification, SGBM, video codecs | 4.13.0 / wheel 4.13.0.92 | OpenCV >=4.5 Apache-2.0: https://opencv.org/license/ ; wheel and bundled third-party notices: https://github.com/opencv/opencv-python |
| NumPy | Array operations and linear algebra | 2.3.5 | BSD-3-Clause: https://github.com/numpy/numpy/blob/main/LICENSE.txt |
| SciPy | Sparse nonlinear least squares and rotations | 1.17.0 | BSD-3-Clause: https://github.com/scipy/scipy/blob/main/LICENSE.txt |
| Pillow | Image decoding, EXIF orientation, standard image export | 12.3.0 | MIT-CMU for recorded version: https://pillow.readthedocs.io/en/stable/about.html#license ; older allowed releases may use different historical identifiers |
| filelock | Cross-process workspace locks | 3.29.0 | MIT for recorded version: https://github.com/tox-dev/filelock ; retain the installed release's actual license, not a presumed identifier for older releases |
| COLMAP / PyCOLMAP, optional | Mature incremental SfM backend | Adapter targets 4.2.x; not locally installed | BSD-3-Clause project license plus independently licensed dependencies: https://github.com/colmap/colmap/blob/main/COPYING.txt |

NumPy/SciPy/OpenCV/Pillow binary wheels can include separately licensed numerical or codec libraries. If distributing an environment, executable, container or wheels of dependencies, retain **their complete license files and notices** and review those exact binaries. The top-level licenses above are not a complete binary redistribution bill of materials. ReconTrail's source/wheel packaging does not redistribute those dependencies.

## Development and external tools

pytest and setuptools use MIT; Playwright uses Apache-2.0; GitHub CLI and Git are separate user-installed publishing tools. Build/test dependencies are not needed for normal reconstruction. Chromium, system fonts and browser executables are not included in release artifacts.

## Compared projects, not runtime dependencies

Meshroom (MPL-2.0), OpenMVG (MPL-2.0), OpenMVS (AGPL-3.0), Open3D (MIT), WebODM (AGPL-3.0), Nerfstudio (Apache-2.0), VGGT (custom code/model conditions) and DUSt3R (CC BY-NC-SA 4.0 code plus checkpoint conditions) were reviewed to understand workflow, representation, interoperability and deployment tradeoffs. No code, logo, image dataset or checkpoint from these projects was copied into ReconTrail. Their names identify the respective projects, not endorsement or affiliation.

See `docs/RESEARCH.md` for date-specific research findings and `docs/REFERENCES.md` for algorithm attribution. SIFT, RANSAC, essential geometry, PnP, bundle adjustment and semi-global stereo are prior methods: ReconTrail does not claim to have invented them. OpenCV and SciPy provide their underlying implementations; the integration, validation policies and evidence/export flow are project code.

Future borrowed code must retain its original copyright and license header, identify the source URL and revision, and list modifications here. A bibliography entry alone does not grant permission to copy source code or model weights.
