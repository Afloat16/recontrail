"""Bounded candidate planning, mutual ratio filtering and overlap evidence."""
import itertools
import cv2
import numpy as np
from .geometry import normalized, triangulate
from .models import Pair


def candidate_pairs(frames, config):
    n = len(frames)
    if config.pairing == "all" or (config.pairing == "auto" and n <= 36):
        return list(itertools.combinations(range(n), 2)), "exhaustive"
    pairs = {(i, j) for i in range(n) for j in range(i+1, min(n, i+config.pair_window+1))}
    if config.pairing == "auto":
        # Cheap appearance candidates supplement sequence neighbours. This is not
        # exhaustive retrieval; a disconnected graph is evidence, not a proof.
        vectors = []
        for f in frames:
            small = cv2.resize(f.image, (64, 64))
            hsv = cv2.cvtColor(small, cv2.COLOR_RGB2HSV)
            hist = cv2.calcHist([hsv], [0, 1], None, [12, 8], [0, 180, 0, 256]).ravel()
            vectors.append(hist / max(np.linalg.norm(hist), 1e-9))
        similarity = np.asarray(vectors) @ np.asarray(vectors).T
        for i in range(n):
            for j in np.argsort(-similarity[i], kind="stable")[:7]:
                if i != j:
                    pairs.add(tuple(sorted((i, int(j)))))
    return sorted(pairs), "sequence+appearance" if config.pairing == "auto" else "sequence"


def mutual_matches(first, second, ratio):
    if len(first) < 2 or len(second) < 2:
        return np.empty((0, 2), int)
    # No copied matcher implementation: the descriptor search is OpenCV FLANN.
    matcher = cv2.FlannBasedMatcher(dict(algorithm=1, trees=4), dict(checks=64))
    forward = matcher.knnMatch(first, second, k=2)
    reverse = matcher.knnMatch(second, first, k=2)
    backward = {m.queryIdx: m.trainIdx for row in reverse if len(row) == 2
                for m, other in [row] if m.distance < ratio * other.distance}
    pairs = [(m.queryIdx, m.trainIdx) for row in forward if len(row) == 2
             for m, other in [row] if m.distance < ratio*other.distance
             and backward.get(m.trainIdx) == m.queryIdx]
    return np.asarray(pairs, dtype=int).reshape(-1, 2)


def verify_pair(frames, i, j, config):
    a, b = frames[i], frames[j]
    indices = mutual_matches(a.descriptors, b.descriptors, config.ratio)
    if len(indices) < config.min_matches:
        return None
    pa, pb = a.points[indices[:, 0]], b.points[indices[:, 1]]
    na, nb = normalized(pa, a.K), normalized(pb, b.K)
    threshold = 1.5 / min(a.K[0, 0], a.K[1, 1], b.K[0, 0], b.K[1, 1])
    E, mask = cv2.findEssentialMat(na, nb, np.eye(3), cv2.RANSAC, .999, threshold)
    if E is None or mask is None:
        return None
    best = None
    for essential in np.vsplit(E, E.shape[0]//3):
        count, R, t, valid = cv2.recoverPose(essential, na, nb, np.eye(3), mask=mask.copy())
        if best is None or count > best[0]:
            best = count, R, t.reshape(3), valid.ravel().astype(bool)
    count, R, t, good = best
    if count < config.min_matches:
        return None
    _, geometric, angles = triangulate(pa[good], pb[good], (np.eye(3), np.zeros(3)),
                                        (R, t), a.K, b.K, config.reprojection_px, 0.)
    accepted = indices[good][geometric]
    if len(accepted) < config.min_matches:
        return None
    _, hm = cv2.findHomography(pa, pb, cv2.RANSAC, 3.)
    hr = float(hm.mean()) if hm is not None else 0.
    return Pair(i, j, accepted, R, t, float(np.median(angles[geometric])), hr, len(indices))


def components(n, pairs):
    adjacency = [set() for _ in range(n)]
    for p in pairs:
        adjacency[p.i].add(p.j)
        adjacency[p.j].add(p.i)
    remaining, groups = set(range(n)), []
    while remaining:
        stack, group = [min(remaining)], []
        while stack:
            item = stack.pop()
            if item not in remaining:
                continue
            remaining.remove(item)
            group.append(item)
            stack.extend(sorted(adjacency[item], reverse=True))
        groups.append(sorted(group))
    return sorted(groups, key=lambda g: (-len(g), g[0]))


def match_all(frames, config, progress=lambda *args: None):
    candidates, policy = candidate_pairs(frames, config)
    verified = []
    for k, (i, j) in enumerate(candidates):
        progress("match", k / max(1, len(candidates)), f"Pair {k+1}/{len(candidates)}")
        try:
            pair = verify_pair(frames, i, j, config)
        except cv2.error:
            pair = None
        if pair is not None:
            verified.append(pair)
    groups = components(len(frames), verified)
    audit = {"pair_policy": policy, "tested_pairs": len(candidates), "verified_pairs": len(verified),
             "components": [[frames[i].name for i in group] for group in groups],
             "edges": [{"a": frames[p.i].name, "b": frames[p.j].name,
                        "inliers": len(p.matches), "median_angle_deg": round(p.angle, 3),
                        "homography_ratio": round(p.homography_ratio, 3)} for p in verified],
             "notes": ["Overlap is a geometric heuristic, not a probability of reconstruction success."]}
    if len(groups) > 1:
        audit["notes"].append("Disconnected photo groups: add overlapping views between the listed groups; "
                              "for large unordered collections also try --pairing all.")
    if any(p.homography_ratio > .9 for p in verified):
        audit["notes"].append("Some pairs are homography-dominated: a flat surface, repeated view or camera rotation "
                              "can produce matches without reliable depth. Move around the object.")
    return verified, audit
