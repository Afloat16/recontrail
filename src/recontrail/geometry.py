"""Pinhole geometry glue; OpenCV provides calibrated estimation primitives.

Conventions: X_camera = R @ X_world + t; image x right, y down, z forward.
See OpenCV calib3d and the publications listed in docs/references.bib.
"""
import cv2
import numpy as np


def project(points, R, t, K):
    camera = np.asarray(points) @ R.T + np.asarray(t).reshape(1, 3)
    z = camera[:, 2]
    safe_z = np.where(np.abs(z) > 1e-10, z, 1e-10)
    xy = camera[:, :2] / safe_z[:, None]
    uv = xy * [K[0, 0], K[1, 1]] + [K[0, 2], K[1, 2]]
    return uv, z


def triangulate(a, b, pose_a, pose_b, Ka, Kb, max_error=3., min_angle=1.):
    if len(a) == 0:
        return np.empty((0, 3)), np.zeros(0, dtype=bool), np.empty(0)
    Ra, ta = pose_a
    Rb, tb = pose_b
    pa = Ka @ np.column_stack((Ra, np.asarray(ta).reshape(3)))
    pb = Kb @ np.column_stack((Rb, np.asarray(tb).reshape(3)))
    homogeneous = cv2.triangulatePoints(pa, pb, np.asarray(a).T, np.asarray(b).T).T
    divisor = homogeneous[:, 3]
    finite = np.abs(divisor) > 1e-12
    points = homogeneous[:, :3] / np.where(finite, divisor, 1)[:, None]
    ua, za = project(points, Ra, ta, Ka)
    ub, zb = project(points, Rb, tb, Kb)
    ca = -Ra.T @ np.asarray(ta).reshape(3)
    cb = -Rb.T @ np.asarray(tb).reshape(3)
    va, vb = points - ca, points - cb
    cosine = np.sum(va*vb, axis=1) / np.maximum(np.linalg.norm(va, axis=1)*np.linalg.norm(vb, axis=1), 1e-12)
    angles = np.degrees(np.arccos(np.clip(cosine, -1, 1)))
    good = (finite & np.isfinite(points).all(axis=1) & (za > 0) & (zb > 0)
            & (np.linalg.norm(ua-a, axis=1) <= max_error)
            & (np.linalg.norm(ub-b, axis=1) <= max_error) & (angles >= min_angle))
    return points, good, angles


def normalized(points, K):
    return (points - [K[0, 2], K[1, 2]]) / [K[0, 0], K[1, 1]]
