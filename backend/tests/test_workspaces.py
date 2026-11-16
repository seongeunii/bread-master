"""Space ownership, onboarding, retained records, and legacy catalog migration."""
import io
import json

from PIL import Image
from fastapi.testclient import TestClient
from app import auth, db
from app.main import app
from app.pos import catalog
from test_auth import client, register, HEADERS  # noqa: F401


def post(client, path, data=None, **kwargs):
    return client.post('/api/v1'+path, json=data or {}, headers=HEADERS, **kwargs)


def seed_photographed_menu(client):
    image = io.BytesIO()
    Image.new('RGB',(10,10),'brown').save(image,format='PNG')
    url = client.post('/api/v1/store-admin/photos',content=image.getvalue(),headers=HEADERS).json()['url']
    items = []
    for index in range(4):
        response = post(client,'/store-admin/menu',{'name':f'커피 메뉴 {index}', 'category_id':1,'pos_slot':index,'price':2000,'photo':url})
        response.raise_for_status()
        items = response.json()['products']
    group = post(client,'/store-admin/quiz-groups/save',{'name':'커피','product_ids':[p['id'] for p in items],'status':'approved','enabled':True})
    group.raise_for_status()
    return items, url


def test_personal_space_is_empty_private_idempotent_and_survives_store_join(client):
    user = register(client).json()
    assert client.get('/api/v1/products').status_code == 409
    personal = post(client,'/workspaces/personal').json()
    assert personal['role'] == 'owner' and personal['kind'] == 'personal'
    assert post(client,'/workspaces/personal').json()['id'] == personal['id']
    assert client.get('/api/v1/pos-catalog').json()['products'] == []
    assert client.get('/api/v1/categories').json() == [{'id':1,'name':'기본'}]
    assert client.get('/api/v1/workspaces/readiness').json() == {'photo_count':0,'similar_ready':False}
    items, photo = seed_photographed_menu(client)
    assert client.get('/api/v1/workspaces/readiness').json() == {'photo_count':4,'similar_ready':True}
    assert client.get('/api/v1/store-admin/my-progress').json()['attempts'] == 0
    assert client.get('/api/v1/store-admin/progress').status_code == 403
    assert post(client,'/assessments/start').status_code == 403
    for mode in ('name','similar-photo'):
        question = post(client,'/questions',{'mode':mode}).json()
        with db.connect() as conn:
            snapshot = json.loads(conn.execute('SELECT snapshot FROM store_exercises WHERE id=?',(question['id'],)).fetchone()[0])
        wrong = next(option['id'] for option in question['options'] if option['id'] != snapshot['correct_id'])
        assert post(client,f"/questions/{question['id']}/answer",{'selected_id':wrong,'elapsed_ms':10}).status_code == 200
        assert post(client,f"/store-admin/my-learning/{question['id']}/retry").status_code == 200
    assert post(client,'/inventory-practices').status_code == 200
    assert post(client,'/delivery-orders').status_code == 200
    assert post(client,'/delivery-orders/pos/start').status_code == 200
    official = post(client,'/stores',{'name':'공식 매장'}).json()
    assert client.get('/api/v1/products').json() == []
    assert client.get(photo).status_code == 404
    assert client.get('/api/v1/store-admin/my-progress').json()['attempts'] == 0
    assert post(client,'/store-admin/quiz-groups/save',{'name':'다른 공간 상품','product_ids':[p['id'] for p in items],'status':'approved','enabled':True}).status_code == 422
    assert post(client,'/workspaces/select',{'workspace_id':personal['id']}).status_code == 200
    assert client.get(photo).status_code == 200
    assert client.get('/api/v1/store-admin/my-progress').json()['attempts'] == 2
    assert len(client.get('/api/v1/workspaces').json()['items']) == 2
    # A request issued by an old tab must not edit the newly selected space.
    stale = client.post('/api/v1/store-admin/categories',json={'items':[{'id':1,'name':'오염'}]},headers={**HEADERS,'X-Bread-Workspace':official['id']})
    assert stale.status_code == 409
    assert client.get('/api/v1/categories').json()[0]['name'] == '기본'
    token = client.cookies[auth.COOKIE_NAME]
    client.cookies.clear()
    register(client,email='stranger@example.com')
    assert post(client,'/workspaces/select',{'workspace_id':personal['id']}).status_code == 404
    assert client.get(photo).status_code == 409
    other = post(client,'/workspaces/personal').json()
    assert other['id'] != personal['id']
    assert client.get(photo).status_code == 404
    assert client.get('/api/v1/store-admin/my-learning').json()['attempts'] == []
    client.cookies.clear()
    client.cookies.set(auth.COOKIE_NAME,token)
    assert client.get('/api/v1/auth/session').json()['workspace']['id'] == personal['id']


def test_pending_worker_keeps_personal_space_and_official_results_stay_scoped(client):
    register(client,email='owner@example.com')
    official = post(client,'/stores',{'name':'매장'}).json()
    owner_token = client.cookies[auth.COOKIE_NAME]
    client.cookies.clear()
    worker = register(client,email='worker@example.com').json()
    personal = post(client,'/workspaces/personal').json()
    worker_token = client.cookies[auth.COOKIE_NAME]
    post(client,'/stores/join',{'code':official['invite_code']}).raise_for_status()
    assert client.get('/api/v1/auth/session').json()['workspace']['id'] == personal['id']
    assert post(client,'/workspaces/select',{'workspace_id':official['id']}).status_code == 404
    client.cookies.clear(); client.cookies.set(auth.COOKIE_NAME,owner_token)
    post(client,f"/stores/requests/{worker['id']}/approve").raise_for_status()
    assert client.get('/api/v1/store-admin/progress').json()[0]['attempts'] == 0
    assert post(client,'/workspaces/select',{'workspace_id':personal['id']}).status_code == 404
    client.cookies.clear(); client.cookies.set(auth.COOKIE_NAME,worker_token)
    assert client.get('/api/v1/auth/session').json()['workspace']['id'] == personal['id']
    post(client,'/workspaces/select',{'workspace_id':official['id']}).raise_for_status()
    assert post(client,'/store-admin/menu',{'name':'권한 위반','price':1,'category_id':1,'pos_slot':0}).status_code == 403
    assert client.get('/api/v1/auth/session').json()['store_role'] == 'worker'
    # A separate login restores the last space without changing this session.
    second = TestClient(app)
    post(second,'/auth/login',{'email':'worker@example.com','password':'bread-practice-2026'}).raise_for_status()
    post(second,'/workspaces/select',{'workspace_id':personal['id']}).raise_for_status()
    assert client.get('/api/v1/auth/session').json()['workspace']['id'] == official['id']
    post(client,'/auth/login',{'email':'worker@example.com','password':'bread-practice-2026'}).raise_for_status()
    assert client.get('/api/v1/auth/session').json()['workspace']['id'] == personal['id']
    with db.connect() as conn:
        conn.execute('UPDATE workspace_preferences SET workspace_id=? WHERE user_id=?',(official['id'],worker['id']))
        conn.execute('DELETE FROM store_memberships WHERE user_id=?',(worker['id'],))
    post(client,'/auth/login',{'email':'worker@example.com','password':'bread-practice-2026'}).raise_for_status()
    assert client.get('/api/v1/auth/session').json()['workspace'] is None
    second.close()


def test_legacy_catalog_migration_is_transactional_and_preserves_snapshots(client):
    register(client)
    store = post(client,'/stores',{'name':'이전 매장'}).json()
    with db.connect() as conn:
        conn.execute('DELETE FROM workspace_metadata WHERE store_id=?',(store['id'],))
        conn.execute('DELETE FROM store_categories WHERE store_id=?',(store['id'],))
        # Simulate the pre-space database before restarting.
        before = catalog(conn,store['id'])
    db.initialize()
    with db.connect() as conn:
        after = catalog(conn,store['id'])
        mapped = {p['id']: p for p in after['products']}
        assert len(after['products']) == len(before['products'])
        for original in before['products']:
            assert original.items() <= mapped[original['id']].items()
        assert after['categories'] == before['categories']
        assert conn.execute('PRAGMA foreign_key_check').fetchall() == []
    db.initialize()
    with db.connect() as conn:
        assert catalog(conn,store['id']) == after


def test_migration_failure_rolls_back_catalog_rows(client):
    import sqlite3
    import pytest
    register(client)
    store = post(client,'/stores',{'name':'이전 중 실패'}).json()
    with db.connect() as conn:
        conn.execute('DELETE FROM workspace_metadata WHERE store_id=?',(store['id'],))
        conn.execute('DELETE FROM store_categories WHERE store_id=?',(store['id'],))
        conn.execute("""CREATE TRIGGER reject_workspace BEFORE INSERT ON workspace_metadata
                        BEGIN SELECT RAISE(ABORT, 'simulated failure'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        db.initialize()
    with db.connect() as conn:
        assert conn.execute('SELECT COUNT(*) FROM store_menus WHERE store_id=?',(store['id'],)).fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM workspace_product_metadata WHERE store_id=?',(store['id'],)).fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM store_categories WHERE store_id=?',(store['id'],)).fetchone()[0] == 0
        conn.execute('DROP TRIGGER reject_workspace')
    db.initialize()
    assert client.get('/api/v1/products').json()


def test_small_personal_catalog_completes_round_and_rejects_cross_origin(client):
    register(client)
    space = post(client,'/workspaces/personal').json()
    assert client.post('/api/v1/workspaces/select',json={'workspace_id':space['id']},headers={**HEADERS,'Origin':'https://other.example'}).status_code == 403
    post(client,'/store-admin/menu',{'name':'한 상품','price':2000,'photo':'https://example.com/item.jpg','category_id':1,'pos_slot':0}).raise_for_status()
    excluded = []
    for _ in range(5):
        question = post(client,'/questions',{'mode':'category','exclude_ids':excluded})
        question.raise_for_status()
        assert post(client,f"/questions/{question.json()['id']}/answer",{'selected_id':1,'elapsed_ms':10}).json()['is_correct']
        excluded.append(client.get('/api/v1/products').json()[0]['id'])
    assert client.get('/api/v1/store-admin/my-progress').json()['attempts'] == 5
