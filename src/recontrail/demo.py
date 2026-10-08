"""Deterministic multi-depth synthetic capture; no third-party images or weights.

Images are rendered from explicit planar surfaces at different depths. The
reconstructor receives only images and (optionally) intrinsics, never true poses.
"""
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
from .geometry import project
from .storage import atomic_json
from .models import ReconError


def make_demo(output: Path, count=8, width=720, height=540, seed=19):
    if not 2 <= count <= 40:
        raise ReconError("Demo view count must be between 2 and 40.")
    if output.exists() and any(output.iterdir()):
        raise ReconError("Demo output must be empty; no existing files will be overwritten.")
    images = output / "images"
    images.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    K = np.array([[780.*width/720, 0, width/2], [0, 780.*width/720, height/2], [0, 0, 1.]])
    planes = [(-3.2, -2.5, 3.2, 2.5, 7.5), (-1.65, -.85, -.25, 1.1, 4.6),
              (.2, -1.05, 1.65, .85, 5.5)]
    textures = []
    for index in range(len(planes)):
        texture = rng.integers(45, 210, (700, 850, 3), dtype=np.uint8)
        texture = cv2.GaussianBlur(texture, (5, 5), .9)
        for _ in range(1000):
            x, y = rng.integers([0, 0], [850, 700])
            color = tuple(int(v) for v in rng.integers(20, 240, 3))
            cv2.circle(texture, (int(x), int(y)), int(rng.integers(2, 12)), color, -1)
        for _ in range(80):
            x, y = rng.integers([0, 0], [800, 650])
            cv2.rectangle(texture, (int(x), int(y)), (int(x+35), int(y+25)), (230, 230, 230), 2)
        textures.append(texture)
    source = np.float32([[0, 0], [849, 0], [849, 699], [0, 699]])
    truth = []
    for i, x in enumerate(np.linspace(-.8, .8, count)):
        center = np.array([x, .08*np.sin(i*.8), 0.])
        R, t = np.eye(3), -center
        image = np.full((height, width, 3), 25, np.uint8)
        for (x0, y0, x1, y1, z), texture in zip(planes, textures):
            corners = np.array([[x0, y0, z], [x1, y0, z], [x1, y1, z], [x0, y1, z]])
            pixel, _ = project(corners, R, t, K)
            H = cv2.getPerspectiveTransform(source, pixel.astype(np.float32))
            warped = cv2.warpPerspective(texture, H, (width, height), flags=cv2.INTER_LINEAR)
            mask = cv2.warpPerspective(np.full(texture.shape[:2], 255, np.uint8), H, (width, height))
            image[mask > 250] = warped[mask > 250]
        name = f"view_{i:03d}.png"
        Image.fromarray(image).save(images / name)
        truth.append({"name": name, "camera_center": center.tolist(), "R": R.tolist(), "t": t.tolist()})
    atomic_json(output / "intrinsics.json", {"width": width, "height": height, "fx": K[0, 0],
                                           "fy": K[1, 1], "cx": K[0, 2], "cy": K[1, 2]})
    atomic_json(output / "ground_truth.json", {"kind": "synthetic-test-only", "seed": seed,
                                              "surfaces": planes, "cameras": truth,
                                              "note": "This file is never read by reconstruction."})
    # The two image cameras may have a small vertical baseline as well.
    atomic_json(output / "stereo.json", {"image_size": [width, height], "K_left": K.tolist(),
                                         "K_right": K.tolist(), "R": np.eye(3).tolist(),
                                         "t": (np.asarray(truth[1]["t"])-np.asarray(truth[0]["t"])).tolist(),
                                         "unit": "m"})
    return images
