"""Optional PyCOLMAP 4.2 adapter; no COLMAP source is vendored.

Uses the documented Python API. This adapter requires a separate optional
installation and is explicitly marked unverified where PyCOLMAP is unavailable.
"""
import importlib
import tempfile
from pathlib import Path
import numpy as np
from PIL import Image
from .models import ReconError, Scene
from .matching import candidate_pairs
from .sfm import filter_scene


def reconstruct_colmap(frames, config, root, progress=lambda *args: None):
    try:
        pc = importlib.import_module("pycolmap")
    except ImportError as exc:
        raise ReconError('COLMAP backend is not installed. Run: python -m pip install ".[colmap]"') from exc
    version = getattr(pc, "__version__", "")
    if not version.startswith("4.2."):
        raise ReconError(f"This adapter targets PyCOLMAP 4.2.x; found {version}. Install the colmap extra.")
    backend_dir = root / "backend"
    backend_dir.mkdir(exist_ok=True)
    # Every retry has a fresh database, never stale partially updated backend state.
    work = Path(tempfile.mkdtemp(prefix="colmap-", dir=backend_dir))
    images = work / "images"
    images.mkdir()
    db = work / "database.db"
    names = []
    for i, frame in enumerate(frames):
        name = f"image_{i:05d}.png"
        names.append(name)
        Image.fromarray(frame.image).save(images / name)
        K = frame.K
        progress("colmap-features", i/len(frames), f"COLMAP features {i+1}/{len(frames)}")
        pc.extract_features(db, images, image_names=[name], camera_mode=pc.CameraMode.PER_IMAGE,
                            reader_options={"camera_model": "PINHOLE", "camera_params":
                                            ",".join(str(v) for v in [K[0,0], K[1,1], K[0,2], K[1,2]])},
                            extraction_options={"num_threads": 2, "max_image_size": config.max_size,
                                                "sift": {"max_num_features": config.max_features}},
                            device=pc.Device.cpu)
    candidates, _ = candidate_pairs(frames, config)
    pair_path = work / "pairs.txt"
    pair_path.write_text("".join(f"{names[i]} {names[j]}\n" for i, j in candidates), encoding="ascii")
    progress("colmap-match", 0., "COLMAP matching candidate pairs")
    pc.match_image_pairs(db, pairing_options={"match_list_path": str(pair_path)},
                         matching_options={"num_threads": 2}, device=pc.Device.cpu)
    maps = work / "models"
    maps.mkdir()
    progress("colmap-map", 0., "COLMAP incremental mapping")
    calibrated = all(f.audit["intrinsics"] == "calibrated" for f in frames)
    reconstructions = pc.incremental_mapping(db, images, maps, options={
        "num_threads": 2, "min_model_size": 3, "random_seed": config.seed,
        "ba_refine_focal_length": not calibrated, "ba_refine_principal_point": False,
        "ba_refine_extra_params": False})
    if not reconstructions:
        raise ReconError("COLMAP could not initialize a reconstruction. Inspect report.html for input diagnostics.")
    reconstruction = max(reconstructions.values(), key=lambda r: (r.num_reg_images(), r.num_points3D()))
    indices = {name: i for i, name in enumerate(names)}
    id_to_index, poses = {}, {}
    for image_id in reconstruction.reg_image_ids():
        image = reconstruction.images[image_id]
        i = indices[image.name]
        id_to_index[image_id] = i
        pose = image.cam_from_world()
        poses[i] = pose.rotation.matrix(), np.array(pose.translation)
        frames[i].K = reconstruction.cameras[image.camera_id].calibration_matrix()
        frames[i].points = np.asarray([p.xy for p in image.points2D])
    points, colors, tracks = [], [], []
    for _, point in sorted(reconstruction.points3D.items()):
        track = {id_to_index[e.image_id]: e.point2D_idx for e in point.track.elements
                 if e.image_id in id_to_index}
        if len(track) >= 2:
            points.append(point.xyz)
            colors.append(point.color)
            tracks.append(track)
    scene = Scene(np.asarray(points), np.asarray(colors, dtype=np.uint8), poses, tracks)
    scene.metrics = {"backend": "colmap", "backend_version": version, "scale": "arbitrary",
                     "models_found": len(reconstructions), "intrinsics_optimized": not calibrated,
                     "selection": "largest model by registered camera count, then point count"}
    return filter_scene(scene, frames, config.reprojection_px)
