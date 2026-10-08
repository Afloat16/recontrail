"""Calibrated CPU stereo: rectification, bidirectional SGBM and surface patches.

OpenCV supplies SGBM and rectification. Original validation, validity masks and
export orchestration are here. The mesh is an open sampled surface, not a
watertight/textured asset. Baseline units come only from the supplied calibration.
"""
import cv2
import numpy as np
from .images import read_rgb
from .models import ReconError, Scene


def validate_calibration(data, size):
    try:
        Kl = np.asarray(data["K_left"], dtype=float)
        Kr = np.asarray(data["K_right"], dtype=float)
        R = np.asarray(data["R"], dtype=float)
        t = np.asarray(data["t"], dtype=float).reshape(3)
        dims = tuple(data["image_size"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ReconError("Stereo calibration needs image_size, K_left, K_right, R and t.") from exc
    if dims != size:
        raise ReconError("Stereo calibration image_size must match both EXIF-oriented input images.")
    for K in (Kl, Kr):
        if K.shape != (3, 3) or not np.isfinite(K).all() or K[0, 0] <= 0 or K[1, 1] <= 0:
            raise ReconError("Invalid stereo camera matrix.")
        if not np.allclose(K[2], [0, 0, 1]) or abs(K[0, 1]) > 1e-9 or abs(K[1, 0]) > 1e-9:
            raise ReconError("Stereo intrinsics must be standard zero-skew pinhole matrices.")
        if not (0 <= K[0, 2] < size[0] and 0 <= K[1, 2] < size[1]):
            raise ReconError("Stereo principal point must lie inside the image.")
    if R.shape != (3, 3) or not np.isfinite(R).all() or not np.allclose(R.T@R, np.eye(3), atol=1e-5):
        raise ReconError("R must be an orthonormal 3x3 rotation.")
    if abs(np.linalg.det(R)-1) > 1e-5 or not np.isfinite(t).all() or np.linalg.norm(t) < 1e-8:
        raise ReconError("Stereo baseline must be nonzero and R must have determinant +1.")
    if data.get("unit") not in {"m", "cm", "mm", "arbitrary"}:
        raise ReconError("Specify calibration unit: m, cm, mm or arbitrary.")
    if abs(t[0]) < abs(t[1]):
        raise ReconError("Vertical stereo is not supported by this horizontal-SGBM backend.")
    distortions = []
    for key in ("distortion_left", "distortion_right"):
        d = np.asarray(data.get(key, [0]*5), dtype=float)
        if d.ndim != 1 or len(d) not in (4, 5, 8, 12, 14) or not np.isfinite(d).all():
            raise ReconError(f"Invalid {key} coefficients.")
        distortions.append(d)
    return Kl, Kr, R, t, *distortions


def grid_faces(valid, xyz, step=2, relative_jump=.04):
    """Triangulate only 2x2 sampled cells with four valid, depth-consistent corners."""
    sampled = valid[::step, ::step]
    shape = sampled.shape
    lookup = np.full(shape, -1, dtype=np.int64)
    lookup[sampled] = np.arange(np.count_nonzero(sampled))
    z = np.where(sampled, xyz[::step, ::step, 2], 0.)
    corners = np.stack([z[:-1, :-1], z[:-1, 1:], z[1:, :-1], z[1:, 1:]])
    good = (sampled[:-1, :-1] & sampled[:-1, 1:] & sampled[1:, :-1] & sampled[1:, 1:]
            & (np.max(corners, axis=0)-np.min(corners, axis=0)
               < relative_jump*np.maximum(np.min(corners, axis=0), 1e-8)))
    a, b = lookup[:-1, :-1][good], lookup[:-1, 1:][good]
    c, d = lookup[1:, :-1][good], lookup[1:, 1:][good]
    return np.vstack((np.column_stack((a, c, b)), np.column_stack((b, c, d))))


def reconstruct_stereo(left_path, right_path, calibration, max_depth=100., stride=2, progress=lambda *args: None):
    if (not np.isfinite(max_depth) or max_depth <= 0 or isinstance(stride, bool)
            or not isinstance(stride, int) or not 1 <= stride <= 16):
        raise ReconError("max_depth must be positive and finite; stride must be between 1 and 16.")
    left, _ = read_rgb(left_path)
    right, _ = read_rgb(right_path)
    if left.shape != right.shape:
        raise ReconError("Stereo images must have identical dimensions.")
    h, w = left.shape[:2]
    if max(w, h) > 2560:
        raise ReconError("Stereo images exceed 2560 pixels. Resize images and scale both camera matrices first.")
    if w < 128 or h < 64:
        raise ReconError("Stereo images are too small; use at least 128x64 pixels.")
    Kl, Kr, R, t, dl, dr = validate_calibration(calibration, (w, h))
    # Rectified disparity is positive when camera 2 is to camera 1's right.
    R1, R2, P1, P2, Q, roi1, roi2 = cv2.stereoRectify(Kl, dl, Kr, dr, (w, h), R, t,
                                                      flags=cv2.CALIB_ZERO_DISPARITY, alpha=0)
    if P2[0, 3] >= 0:
        raise ReconError("Calibration gives negative horizontal disparity. Swap left/right and transform R,t.")
    progress("rectify", .1, "Rectifying calibrated stereo")
    mx1, my1 = cv2.initUndistortRectifyMap(Kl, dl, R1, P1, (w, h), cv2.CV_32FC1)
    mx2, my2 = cv2.initUndistortRectifyMap(Kr, dr, R2, P2, (w, h), cv2.CV_32FC1)
    a = cv2.remap(left, mx1, my1, cv2.INTER_LINEAR)
    b = cv2.remap(right, mx2, my2, cv2.INTER_LINEAR)
    gray_a, gray_b = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY), cv2.cvtColor(b, cv2.COLOR_RGB2GRAY)
    disparities = min(256, max(16, (w//4//16)*16))
    args = dict(numDisparities=disparities, blockSize=5, P1=8*25, P2=32*25,
                uniquenessRatio=10, speckleWindowSize=80, speckleRange=2,
                disp12MaxDiff=1, mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY)
    progress("stereo", .3, "Computing bidirectional stereo disparity")
    disparity = cv2.StereoSGBM_create(minDisparity=0, **args).compute(gray_a, gray_b).astype(float)/16
    reverse = cv2.StereoSGBM_create(minDisparity=-disparities, **args).compute(gray_b, gray_a).astype(float)/16
    yy, xx = np.indices((h, w))
    xr = np.rint(xx-disparity).astype(int)
    in_bounds = (xr >= 0) & (xr < w)
    xr_safe = np.clip(xr, 0, w-1)
    back = reverse[yy, xr_safe]
    consistent = np.abs(disparity+back) <= 1.
    xyz_rect = cv2.reprojectImageTo3D(disparity.astype(np.float32), Q)
    valid = (in_bounds & consistent & (disparity > .5) & (back > -disparities-1)
             & (back < -.5) & np.isfinite(xyz_rect).all(axis=2)
             & (xyz_rect[:, :, 2] > 0) & (xyz_rect[:, :, 2] < max_depth))
    valid_left = (mx1 >= 1) & (mx1 < w-2) & (my1 >= 1) & (my1 < h-2)
    valid_right = (mx2 >= 1) & (mx2 < w-2) & (my2 >= 1) & (my2 < h-2)
    valid &= valid_left & valid_right[yy, xr_safe]
    sampled = valid[::stride, ::stride]
    xyz = (np.where(np.isfinite(xyz_rect), xyz_rect, 0.).reshape(-1, 3) @ R1).reshape(h, w, 3)
    # Index ordering is the same boolean row-major ordering used by grid_faces.
    points, colors = xyz[::stride, ::stride][sampled], a[::stride, ::stride][sampled]
    if len(points) < 30:
        raise ReconError("Too few consistent disparities. Verify synchronization, calibration, order and texture.")
    faces = grid_faces(valid, xyz_rect, stride)
    metrics = {"backend": "stereo-sgbm", "points": len(points), "faces": len(faces),
               "registered_images": 2, "input_images": 2, "scale": calibration["unit"],
               "valid_pixel_fraction": float(valid.mean()), "left_right_threshold_px": 1.,
               "max_depth": max_depth, "stride": stride, "baseline": float(np.linalg.norm(t)),
               "depth_median": float(np.median(points[:, 2])),
               "surface_type": "open grid surface; no watertightness or metric-accuracy guarantee"}
    return Scene(points, colors, {0: (np.eye(3), np.zeros(3)), 1: (R, t)}, metrics=metrics, faces=faces)
