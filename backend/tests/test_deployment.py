from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from app import db
from app.main import app
from app import web, demo

def test_static_web_and_api_boundaries(tmp_path, monkeypatch):
    directory=tmp_path/'web'
    directory.mkdir()
    (directory/'assets').mkdir()
    (directory/'assets/app.js').write_text('const demo = true')
    (directory/'index.html').write_text('<html>Bread Master</html>')
    (directory/'favicon.svg').write_text('<svg/>')
    outside=tmp_path/'secret.txt'
    outside.write_text('private')
    (directory/'link.txt').symlink_to(outside)
    monkeypatch.setenv('BREAD_STATIC_DIR',str(directory))
    test_app=FastAPI()
    web.install(test_app)
    client=TestClient(test_app)
    assert 'Bread Master' in client.get('/').text
    assert 'Bread Master' in client.get('/practice').text
    assert client.get('/assets/app.js').status_code==200
    assert client.get('/favicon.svg').status_code==200
    assert client.get('/api/v1/missing').status_code==404
    assert client.get('/missing.js').status_code==404
    assert client.get('/link.txt').status_code==404

def test_demo_starts_with_official_catalog_and_preserves_saved_practice(tmp_path,monkeypatch):
    monkeypatch.setattr(db,'DB_PATH',tmp_path/'demo.db')
    monkeypatch.setenv('BREAD_DEMO','1')
    monkeypatch.setenv('BREAD_DB_PATH',str(tmp_path/'demo.db'))
    with TestClient(app) as client:
        assert client.get('/api/v1/health').json()['data']=='demo'
        assert len(client.get('/api/v1/products').json())==176
        practice=client.post('/api/v1/inventory-practices',json={}).json()
        assert practice['id']
        assert client.get('/api/v1/categories').json()[0]['name']=='휴면반죽단과자'
    with TestClient(app) as client:
        assert client.get(f"/api/v1/inventory-practices/{practice['id']}").status_code==200
        assert len(client.get('/api/v1/products').json())==176

def test_demo_requires_explicit_database(monkeypatch):
    monkeypatch.delenv('BREAD_DB_PATH',raising=False)
    with pytest.raises(RuntimeError,match='BREAD_DB_PATH'):
        demo.prepare()

def test_demo_rate_limit(tmp_path,monkeypatch):
    monkeypatch.setattr(db,'DB_PATH',tmp_path/'demo.db')
    db.initialize()
    monkeypatch.setenv('BREAD_DEMO','1')
    test_app=FastAPI()
    demo.install_limits(test_app,limit=2)
    @test_app.post('/api/test')
    def post():
        return {'ok':True}
    client=TestClient(test_app)
    assert client.post('/api/test').status_code==200
    assert client.post('/api/test').status_code==200
    assert client.post('/api/test').status_code==429
    assert client.get('/api/test').status_code==405
