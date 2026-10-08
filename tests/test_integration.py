import json
from pathlib import Path
import numpy as np
import pytest
from recontrail.pipeline import run_photos, run_stereo, cache_valid
from recontrail.models import Config, ReconError
from recontrail.storage import read_json
from recontrail.stereo import reconstruct_stereo
from recontrail.video import extract_video


def read_ply_vertices(path):
    with path.open() as f:
        n=0
        for line in f:
            if line.startswith('element vertex '):
                n=int(line.split()[-1])
            if line.strip()=='end_header':
                break
        return np.array([[float(x) for x in next(f).split()[:3]] for _ in range(n)])


@pytest.mark.integration
def test_photos_end_to_end(reconstructed, capture):
    root,metrics,config=reconstructed
    assert metrics['registered_images']==8 and metrics['points']>500
    assert metrics['reprojection_median_px']<.6
    assert metrics['scale']=='arbitrary' and metrics['status']=='complete'
    assert metrics['bundle_adjustment']['cost_after']<metrics['bundle_adjustment']['cost_before']
    assert cache_valid(root)
    cameras=read_json(root/'cameras.json')['cameras']
    truth=read_json(capture/'ground_truth.json')['cameras']
    # Compare using independently known seed baseline, not reported pixel error.
    a,b=metrics['seed_images']
    baseline=np.linalg.norm(np.array(truth[a]['camera_center'])-np.array(truth[b]['camera_center']))
    origin=np.array(truth[a]['camera_center'])
    errors=[]
    for camera in cameras:
        expected=np.array(truth[camera['image_id']-1]['camera_center'])
        recovered=baseline*np.array(camera['center'])+origin
        errors.append(np.linalg.norm(recovered-expected))
        R=np.array(camera['R']);t=np.array(camera['t'])
        assert np.allclose(-R.T@t,camera['center'])
    assert max(errors)<.03
    X=read_ply_vertices(root/'cloud.ply')*baseline+origin
    distance=np.min(np.abs(X[:,2,None]-[7.5,4.6,5.5]),axis=1)
    assert np.median(distance)<.03
    assert np.isfinite(X).all()


@pytest.mark.integration
def test_reuse_and_no_overwrite(reconstructed,capture):
    root,metrics,config=reconstructed
    sha=(root/'cloud.ply').read_bytes()
    with pytest.raises(ReconError):
        run_photos(capture/'images',root,config,read_json(capture/'intrinsics.json'))
    result=run_photos(capture/'images',root,config,read_json(capture/'intrinsics.json'),resume=True)
    assert result['cached'] and (root/'cloud.ply').read_bytes()==sha
    with pytest.raises(ReconError):
        run_photos(capture/'images',root,Config(max_features=1000),read_json(capture/'intrinsics.json'),resume=True)


@pytest.mark.integration
def test_colmap_text_tracks_are_bidirectional(reconstructed):
    root,_,_=reconstructed
    lines=(root/'sparse/0/images.txt').read_text().splitlines()
    data=[line for line in lines if not line.startswith('#')]
    images={}
    for i in range(0,len(data),2):
        header=data[i].split();obs=data[i+1].split()
        assert len(obs)%3==0
        assert (root/'images'/header[9]).is_file()
        assert np.isclose(np.linalg.norm([float(q) for q in header[1:5]]),1)
        images[int(header[0])]=[int(v) for v in obs[2::3]]
    points={}
    for line in (root/'sparse/0/points3D.txt').read_text().splitlines():
        if line.startswith('#'):continue
        values=line.split();ident=int(values[0]);track=[int(x) for x in values[8:]]
        assert len(track)%2==0 and len(track)>=4
        points[ident]=set(zip(track[::2],track[1::2]))
        for image,index in points[ident]:
            assert images[image][index]==ident
    for image,obs in images.items():
        for index,ident in enumerate(obs):
            if ident!=-1:
                assert (image,index) in points[ident]


@pytest.mark.integration
def test_calibrated_dense_stereo(capture,tmp_path):
    root=tmp_path/'dense'
    calib=read_json(capture/'stereo.json')
    metrics=run_stereo(capture/'images/view_000.png',capture/'images/view_001.png',calib,root,max_depth=15)
    assert metrics['scale']=='m' and metrics['points']>10000 and metrics['faces']>10000
    assert metrics['valid_pixel_fraction']>.2
    points=read_ply_vertices(root/'cloud.ply')
    assert np.isfinite(points).all() and (points[:,2]>0).all()
    distance=np.min(np.abs(points[:,2,None]-[4.6,5.5,7.5]),axis=1)
    assert np.median(distance)<.02
    assert (root/'mesh.obj').is_file() and cache_valid(root)


@pytest.mark.integration
def test_reversed_stereo_refuses(capture):
    data=read_json(capture/'stereo.json');data['t']=(-np.array(data['t'])).tolist()
    with pytest.raises(ReconError,match='negative horizontal disparity'):
        reconstruct_stereo(capture/'images/view_001.png',capture/'images/view_000.png',data)


@pytest.mark.integration
def test_failed_scene_leaves_report_and_not_complete(tmp_path):
    from PIL import Image
    source=tmp_path/'input';source.mkdir()
    Image.new('RGB',(640,480),'black').save(source/'a.png')
    Image.new('RGB',(640,480),'white').save(source/'b.png')
    output=tmp_path/'failed'
    with pytest.raises(ReconError):
        run_photos(source,output)
    assert read_json(output/'status.json')['state']=='failed'
    assert (output/'report.html').is_file() and not cache_valid(output)
    checked=run_photos(source,tmp_path/'checked',check_only=True)
    assert checked['status']=='inspected' and checked['points']==0


@pytest.mark.integration
def test_video_sampling(capture,tmp_path):
    import cv2
    source=tmp_path/'clip.avi'
    writer=cv2.VideoWriter(str(source),cv2.VideoWriter_fourcc(*'MJPG'),10,(720,540))
    if not writer.isOpened():
        pytest.skip('MJPG codec unavailable')
    for path in sorted((capture/'images').glob('*.png')):
        image=cv2.imread(str(path))
        for _ in range(3):writer.write(image)
    writer.release()
    result=extract_video(source,tmp_path/'frames',interval=.3,max_frames=8)
    assert 2<=result['frames']<=8
    assert Path(result['manifest']).is_file()


@pytest.mark.optional
def test_optional_colmap_imports_export(reconstructed):
    pc=pytest.importorskip('pycolmap')
    root,metrics,_=reconstructed
    model=pc.Reconstruction(root/'sparse/0')
    assert model.num_reg_images()==metrics['registered_images']
    assert model.num_points3D()==metrics['points']


@pytest.mark.optional
def test_optional_colmap_backend(capture,tmp_path):
    pytest.importorskip('pycolmap')
    result=run_photos(capture/'images',tmp_path/'native',Config(backend='colmap',max_features=2000),read_json(capture/'intrinsics.json'))
    assert result['registered_images']>=6 and result['points']>=200
