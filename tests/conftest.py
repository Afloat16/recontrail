from pathlib import Path
import pytest
from recontrail.demo import make_demo
from recontrail.models import Config
from recontrail.pipeline import run_photos
from recontrail.storage import read_json


@pytest.fixture(scope="session")
def capture(tmp_path_factory):
    root = tmp_path_factory.mktemp("rendered-capture")
    make_demo(root, count=8)
    return root


@pytest.fixture(scope="session")
def reconstructed(capture, tmp_path_factory):
    root = tmp_path_factory.mktemp("reconstruction-parent")/"result"
    config = Config(max_features=2000, ba_points=1200, ba_evaluations=15)
    result = run_photos(capture/"images", root, config, read_json(capture/"intrinsics.json"))
    return root, result, config
