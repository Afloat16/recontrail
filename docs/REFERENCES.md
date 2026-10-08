# References and use map

Accessed/reviewed 2026-10-08 unless a paper year is stated. References document existing methods and interoperability; they do not imply code copying, upstream endorsement or a new algorithm invented here. BibTeX entries are in `references.bib`.

## Methods actually used

**[1] David G. Lowe.** “Distinctive Image Features from Scale-Invariant Keypoints.” *International Journal of Computer Vision* 60(2), 91–110, 2004. Author's reference page: https://www.cs.ubc.ca/~lowe/keypoints/ . Used through OpenCV SIFT in `images.py`; ratio matching policy in `matching.py`. No source from the historical SIFT demo is incorporated.

**[2] OpenCV contributors.** Camera Calibration and 3D Reconstruction, OpenCV 4.x documentation. https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html . Authoritative API and conventions for `findEssentialMat`, `recoverPose`, `solvePnPRansac`, `solvePnPRefineLM`, `triangulatePoints`, `stereoRectify` and `reprojectImageTo3D`. Used in `matching.py`, `sfm.py`, `geometry.py`, `stereo.py`.

**[3] OpenCV contributors.** `cv::SIFT` reference. https://docs.opencv.org/4.x/d7/d60/classcv_1_1SIFT.html . Feature extraction options and returned keypoints/descriptors. Used in `images.py`.

**[4] OpenCV contributors.** `cv::StereoSGBM` reference. https://docs.opencv.org/4.x/d2/d85/classcv_1_1StereoSGBM.html . OpenCV's modified semi-global matching implementation, parameters and fixed-point disparity representation. Used in `stereo.py`. The implementation is OpenCV's, not a literal reproduction of the original semi-global matching paper.

**[5] SciPy contributors.** `scipy.optimize.least_squares` documentation. https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html . Trust-region least squares, sparse Jacobian structure and robust loss. `refine.py` supplies original camera/point residual assembly, while numerical optimization is SciPy's implementation.

**[6] Johannes Lutz Schönberger and Jan-Michael Frahm.** “Structure-from-Motion Revisited.” *CVPR*, 2016. Official project and citation: https://github.com/colmap/colmap . Attribution for the optional mature COLMAP SfM backend; not a claim that the lite backend reproduces the full COLMAP algorithm.

**[7] Johannes Lutz Schönberger, Enliang Zheng, Marc Pollefeys and Jan-Michael Frahm.** “Pixelwise View Selection for Unstructured Multi-View Stereo.” *ECCV*, 2016. Official citation: https://github.com/colmap/colmap . Read to distinguish COLMAP MVS from sparse SfM. Its dense implementation is not bundled or invoked by the current adapter.

**[8] COLMAP contributors.** Output Format, FAQ and PyCOLMAP API. https://colmap.github.io/format.html ; https://colmap.github.io/faq.html ; https://colmap.github.io/pycolmap/pycolmap.html . Used for `exports.py`, documented operating limits and `colmap_backend.py`. Adapter targets the 4.2.x API and uses `extract_features`, `match_image_pairs`, `incremental_mapping` and reconstruction data structures. Package reference: https://pypi.org/project/pycolmap/ .

## Representation and workflow comparison only

**[9] AliceVision / Meshroom contributors.** https://github.com/alicevision/Meshroom . Visual graph and photogrammetry workflow comparison, no code or assets imported.

**[10] OpenMVG contributors.** https://github.com/openMVG/openMVG . Modular multi-view geometry reference, no code imported.

**[11] OpenMVS contributors.** https://github.com/cdcseacave/openMVS . Dense reconstruction/meshing/texture scope and interoperability comparison, no implementation imported.

**[12] Open3D contributors.** https://github.com/isl-org/Open3D . 3D data processing ecosystem and output interoperability reference, not a runtime dependency.

**[13] WebODM contributors.** https://github.com/WebODM/WebODM . Project/processing/output workflow comparison. Current repository rather than obsolete ownership/engine assumptions is used.

**[14] Nerfstudio contributors.** https://github.com/nerfstudio-project/nerfstudio . Neural rendering workflow and deployment comparison. Not a runtime dependency; no training or weights used.

**[15] Jianyuan Wang, Minghao Chen, Nikita Karaev, Andrea Vedaldi, Christian Rupprecht and David Novotny.** “VGGT: Visual Geometry Grounded Transformer.” *CVPR*, 2025. https://github.com/facebookresearch/vggt . Compared as a feed-forward geometry option. Code and checkpoint terms are distinct; no model downloaded.

**[16] Shuzhe Wang, Vincent Leroy, Yohann Cabon, Boris Chidlovskii and Jérôme Revaud.** “DUSt3R: Geometric 3D Vision Made Easy.” *CVPR*, 2024. https://github.com/naver/dust3r . Compared as a point-map approach. No source/checkpoints imported; noncommercial and other upstream conditions are not silently removed.

## Libraries, licensing and publishing

OpenCV license: https://opencv.org/license/ . Pillow license: https://pillow.readthedocs.io/en/stable/about.html#license . NumPy: https://github.com/numpy/numpy . SciPy: https://scipy.org/about/ . filelock: https://github.com/tox-dev/filelock . Exact installed versions/license identifiers are recorded in `THIRD_PARTY_NOTICES.md` and `VALIDATION.md`.

GitHub CLI repository creation interface: https://cli.github.com/manual/gh_repo_create . Referenced by `scripts/publish.py`; it is not a claim that a remote publication occurred. CI interface references: https://github.com/actions/checkout and https://github.com/actions/setup-python .

## Attribution rules for maintenance

When importing a future implementation, retain the original copyright/license header, pin a source revision, state modifications, and update third-party notices. When using a new model, separately review code, checkpoint, training-data and redistribution conditions. When publishing real-data results, cite the exact dataset version/license and capture split. A reference entry alone is not permission to redistribute material.
