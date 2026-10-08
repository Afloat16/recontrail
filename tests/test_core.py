import io
import json
from pathlib import Path
import shutil
import numpy as np
import pytest
from PIL import Image
from filelock import FileLock
from recontrail.models import Config, ReconError, Scene
from recontrail.geometry import project, triangulate
from recontrail.images import discover, prepare, read_rgb, camera_matrix
from recontrail.storage import workspace, atomic_json, digest, fingerprint, read_json
from recontrail.pipeline import cache_valid
from recontrail.report import safe_json, render_report
from recontrail.exports import write_ply, write_obj
from recontrail.stereo import grid_faces, validate_calibration
from recontrail.matching import candidate_pairs, components
from recontrail.cli import main


@pytest.mark.parametrize("field,value", [("max_size",0),("max_features",True),("max_images",1),
    ("ratio",float('nan')),("reprojection_px",float('inf')),("pairing","unknown"),
    ("backend","shell"),("bundle_adjust","false"),("seed",-1),("ba_points",1)])
def test_config_rejects_invalid(field, value):
    with pytest.raises(ReconError):
        Config(**{field:value})


def test_json_atomic_and_finite(tmp_path):
    target = tmp_path/"a.json"
    atomic_json(target, {"name":"测试"})
    before = target.read_bytes()
    with pytest.raises(ValueError):
        atomic_json(target, {"bad":float('nan')})
    assert target.read_bytes() == before
    assert not list(tmp_path.glob('.rt-*'))


def test_fingerprint_reads_content_not_mtime(tmp_path):
    p = tmp_path/"a.png"
    p.write_bytes(b"first")
    a = fingerprint([p], {})
    p.write_bytes(b"other")
    assert fingerprint([p], {}) != a


def test_protect_unrelated_directory(tmp_path):
    (tmp_path/"keep.txt").write_text("keep")
    with pytest.raises(ReconError), workspace(tmp_path, "sig"):
        pass
    assert (tmp_path/"keep.txt").read_text() == "keep"


def test_workspace_signature_and_lock(tmp_path):
    target = tmp_path/"out"
    with workspace(target, "a"):
        with pytest.raises(ReconError), workspace(target, "a", True):
            pass
    with pytest.raises(ReconError), workspace(target, "b", True):
        pass
    with workspace(target, "a", True):
        pass


@pytest.mark.parametrize('manifest',[[],{},['report.html'],{'../escape':'bad'}])
def test_cache_bad_manifest(tmp_path, manifest):
    atomic_json(tmp_path/"complete.json",manifest)
    assert not cache_valid(tmp_path)


def test_cache_detects_corruption(tmp_path):
    for name in ("report.html","metrics.json"):
        (tmp_path/name).write_text("example")
    atomic_json(tmp_path/"complete.json",{n:digest(tmp_path/n) for n in ("report.html","metrics.json")})
    assert cache_valid(tmp_path)
    (tmp_path/"report.html").write_text("tampered")
    assert not cache_valid(tmp_path)


def test_report_script_injection_is_escaped(tmp_path):
    attack = '</script><script>alert("x")</script> & <img src=x>'
    encoded = safe_json({"name":attack})
    assert '<' not in encoded and '&' not in encoded
    assert json.loads(encoded)["name"] == attack
    render_report(tmp_path/"report.html", {"notes":[attack],"images":[]})
    content = (tmp_path/"report.html").read_text()
    assert attack not in content
    assert 'src="https:' not in content
    assert 'fetch(' not in content


def test_orientation_and_decode_limit(tmp_path):
    p = tmp_path/"oriented.jpg"
    image = Image.new("RGB", (120,80), (130,80,60))
    exif = Image.Exif(); exif[274] = 6
    image.save(p, exif=exif)
    rgb,_ = read_rgb(p)
    assert rgb.shape == (120,80,3)


def test_duplicate_and_corrupt_images(tmp_path, capture):
    a = capture/"images"/"view_000.png"
    b = capture/"images"/"view_001.png"
    shutil.copy(a,tmp_path/"first.png"); shutil.copy(a,tmp_path/"copy.png")
    shutil.copy(b,tmp_path/"second.png"); (tmp_path/"broken.png").write_bytes(b"not an image")
    frames,rejected = prepare(discover(tmp_path,160),Config(max_features=500))
    assert len(frames)==2 and len(rejected)==2
    assert len({f.audit['pixel_sha256'] for f in frames})==2


def test_blank_flags(tmp_path):
    Image.new("RGB",(640,480),'black').save(tmp_path/"black.png")
    Image.new("RGB",(640,480),'white').save(tmp_path/"white.png")
    frames,_ = prepare(discover(tmp_path,160),Config())
    flags = {flag for f in frames for flag in f.audit['flags']}
    assert {'mostly_dark','mostly_bright','limited_texture','soft_image'} <= flags


def test_symlink_input_rejected(tmp_path, capture):
    if not hasattr(Path, "symlink_to"):
        pytest.skip("No symlink support")
    try:
        (tmp_path/"link.png").symlink_to(capture/"images"/"view_000.png")
        (tmp_path/"other.png").symlink_to(capture/"images"/"view_001.png")
    except OSError:
        pytest.skip("Symlink permissions unavailable")
    with pytest.raises(ReconError):
        discover(tmp_path,160)


def test_triangulation_known_geometry():
    rng=np.random.default_rng(42)
    points=rng.uniform([-1,-1,4],[1,1,8],(100,3))
    K=np.array([[700.,0,320],[0,700,240],[0,0,1]])
    a,b=(np.eye(3),np.zeros(3)),(np.eye(3),np.array([-1.,0,0]))
    x,_=project(points,*a,K);y,_=project(points,*b,K)
    result,valid,angles=triangulate(x,y,a,b,K,K,1.,1.)
    assert valid.all() and (angles>1).all()
    assert np.allclose(result,points,atol=1e-8)


def test_grid_faces_do_not_bridge_holes_or_depth_edges():
    valid=np.ones((3,3),bool);xyz=np.zeros((3,3,3));xyz[:,:,2]=5
    assert len(grid_faces(valid,xyz,1))==8
    valid[1,1]=False
    assert len(grid_faces(valid,xyz,1))==0
    valid[:]=True;xyz[:,1:,2]=10
    assert len(grid_faces(valid,xyz,1))==4


@pytest.mark.parametrize('change',[{'t':[0,0,0]},{'unit':'inch'},{'R':[[1,0,0],[0,2,0],[0,0,1]]},
    {'image_size':[1,1]},{'distortion_left':[0,0]},{'t':[0,1,0]}])
def test_bad_stereo_calibration(capture,change):
    data=read_json(capture/'stereo.json');data.update(change)
    with pytest.raises(ReconError):
        validate_calibration(data,(720,540))


def test_ply_and_obj_indices(tmp_path):
    scene=Scene(np.array([[0.,0,1],[1,0,1],[0,1,1]]),np.array([[255,0,0],[0,255,0],[0,0,255]]),{},faces=np.array([[0,1,2]]))
    write_ply(tmp_path/'mesh.ply',scene);write_obj(tmp_path/'mesh.obj',scene)
    assert (tmp_path/'mesh.ply').read_text().endswith('3 0 1 2\n')
    assert (tmp_path/'mesh.obj').read_text().endswith('f 1 2 3\n')
    scene.points[0,0]=float('nan')
    with pytest.raises(ReconError):
        write_ply(tmp_path/'bad.ply',scene)


def test_cli_doctor_and_bad_input(capsys,tmp_path):
    assert main(['doctor'])==0
    assert json.loads(capsys.readouterr().out)['default_backend']=='lite-cpu'
    assert main(['run',str(tmp_path/'missing'),'-o',str(tmp_path/'out')])==2
