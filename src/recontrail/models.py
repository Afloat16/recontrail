"""Small, explicit data contracts shared by reconstruction backends."""
from dataclasses import asdict, dataclass, field
from typing import Any
import math
import numpy as np


class ReconError(RuntimeError):
    """Actionable input, reconstruction or workspace error."""


@dataclass(frozen=True)
class Config:
    max_size: int = 1400
    max_features: int = 4000
    max_images: int = 160
    pair_window: int = 8
    pairing: str = "auto"
    ratio: float = 0.75
    min_matches: int = 20
    reprojection_px: float = 3.0
    min_angle_deg: float = 1.0
    focal_ratio: float = 1.2
    bundle_adjust: bool = True
    ba_points: int = 2500
    ba_evaluations: int = 25
    backend: str = "lite"
    seed: int = 7

    def __post_init__(self):
        for name, lo, hi in [
            ("max_size", 320, 4096), ("max_features", 300, 16000),
            ("max_images", 2, 1000), ("pair_window", 1, 50),
            ("min_matches", 8, 1000), ("ba_points", 20, 20000),
            ("ba_evaluations", 1, 200), ("seed", 0, 2**31 - 1),
        ]:
            val = getattr(self, name)
            if isinstance(val, bool) or not isinstance(val, int) or not lo <= val <= hi:
                raise ReconError(f"{name} must be an integer in [{lo}, {hi}].")
        for name, lo, hi in [("ratio", .4, .95), ("reprojection_px", .2, 15),
                              ("min_angle_deg", .1, 15), ("focal_ratio", .2, 5)]:
            val = getattr(self, name)
            if not isinstance(val, (int, float)) or not math.isfinite(val) or not lo <= val <= hi:
                raise ReconError(f"{name} must be finite and in [{lo}, {hi}].")
        if not isinstance(self.bundle_adjust, bool):
            raise ReconError("bundle_adjust must be a boolean.")
        if self.backend not in {"lite", "colmap"} or self.pairing not in {"auto", "all", "sequence"}:
            raise ReconError("Invalid backend or pairing policy.")

    def to_dict(self):
        return asdict(self)


@dataclass
class Frame:
    name: str
    image: np.ndarray  # RGB, oriented, optionally undistorted, resized
    K: np.ndarray
    points: np.ndarray
    descriptors: np.ndarray
    colors: np.ndarray
    audit: dict[str, Any]


@dataclass
class Pair:
    i: int
    j: int
    matches: np.ndarray  # feature indices; unique in both views
    R: np.ndarray  # camera i -> camera j
    t: np.ndarray
    angle: float
    homography_ratio: float
    raw_matches: int


@dataclass
class Scene:
    points: np.ndarray
    colors: np.ndarray
    poses: dict[int, tuple[np.ndarray, np.ndarray]]
    observations: list[dict[int, int]] = field(default_factory=list)
    errors: np.ndarray = field(default_factory=lambda: np.empty(0))
    metrics: dict[str, Any] = field(default_factory=dict)
    faces: np.ndarray | None = None
