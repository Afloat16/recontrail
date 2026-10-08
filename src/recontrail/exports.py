"""Standard PLY/OBJ/COLMAP exports without third-party writer code."""
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.spatial.transform import Rotation
from .geometry import project
from .storage import atomic_json
from .models import ReconError


def write_ply(path: Path, scene):
    if not np.isfinite(scene.points).all():
        raise ReconError("Refusing to export non-finite point coordinates.")
    with path.open("w", encoding="ascii", newline="\n") as out:
        out.write("ply\nformat ascii 1.0\ncomment ReconTrail\n")
        out.write(f"element vertex {len(scene.points)}\n")
        out.write("property double x\nproperty double y\nproperty double z\n")
        out.write("property uchar red\nproperty uchar green\nproperty uchar blue\n")
        if scene.faces is not None:
            out.write(f"element face {len(scene.faces)}\nproperty list uchar int vertex_indices\n")
        out.write("end_header\n")
        for xyz, rgb in zip(scene.points, scene.colors):
            out.write(" ".join(f"{v:.10g}" for v in xyz) + " " + " ".join(str(int(v)) for v in rgb) + "\n")
        if scene.faces is not None:
            for face in scene.faces:
                out.write("3 " + " ".join(str(int(v)) for v in face) + "\n")


def write_obj(path, scene):
    with path.open("w", encoding="ascii", newline="\n") as out:
        out.write("# ReconTrail open surface; vertex colors; no texture atlas or watertight guarantee\n")
        for xyz, rgb in zip(scene.points, scene.colors):
            out.write("v " + " ".join(f"{v:.10g}" for v in xyz) + " " +
                      " ".join(f"{v/255:.6f}" for v in rgb) + "\n")
        for face in scene.faces:
            out.write("f " + " ".join(str(int(v)+1) for v in face) + "\n")


def cameras_json(scene, frames=None):
    cameras = []
    for i, (R, t) in sorted(scene.poses.items()):
        record = {"image_id": i+1, "R": R.tolist(), "t": np.asarray(t).tolist(),
                  "center": (-R.T@t).tolist()}
        if frames:
            record.update(name=frames[i].name, image=f"images/image_{i:05d}.png", K=frames[i].K.tolist())
        cameras.append(record)
    return {"convention": "X_camera = R @ X_world + t; x right, y down, z forward",
            "scale": scene.metrics.get("scale", "arbitrary"), "cameras": cameras}


def write_colmap(root, scene, frames):
    """Text schema: https://colmap.github.io/format.html; IDs are one-based."""
    model = root / "sparse" / "0"
    model.mkdir(parents=True, exist_ok=True)
    image_dir = root / "images"
    image_dir.mkdir(exist_ok=True)
    lookup = {}
    for pid, track in enumerate(scene.observations, 1):
        for image, feature in track.items():
            lookup[(image, feature)] = pid
    with (model / "cameras.txt").open("w", encoding="ascii") as cameras, \
            (model / "images.txt").open("w", encoding="ascii") as images:
        cameras.write("# CAMERA_ID MODEL WIDTH HEIGHT PARAMS[]\n")
        images.write("# IMAGE_ID QW QX QY QZ TX TY TZ CAMERA_ID NAME\n# POINTS2D: X Y POINT3D_ID\n")
        for i, (R, t) in sorted(scene.poses.items()):
            f = frames[i]
            name = f"image_{i:05d}.png"
            Image.fromarray(f.image).save(image_dir / name)
            K = f.K
            h, w = f.image.shape[:2]
            cameras.write(f"{i+1} PINHOLE {w} {h} {K[0,0]:.12g} {K[1,1]:.12g} {K[0,2]:.12g} {K[1,2]:.12g}\n")
            qxyzw = Rotation.from_matrix(R).as_quat()
            quaternion = qxyzw[[3, 0, 1, 2]]
            images.write(f"{i+1} " + " ".join(f"{v:.12g}" for v in np.r_[quaternion, t]) + f" {i+1} {name}\n")
            images.write(" ".join(f"{x:.10g} {y:.10g} {lookup.get((i, k), -1)}"
                                  for k, (x, y) in enumerate(f.points)) + "\n")
    with (model / "points3D.txt").open("w", encoding="ascii") as out:
        out.write("# POINT3D_ID X Y Z R G B ERROR TRACK[]: IMAGE_ID POINT2D_IDX\n")
        for pid, (point, color, track) in enumerate(zip(scene.points, scene.colors, scene.observations), 1):
            residuals = []
            for image, feature in track.items():
                uv, _ = project(point[None], *scene.poses[image], frames[image].K)
                residuals.append(np.linalg.norm(uv[0]-frames[image].points[feature]))
            error = float(np.mean(residuals))
            out.write(f"{pid} " + " ".join(f"{v:.12g}" for v in point) + " " +
                      " ".join(str(int(v)) for v in color) + f" {error:.10g} " +
                      " ".join(f"{image+1} {feature}" for image, feature in sorted(track.items())) + "\n")
    atomic_json(root / "image_mapping.json", {f"image_{i:05d}.png": frames[i].name for i in scene.poses})


def export_scene(root, scene, frames=None):
    write_ply(root / "cloud.ply", scene)
    atomic_json(root / "cameras.json", cameras_json(scene, frames))
    atomic_json(root / "metrics.json", scene.metrics)
    if scene.faces is not None:
        write_obj(root / "mesh.obj", scene)
    elif frames is not None:
        write_colmap(root, scene, frames)
