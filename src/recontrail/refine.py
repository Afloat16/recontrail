"""Sparse robust bundle adjustment with an explicit seven-DOF gauge.

The first seed camera is fixed; one baseline length fixes scale. Other camera
poses and selected landmarks are refined with SciPy's sparse least_squares.
Intrinsics are fixed. This is not an uncertainty/calibration estimator.
"""
import cv2
import numpy as np
from scipy.optimize import least_squares
from scipy.sparse import lil_matrix
from scipy.spatial.transform import Rotation
from .models import Scene


def bundle_adjust(scene, frames, config):
    chosen = sorted(range(len(scene.points)), key=lambda p: (-len(scene.observations[p]), p))[:config.ba_points]
    points = scene.points[chosen].copy()
    tracks = [scene.observations[p] for p in chosen]
    fixed, scale_camera = scene.metrics["seed_images"]
    variable = [i for i in sorted(scene.poses) if i != fixed]
    camera_index = {image: index for index, image in enumerate(variable)}
    camera_params = np.array([np.r_[cv2.Rodrigues(scene.poses[i][0])[0].ravel(), scene.poses[i][1]]
                              for i in variable])
    obs_camera, obs_point, pixels, intrinsics = [], [], [], []
    for point_id, track in enumerate(tracks):
        for image_id, feature_id in sorted(track.items()):
            obs_camera.append(camera_index.get(image_id, len(variable)))
            obs_point.append(point_id)
            pixels.append(frames[image_id].points[feature_id])
            K = frames[image_id].K
            intrinsics.append([K[0, 0], K[1, 1], K[0, 2], K[1, 2]])
    obs_camera, obs_point = np.asarray(obs_camera), np.asarray(obs_point)
    pixels, intrinsics = np.asarray(pixels), np.asarray(intrinsics)
    offset = 6 * len(variable)
    scale_index = camera_index[scale_camera]
    baseline = np.linalg.norm(scene.poses[scale_camera][1])
    fixed_R, fixed_t = scene.poses[fixed]

    def unpack(parameters):
        cp = parameters[:offset].reshape(-1, 6)
        rotations = np.concatenate((Rotation.from_rotvec(cp[:, :3]).as_matrix(), fixed_R[None]), axis=0)
        translations = np.vstack((cp[:, 3:], fixed_t))
        return rotations, translations, parameters[offset:].reshape(-1, 3)

    def residual(parameters):
        rotations, translations, xyz = unpack(parameters)
        camera_xyz = np.einsum("nij,nj->ni", rotations[obs_camera], xyz[obs_point]) + translations[obs_camera]
        z = np.where(np.abs(camera_xyz[:, 2]) > 1e-8, camera_xyz[:, 2], 1e-8)
        projected = camera_xyz[:, :2] / z[:, None] * intrinsics[:, :2] + intrinsics[:, 2:]
        scale_residual = 100. * (np.linalg.norm(translations[scale_index]) - baseline)
        return np.r_[(projected - pixels).ravel(), scale_residual]

    sparsity = lil_matrix((2*len(pixels)+1, offset+3*len(points)), dtype=int)
    for k, (camera, point) in enumerate(zip(obs_camera, obs_point)):
        if camera < len(variable):
            sparsity[2*k:2*k+2, 6*camera:6*camera+6] = 1
        sparsity[2*k:2*k+2, offset+3*point:offset+3*point+3] = 1
    sparsity[-1, 6*scale_index+3:6*scale_index+6] = 1
    initial = np.r_[camera_params.ravel(), points.ravel()]
    before = residual(initial)
    result = least_squares(residual, initial, jac_sparsity=sparsity.tocsr(), method="trf",
                           loss="soft_l1", f_scale=1., x_scale="jac", max_nfev=config.ba_evaluations,
                           ftol=1e-5, xtol=1e-5)
    after = residual(result.x)
    robust_cost = lambda r: float(np.sum(np.sqrt(1+r*r)-1))
    accepted = np.isfinite(result.x).all() and robust_cost(after) <= robust_cost(before)
    metrics = dict(scene.metrics)
    metrics["bundle_adjustment"] = {"accepted": bool(accepted), "converged": bool(result.success),
                                    "evaluations": result.nfev, "point_budget": config.ba_points,
                                    "cost_before": robust_cost(before), "cost_after": robust_cost(after),
                                    "gauge": "first camera fixed; one baseline length fixed by residual",
                                    "termination": str(result.message)}
    if not accepted:
        scene.metrics = metrics
        return scene
    rotations, translations, points = unpack(result.x)
    poses = dict(scene.poses)
    for i, image in enumerate(variable):
        poses[image] = rotations[i], translations[i]
    return Scene(points, scene.colors[chosen], poses, tracks, metrics=metrics)
