import io
import os
from pathlib import Path
import json
import threading
import urllib.request
import urllib.error
import pytest
from recontrail.server import JobStore, WorkbenchServer, MAX_UPLOAD
from recontrail.models import ReconError


@pytest.fixture
def local_server(tmp_path, monkeypatch):
    # pytest adds src to its own sys.path, but subprocess workers need an explicit
    # source path when tests run without an editable install. Installed-wheel
    # smoke tests separately verify ordinary imports without this override.
    source = str(Path(__file__).resolve().parents[1] / "src")
    monkeypatch.setenv("PYTHONPATH", source + os.pathsep + os.environ.get("PYTHONPATH", ""))
    store=JobStore(tmp_path/'jobs')
    server=WorkbenchServer(('127.0.0.1',0),store)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    yield server,store
    server.shutdown();server.server_close();store.close();thread.join(timeout=2)


def request(server, path='/', token=None, method='GET', data=None, extra=None):
    headers={}
    if token:headers['X-ReconTrail-Token']=token
    headers.update(extra or {})
    req=urllib.request.Request(f'http://{server.expected_host}{path}',data=data,method=method,headers=headers)
    try:
        with urllib.request.urlopen(req,timeout=5) as response:
            return response.status,response.read(),response.headers
    except urllib.error.HTTPError as exc:
        return exc.code,exc.read(),exc.headers


def test_http_auth_and_origin(local_server):
    server,store=local_server
    assert request(server)[0]==200
    assert request(server,'/api/jobs')[0]==403
    assert request(server,'/api/jobs',token='wrong')[0]==403
    assert request(server,'/api/jobs',token=store.token)[0]==200
    assert request(server,'/api/jobs',token=store.token,extra={'Origin':'https://evil.example'})[0]==403
    assert request(server,extra={'Host':'evil.example'})[0]==403
    assert request(server,'/../../etc/passwd',token=store.token)[0]==404


def test_http_upload_validation(local_server,capture):
    server,store=local_server
    status,body,headers=request(server,'/api/jobs',token=store.token,method='POST',data=b'{}')
    assert status==200 and headers['X-Content-Type-Options']=='nosniff'
    ident=json.loads(body)['id']
    image=(capture/'images/view_000.png').read_bytes()
    path=f'/api/jobs/{ident}/images?name=photo.png'
    assert request(server,path,token=store.token,method='POST',data=image)[0]==200
    assert request(server,path.replace('photo.png','..%2Fescape.png'),token=store.token,method='POST',data=image)[0]==400
    assert request(server,path,token=store.token,method='POST',data=b'broken')[0]==400
    assert store.status(ident)['images']==1
    assert request(server,f'/api/jobs/{ident}/start',token=store.token,method='POST',data=b'{}')[0]==400
    assert request(server,'/api/jobs',token=store.token,method='POST',data=b'[]')[0]==400


@pytest.mark.parametrize('ident',['../escape','abcd','x'*24,'a'*23+'/', ''])
def test_job_identifiers(tmp_path,ident):
    store=JobStore(tmp_path/'jobs')
    try:
        with pytest.raises(ReconError):store.path(ident)
    finally:store.close()


def test_server_single_workspace_owner(tmp_path):
    store=JobStore(tmp_path/'jobs')
    try:
        with pytest.raises(ReconError):JobStore(tmp_path/'jobs')
    finally:store.close()


def test_partial_upload_is_removed(tmp_path):
    store=JobStore(tmp_path/'jobs')
    try:
        ident=store.create()['id']
        with pytest.raises(ReconError):
            store.upload(ident,'a.png',io.BytesIO(b'123'),500)
        assert not list((store.path(ident)/'input').iterdir())
    finally:store.close()


@pytest.mark.integration
def test_http_worker_reconstruction(local_server,capture):
    import time
    server,store=local_server
    status,body,_=request(server,'/api/jobs',token=store.token,method='POST',data=b'{}')
    ident=json.loads(body)['id']
    for path in sorted((capture/'images').glob('*.png')):
        status,_,_=request(server,f'/api/jobs/{ident}/images?name={path.name}',token=store.token,method='POST',data=path.read_bytes())
        assert status==200
    options={'mode':'run','preset':'quick','intrinsics':json.loads((capture/'intrinsics.json').read_text())}
    assert request(server,f'/api/jobs/{ident}/start',token=store.token,method='POST',data=json.dumps(options).encode())[0]==200
    deadline=time.monotonic()+90
    while time.monotonic()<deadline:
        status,body,_=request(server,f'/api/jobs/{ident}',token=store.token)
        result=json.loads(body)
        if result['state'] in {'complete','failed'}:break
        time.sleep(.1)
    assert result['state']=='complete',result
    assert result['metrics']['registered_images']==8
    status,report,_=request(server,f'/api/jobs/{ident}/files/report.html',token=store.token)
    assert status==200 and b'POINT CLOUD' in report
    assert request(server,f'/api/jobs/{ident}/files/project.json',token=store.token)[0]==400


@pytest.mark.integration
def test_worker_cancel(local_server,capture):
    import time
    server,store=local_server
    ident=store.create()['id']
    for path in sorted((capture/'images').glob('*.png'))[:3]:
        image=path.read_bytes();store.upload(ident,path.name,io.BytesIO(image),len(image))
    store.start(ident,{'mode':'run'})
    store.cancel(ident)
    deadline=time.monotonic()+8
    while store.active is not None and time.monotonic()<deadline:
        time.sleep(.05)
    assert store.status(ident)['state']=='cancelled'
    assert store.process is None
