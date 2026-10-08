"""Original incremental orchestration built on OpenCV geometric primitives.

This lightweight backend is a bounded preview backend, not a replacement for
COLMAP's production incremental mapper. Intrinsics stay fixed throughout.
"""
import cv2
import numpy as np
from .geometry import project, triangulate
from .models import ReconError, Scene


def reconstruct(frames, pairs, config, progress=lambda *args: None):
    seeds = [p for p in pairs if p.angle >= config.min_angle_deg and p.homography_ratio < .9]
    if not seeds:
        raise ReconError("No stable non-planar initialization pair. Add translated, overlapping views with depth "
                         "variation; check focus and focal calibration. Pure rotation and flat targets are insufficient.")
    seed = max(seeds, key=lambda p: len(p.matches)*min(p.angle, 12)*(1-p.homography_ratio))
    poses = {seed.i: (np.eye(3), np.zeros(3)), seed.j: (seed.R.copy(), seed.t.copy())}
    landmarks, observations, colors = [], [], []
    lookup = [dict() for _ in frames]

    def add_pair(pair):
        i, j = pair.i, pair.j
        if i not in poses or j not in poses:
            return
        fresh = []
        for u, v in pair.matches:
            u, v = int(u), int(v)
            pid_a, pid_b = lookup[i].get(u), lookup[j].get(v)
            if pid_a is None and pid_b is None:
                fresh.append((u, v))
            elif (pid_a is None) != (pid_b is None):
                target, key, pid = (i, u, pid_b) if pid_a is None else (j, v, pid_a)
                if target in observations[pid]:
                    continue
                predicted, depth = project(np.asarray([landmarks[pid]]), *poses[target], frames[target].K)
                if depth[0] > 0 and np.linalg.norm(predicted[0]-frames[target].points[key]) <= config.reprojection_px:
                    lookup[target][key] = pid
                    observations[pid][target] = key
            # Conflicting tracks are not merged by guesswork.
        if not fresh:
            return
        fresh = np.asarray(fresh)
        xyz, valid, _ = triangulate(frames[i].points[fresh[:, 0]], frames[j].points[fresh[:, 1]],
                                    poses[i], poses[j], frames[i].K, frames[j].K,
                                    config.reprojection_px, config.min_angle_deg)
        for point, (u, v) in zip(xyz[valid], fresh[valid]):
            pid = len(landmarks)
            lookup[i][int(u)] = lookup[j][int(v)] = pid
            landmarks.append(point)
            observations.append({i: int(u), j: int(v)})
            colors.append((frames[i].colors[u].astype(float)+frames[j].colors[v])/2)

    add_pair(seed)
    if len(landmarks) < config.min_matches:
        raise ReconError("Initialization failed the depth/parallax/reprojection checks. Capture wider translated views.")

    def correspondences(target):
        candidates = {}
        for pair in pairs:
            if pair.i == target and pair.j in poses:
                for own, other in pair.matches:
                    pid = lookup[pair.j].get(int(other))
                    if pid is not None:
                        candidates.setdefault(int(own), set()).add(pid)
            elif pair.j == target and pair.i in poses:
                for other, own in pair.matches:
                    pid = lookup[pair.i].get(int(other))
                    if pid is not None:
                        candidates.setdefault(int(own), set()).add(pid)
        items = [(key, next(iter(ids))) for key, ids in sorted(candidates.items()) if len(ids) == 1]
        # solvePnP must not count a single landmark multiple times.
        counts = {}
        for _, pid in items:
            counts[pid] = counts.get(pid, 0) + 1
        return [(key, pid) for key, pid in items if counts[pid] == 1]

    while len(poses) < len(frames):
        choices = [(i, correspondences(i)) for i in range(len(frames)) if i not in poses]
        choices.sort(key=lambda item: (-len(item[1]), item[0]))
        added = False
        for target, items in choices:
            if len(items) < 12:
                continue
            keys, pids = np.asarray(items).T
            object_points = np.asarray(landmarks)[pids].astype(np.float64)
            image_points = frames[target].points[keys].astype(np.float64)
            success, rvec, t, inliers = cv2.solvePnPRansac(
                object_points, image_points, frames[target].K, None,
                iterationsCount=1000, reprojectionError=config.reprojection_px, confidence=.999,
                flags=cv2.SOLVEPNP_EPNP)
            if not success or inliers is None or len(inliers) < 12:
                continue
            use = inliers.ravel()
            rvec, t = cv2.solvePnPRefineLM(object_points[use], image_points[use], frames[target].K, None, rvec, t)
            R = cv2.Rodrigues(rvec)[0]
            predicted, z = project(object_points[use], R, t, frames[target].K)
            good = (z > 0) & (np.linalg.norm(predicted-image_points[use], axis=1) <= config.reprojection_px)
            use = use[good]
            if len(use) < 12:
                continue
            poses[target] = (R, t.reshape(3))
            for at in use:
                key, pid = int(keys[at]), int(pids[at])
                observations[pid][target] = key
                lookup[target][key] = pid
            for pair in sorted(pairs, key=lambda p: -len(p.matches)):
                if target in (pair.i, pair.j):
                    add_pair(pair)
            progress("reconstruct", len(poses)/len(frames), f"Registered {len(poses)}/{len(frames)} cameras")
            added = True
            break
        if not added:
            break
    scene = Scene(np.asarray(landmarks), np.uint8(np.clip(colors, 0, 255)), poses, observations)
    scene.metrics = {"backend": "lite", "seed_images": [seed.i, seed.j],
                     "seed_parallax_deg": seed.angle, "landmarks_before_refinement": len(landmarks),
                     "scale": "arbitrary", "intrinsics_optimized": False}
    if config.bundle_adjust:
        from .refine import bundle_adjust
        progress("refine", 0., "Refining cameras and points")
        scene = bundle_adjust(scene, frames, config)
    return filter_scene(scene, frames, config.reprojection_px)


def filter_scene(scene, frames, max_error):
    errors = np.full(len(scene.points), np.inf)
    good = np.ones(len(scene.points), bool)
    for pid, track in enumerate(scene.observations):
        residuals = []
        for i, key in track.items():
            uv, z = project(scene.points[pid:pid+1], *scene.poses[i], frames[i].K)
            if z[0] <= 0 or not np.isfinite(uv).all():
                good[pid] = False
            residuals.append(float(np.linalg.norm(uv[0]-frames[i].points[key])))
        errors[pid] = max(residuals, default=float("inf"))
    good &= np.isfinite(scene.points).all(axis=1) & (errors <= max_error)
    scene.points = scene.points[good]
    scene.colors = scene.colors[good]
    scene.errors = errors[good]
    scene.observations = [track for track, ok in zip(scene.observations, good) if ok]
    if len(scene.points) < 8:
        raise ReconError("Too few landmarks survive reprojection checks. No valid point cloud was produced.")
    scene.metrics.update({"registered_images": len(scene.poses), "input_images": len(frames),
                          "points": len(scene.points), "reprojection_median_px": float(np.median(scene.errors)),
                          "reprojection_p95_px": float(np.percentile(scene.errors, 95)),
                          "point_error_definition": "maximum observation reprojection error per landmark",
                          "unregistered": [f.name for i, f in enumerate(frames) if i not in scene.poses]})
    return scene
