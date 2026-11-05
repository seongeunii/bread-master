"""쿠키·서버 세션 경계와 기존 DB 보존을 실제 HTTP 요청으로 확인합니다."""
import hashlib
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from app import db, auth
from app.main import app

HEADERS = {'X-Bread-Client': 'web'}
USER = {'email': 'Learner@example.com', 'password': 'bread-practice-2026', 'display_name': '성은'}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'auth.db')
    for key in ('BREAD_DEMO', 'BREAD_ENV', 'RENDER', 'BREAD_PUBLIC_ORIGIN', 'BREAD_AUTH_COOKIE_SECURE'):
        monkeypatch.delenv(key, raising=False)
    with TestClient(app) as client:
        yield client


def register(client, **changes):
    return client.post('/api/v1/auth/register', json={**USER, **changes}, headers=HEADERS)


def test_register_session_me_and_logout(client):
    assert client.get('/api/v1/auth/session').json() == {'enabled': True, 'user': None, 'store_role': None}
    assert client.get('/api/v1/auth/me').status_code == 401
    response = register(client)
    assert response.status_code == 201
    account = response.json()
    assert account['email'] == 'learner@example.com'
    assert set(account) == {'id', 'email', 'display_name', 'created_at'}
    assert 'password' not in response.text
    assert response.headers['cache-control'] == 'no-store'
    cookie = response.headers['set-cookie'].lower()
    assert 'httponly' in cookie and 'samesite=strict' in cookie and 'max-age=86400' in cookie
    token = client.cookies[auth.COOKIE_NAME]
    with db.connect() as conn:
        row = conn.execute('SELECT * FROM users').fetchone()
        session = conn.execute('SELECT * FROM auth_sessions').fetchone()
        assert row['password_hash'].startswith('$argon2id$')
        assert row['password_hash'] != USER['password']
        assert session['token_hash'] == hashlib.sha256(token.encode()).hexdigest()
        assert session['token_hash'] != token
    assert client.get('/api/v1/auth/me').json() == account
    assert client.get('/api/v1/auth/session').json()['user'] == account
    assert client.post('/api/v1/auth/logout', json={}, headers=HEADERS).status_code == 204
    assert client.get('/api/v1/auth/me').status_code == 401
    client.cookies.set(auth.COOKIE_NAME, token)
    assert client.get('/api/v1/auth/me').status_code == 401


def test_login_rotates_session_and_keeps_credentials_private(client):
    account = register(client).json()
    old = client.cookies[auth.COOKIE_NAME]
    response = client.post('/api/v1/auth/login', json={
        'email': ' LEARNER@example.com ', 'password': USER['password'],
    }, headers=HEADERS)
    assert response.status_code == 200
    assert response.json() == account
    assert 'password' not in response.text and '$argon' not in response.text
    assert client.cookies[auth.COOKIE_NAME] != old
    with db.connect() as conn:
        assert conn.execute('SELECT COUNT(*) FROM auth_sessions').fetchone()[0] == 1
        assert not conn.execute('SELECT 1 FROM auth_sessions WHERE token_hash=?', (auth.digest(old),)).fetchone()


def test_duplicate_case_insensitive_registration_does_not_change_account(client):
    first = register(client).json()
    duplicate = register(client, email='learner@example.com', display_name='다른 이름')
    assert duplicate.status_code == 409
    assert client.get('/api/v1/auth/me').json() == first
    with db.connect() as conn:
        assert conn.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 1


@pytest.mark.parametrize('change', [
    {'email': 'wrong-email'}, {'password': 'short'}, {'password': 'p' * 129},
    {'display_name': '  '}, {'display_name': '이름\n줄바꿈'}, {'display_name': '이' * 31},
    {'role': 'admin'}, {'store_id': 'other-store'},
])
def test_validation_and_role_injection_are_rejected_without_password_echo(client, change):
    response = register(client, **change)
    assert response.status_code == 422
    assert USER['password'] not in response.text
    assert client.get('/api/v1/auth/session').json()['user'] is None
    with db.connect() as conn:
        assert conn.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0


def test_unknown_account_and_wrong_password_have_same_error(client):
    register(client)
    results = [client.post('/api/v1/auth/login', json={'email': email, 'password': 'incorrect-password'}, headers=HEADERS)
               for email in ('learner@example.com', 'unknown@example.com')]
    assert [r.status_code for r in results] == [401, 401]
    assert results[0].json() == results[1].json()


@pytest.mark.parametrize('path', ['register', 'login', 'logout'])
def test_csrf_missing_header_and_foreign_origin_blocked(client, path):
    payload = USER if path == 'register' else {'email': USER['email'], 'password': USER['password']} if path == 'login' else {}
    assert client.post('/api/v1/auth/' + path, json=payload).status_code == 403
    assert client.post('/api/v1/auth/' + path, json=payload,
                       headers={**HEADERS, 'Origin': 'https://attacker.example'}).status_code == 403
    assert client.post('/api/v1/auth/' + path, json=payload,
                       headers={**HEADERS, 'Sec-Fetch-Site': 'cross-site'}).status_code == 403
    with db.connect() as conn:
        assert conn.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0


def test_same_origin_and_secure_cookie(client):
    with TestClient(app, base_url='https://testserver') as secure:
        response = secure.post('/api/v1/auth/register', json=USER,
                               headers={**HEADERS, 'Origin': 'https://testserver'})
        assert response.status_code == 201
        assert '; secure' in response.headers['set-cookie'].lower()
        assert secure.get('/api/v1/auth/me').status_code == 200


def test_expired_tampered_and_missing_sessions(client):
    register(client)
    token = client.cookies[auth.COOKIE_NAME]
    with db.connect() as conn:
        conn.execute('UPDATE auth_sessions SET expires_at=?', (int(time.time()) - 1,))
    assert client.get('/api/v1/auth/me').status_code == 401
    assert client.get('/api/v1/auth/session').json()['user'] is None
    client.cookies.clear()
    client.cookies.set(auth.COOKIE_NAME, 'tampered-' + token)
    assert client.get('/api/v1/auth/me').status_code == 401
    assert client.post('/api/v1/auth/logout', json={}, headers=HEADERS).status_code == 204


def test_accounts_and_sessions_survive_restart_without_touching_learning_data(client):
    account = register(client).json()
    token = client.cookies[auth.COOKIE_NAME]
    question = client.post('/api/v1/questions', json={'mode': 'name'}).json()
    db.initialize()
    with TestClient(app) as restarted:
        restarted.cookies.set(auth.COOKIE_NAME, token)
        assert restarted.get('/api/v1/auth/me').json() == account
        response = restarted.post('/api/v1/auth/login', json={'email': USER['email'], 'password': USER['password']}, headers=HEADERS)
        assert response.status_code == 200
    with db.connect() as conn:
        assert conn.execute('SELECT 1 FROM questions WHERE id=?', (question['id'],)).fetchone()
        assert conn.execute('SELECT COUNT(*) FROM products').fetchone()[0] == 12


def test_two_browser_sessions_do_not_expose_each_others_accounts(client):
    first = register(client).json()
    with TestClient(app) as other:
        assert other.get('/api/v1/auth/me').status_code == 401
        second = register(other, email='second@example.com', display_name='두 번째').json()
        assert second['id'] != first['id']
        assert other.get('/api/v1/auth/me').json() == second
        assert client.get('/api/v1/auth/me').json() == first
        assert client.post('/api/v1/auth/logout', json={}, headers=HEADERS).status_code == 204
        assert other.get('/api/v1/auth/me').json() == second


def test_login_attempt_limit_survives_initialize_and_expires(client):
    for _ in range(10):
        assert client.post('/api/v1/auth/login', json={'email': 'unknown@example.com', 'password': 'wrong'}, headers=HEADERS).status_code == 401
    db.initialize()
    limited = client.post('/api/v1/auth/login', json={'email': 'unknown@example.com', 'password': 'wrong'}, headers=HEADERS)
    assert limited.status_code == 429 and int(limited.headers['retry-after']) > 0
    with db.connect() as conn:
        conn.execute('UPDATE auth_attempts SET expires_at=?', (int(time.time()) - 1,))
    assert client.post('/api/v1/auth/login', json={'email': 'unknown@example.com', 'password': 'wrong'}, headers=HEADERS).status_code == 401


def test_demo_cannot_collect_credentials(client, monkeypatch):
    monkeypatch.setenv('BREAD_DEMO', '1')
    assert client.get('/api/v1/auth/session').json() == {'enabled': False, 'user': None, 'store_role': None}
    assert register(client).status_code == 503
    assert client.post('/api/v1/auth/login', json={'email': USER['email'], 'password': USER['password']}, headers=HEADERS).status_code == 503
    assert client.get('/api/v1/auth/me').status_code == 503
    with db.connect() as conn:
        assert conn.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0
    assert client.get('/api/v1/products').status_code == 200


def test_production_requires_secure_origin_and_persistent_database(client, monkeypatch):
    monkeypatch.setenv('BREAD_ENV', 'production')
    with pytest.raises(RuntimeError, match='HTTPS'):
        auth.validate_configuration()
    monkeypatch.setenv('BREAD_PUBLIC_ORIGIN', 'https://bread.example')
    with pytest.raises(RuntimeError, match='COOKIE_SECURE'):
        auth.validate_configuration()
    monkeypatch.setenv('BREAD_AUTH_COOKIE_SECURE', '1')
    monkeypatch.setenv('BREAD_DATA_PERSISTENT', '1')
    monkeypatch.setenv('BREAD_DB_PATH', str(db.DB_PATH))
    with pytest.raises(RuntimeError, match='영속'):
        auth.validate_configuration()
    monkeypatch.setattr(db, 'DB_PATH', Path('/data/bread-master/account.db'))
    monkeypatch.setenv('BREAD_DB_PATH', str(db.DB_PATH))
    auth.validate_configuration()
    monkeypatch.setenv('BREAD_DEMO', '1')
    monkeypatch.delenv('BREAD_PUBLIC_ORIGIN')
    auth.validate_configuration()


def test_store_approval_is_limited_to_own_store(client):
    stores = '/api/v1/stores'
    assert client.get(stores + '/mine').status_code == 401
    register(client, email='owner@example.com')
    owner_cookie = client.cookies[auth.COOKIE_NAME]
    owner = client.post(stores, json={'name': '연습 매장'}, headers=HEADERS)
    assert owner.status_code == 201
    code = owner.json()['invite_code']
    assert client.get('/api/v1/auth/session').json()['store_role'] == 'admin'
    assert client.post(stores, json={'name': '중복 매장'}, headers=HEADERS).status_code == 409

    client.cookies.clear()
    worker = register(client, email='worker@example.com').json()
    worker_cookie = client.cookies[auth.COOKIE_NAME]
    pending = client.post(stores + '/join', json={'code': code.upper()}, headers=HEADERS)
    assert pending.status_code == 201
    assert pending.json()['status'] == 'pending'
    assert client.get('/api/v1/auth/session').json()['store_role'] is None
    assert 'invite_code' not in pending.json()
    assert client.post(stores + '/join', json={'code': code}, headers=HEADERS).status_code == 409
    approve = f"{stores}/requests/{worker['id']}/approve"
    assert client.post(approve, json={}, headers=HEADERS).status_code == 403

    client.cookies.clear()
    register(client, email='other-owner@example.com')
    assert client.post(stores, json={'name': '다른 매장'}, headers=HEADERS).status_code == 201
    assert client.post(approve, json={}, headers=HEADERS).status_code == 404
    assert client.get(stores + '/mine').json()['requests'] == []

    client.cookies.clear()
    client.cookies.set(auth.COOKIE_NAME, owner_cookie)
    assert client.get(stores + '/mine').json()['requests'][0]['user_id'] == worker['id']
    assert client.post(approve, json={}).status_code == 403
    assert client.post(approve, json={}, headers=HEADERS).status_code == 204
    assert client.post(approve, json={}, headers=HEADERS).status_code == 404

    client.cookies.clear()
    client.cookies.set(auth.COOKIE_NAME, worker_cookie)
    assert client.get(stores + '/mine').json()['status'] == 'active'
    assert client.get('/api/v1/auth/session').json()['store_role'] == 'worker'
    assert client.post(stores + '/cancel', json={}, headers=HEADERS).status_code == 204
    assert client.get(stores + '/mine').json()['role'] == 'worker'


def test_store_menus_and_progress_respect_membership_and_keep_original_grade(client):
    api = '/api/v1'

    def post(path, body):
        return client.post(api + path, json=body, headers=HEADERS)

    def get(path):
        return client.get(api + path)

    def switch(token):
        client.cookies.clear()
        client.cookies.set(auth.COOKIE_NAME, token)

    register(client, email='menu-owner@example.com')
    owner_token = client.cookies[auth.COOKIE_NAME]
    invite = post('/stores', {'name': '메뉴 매장'}).json()['invite_code']
    menu = {'name': '테스트 메뉴', 'category_id': 1, 'pos_slot': 19, 'price': 2200,
            'photo': 'https://example.com/bread.jpg'}
    response = post('/store-admin/menu', menu)
    assert response.status_code == 200
    item = next(p for p in response.json()['products'] if p['name'] == menu['name'])
    assert post('/store-admin/menu', menu).status_code == 409

    client.cookies.clear()
    worker = register(client, email='menu-worker@example.com').json()
    worker_token = client.cookies[auth.COOKIE_NAME]
    assert post('/stores/join', {'code': invite}).status_code == 201
    assert not any(p['id'] == item['id'] for p in get('/products').json())
    assert get('/store-admin/my-progress').status_code == 403
    switch(owner_token)
    assert post(f"/stores/requests/{worker['id']}/approve", {}).status_code == 204

    switch(worker_token)
    assert post('/store-admin/menu', menu).status_code == 403
    assert get('/store-admin/progress').status_code == 403
    assert any(p['id'] == item['id'] for p in get('/pos-catalog').json()['products'])
    excluded = [p['id'] for p in get('/products').json() if p['id'] != item['id']]
    question = post('/questions', {'mode': 'category', 'exclude_ids': excluded}).json()
    answer = f"/questions/{question['id']}/answer"

    switch(owner_token)
    assert post(answer, {'selected_id': 1, 'elapsed_ms': 200}).status_code == 404
    assert post('/store-admin/menu', {**menu, 'product_id': item['id'], 'name': '바뀐 메뉴', 'category_id': 2}).status_code == 200
    assert get('/store-admin/progress').json()[0]['attempts'] == 0

    switch(worker_token)
    result = post(answer, {'selected_id': 1, 'elapsed_ms': 200}).json()
    assert result['is_correct'] and result['correct_product']['name'] == '테스트 메뉴'
    assert post(answer, {'selected_id': 1, 'elapsed_ms': 800}).json() == result
    assert get('/store-admin/my-progress').json()['attempts'] == 1

    switch(owner_token)
    row = get('/store-admin/progress').json()[0]
    assert (row['attempts'], row['accuracy'], row['level']) == (1, 100, 1)
    assert row['latest']
    client.cookies.clear()
    register(client, email='menu-other@example.com')
    assert post('/stores', {'name': '다른 매장'}).status_code == 201
    assert get('/store-admin/progress').json() == []
    assert get(f"/products/{item['id']}").status_code == 404


def test_store_categories_and_uploaded_photos_are_scoped(client):
    import io
    from PIL import Image

    register(client, email='photo-owner@example.com')
    owner_token = client.cookies[auth.COOKIE_NAME]
    client.post('/api/v1/stores', json={'name': '사진 매장'}, headers=HEADERS)
    layout = client.get('/api/v1/store-admin/menu').json()
    categories = layout['categories']
    changed = [{**category, 'name': '새 분류명' if index == 0 else category['name']} for index, category in enumerate(categories)]
    response = client.post('/api/v1/store-admin/categories', json={'items': list(reversed(changed)) + [{'name': '신메뉴'}]}, headers=HEADERS)
    assert response.status_code == 200
    saved_categories = response.json()['categories']
    new_category = saved_categories[-1]
    assert client.post('/api/v1/store-admin/categories', json={'items': [new_category]}, headers=HEADERS).status_code == 409
    assert client.get('/api/v1/categories').json() == saved_categories

    image = io.BytesIO()
    Image.new('RGB', (1600, 1000), 'brown').save(image, format='PNG')
    upload = client.post('/api/v1/store-admin/photos', content=image.getvalue(), headers=HEADERS)
    assert upload.status_code == 201
    url = upload.json()['url']
    photo = client.get(url)
    assert photo.status_code == 200 and photo.headers['content-type'] == 'image/jpeg'
    normalized = Image.open(io.BytesIO(photo.content))
    assert normalized.size == (1200, 750) and not normalized.getexif()
    assert client.post('/api/v1/store-admin/photos', content=b'<svg/>', headers=HEADERS).status_code == 422
    assert client.post('/api/v1/store-admin/photos', content=b'x' * (5 * 1024 * 1024 + 1), headers=HEADERS).status_code == 413
    menu = {'name': '업로드 상품', 'category_id': new_category['id'], 'pos_slot': 0, 'price': 2000, 'photo': url}
    assert client.post('/api/v1/store-admin/menu', json=menu, headers=HEADERS).status_code == 200
    assert client.post('/api/v1/store-admin/categories', json={'items': saved_categories[:-1]}, headers=HEADERS).status_code == 409

    client.cookies.clear()
    register(client, email='photo-other@example.com')
    client.post('/api/v1/stores', json={'name': '다른 사진 매장'}, headers=HEADERS)
    assert client.get(url).status_code == 404
    assert client.post('/api/v1/store-admin/menu', json={**menu, 'category_id': categories[0]['id'], 'pos_slot': 24}, headers=HEADERS).status_code == 422
    assert not any(c['name'] == '신메뉴' for c in client.get('/api/v1/categories').json())

    client.cookies.clear()
    client.cookies.set(auth.COOKIE_NAME, owner_token)
    base_product = client.get('/api/v1/products').json()[0]
    assert client.post('/api/v1/store-admin/menu', json={
        'product_id': base_product['id'], 'category_id': base_product['category_id'],
        'pos_slot': base_product['pos_slot'], 'name': base_product['name'],
        'price': base_product['price'], 'photo': url,
    }, headers=HEADERS).status_code == 200


def test_file_import_preview_and_atomic_retry(client):
    import io
    import uuid
    from openpyxl import Workbook

    register(client, email='import-owner@example.com')
    client.post('/api/v1/stores', json={'name': '등록 매장'}, headers=HEADERS)
    headers = ['상품명', '가격', '카테고리', '칸번호', '사진주소']
    workbook = Workbook()
    workbook.active.append(headers)
    workbook.active.append(['등록 빵', 1900, '페이스트리', 24, ''])
    data = io.BytesIO()
    workbook.save(data)
    preview = client.post('/api/v1/store-admin/import/preview', content=data.getvalue(), headers=HEADERS)
    assert preview.status_code == 200
    assert preview.json()['rows'][0]['상품명'] == '등록 빵'
    csv = '상품명,가격,카테고리,칸번호,사진주소\n등록 빵,1900,페이스트리,24,\n'
    assert client.post('/api/v1/store-admin/import/preview', content=csv.encode('utf-8-sig'), headers=HEADERS).status_code == 200
    assert client.post('/api/v1/store-admin/import/preview', content=b'bad', headers=HEADERS).status_code == 422

    item = {'name': '등록 빵', 'price': 1900, 'category_id': 1, 'pos_slot': 23}
    path = '/api/v1/store-admin/import/save'
    before = len(client.get('/api/v1/products').json())
    payload = {'request_id': str(uuid.uuid4()), 'items': [item, {**item, 'name': '중복 칸'}]}
    assert client.post(path, json=payload, headers=HEADERS).status_code == 409
    assert len(client.get('/api/v1/products').json()) == before
    payload['items'] = [item]
    assert client.post(path, json=payload, headers=HEADERS).status_code == 200
    assert client.post(path, json=payload, headers=HEADERS).status_code == 200
    assert len(client.get('/api/v1/products').json()) == before + 1
    payload['items'] = [{**item, 'name': '변경 요청'}]
    assert client.post(path, json=payload, headers=HEADERS).status_code == 409


@pytest.mark.parametrize('url', [
    'http://www.paris.co.kr/product/bread/', 'https://localhost/product/bread/',
    'https://www.paris.co.kr.evil.test/product/bread/', 'https://user@www.paris.co.kr/product/bread/',
    'https://www.paris.co.kr:444/product/bread/', 'https://www.paris.co.kr/products/',
    'https://www.paris.co.kr/product/../secret', 'https://www.paris.co.kr/product/bread/?redirect=localhost',
    'https://[', 'https://www.paris.co.kr/product/%2fsecret/',
])
def test_product_link_rejects_unsupported_destinations(url):
    from app.store_link import supported_url
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        supported_url(url)
    assert error.value.status_code == 422


def test_product_link_preview_requires_admin_and_leaves_prices_for_confirmation(client, monkeypatch):
    from app import store_link
    url = 'https://www.paris.co.kr/product/bread/'
    html = '<meta property="og:image" content="https://example.com/bread.jpg"><h1 class="product-name">빵 &amp; 버터</h1>'
    result = store_link.parse_product(html, url)
    assert result == {'name': '빵 & 버터', 'photo': 'https://example.com/bread.jpg', 'source_url': url}
    async def fetch(_):
        return result
    monkeypatch.setattr(store_link, 'fetch_product', fetch)
    path = '/api/v1/store-admin/import/link'
    assert client.post(path, json={'url': url}, headers=HEADERS).status_code == 403
    register(client, email='link-owner@example.com')
    client.post('/api/v1/stores', json={'name': '링크 매장'}, headers=HEADERS)
    before = len(client.get('/api/v1/products').json())
    response = client.post(path, json={'url': url}, headers=HEADERS)
    assert response.status_code == 200 and response.json() == result
    assert len(client.get('/api/v1/products').json()) == before
    saved = client.post('/api/v1/store-admin/menu', json={
        'name': result['name'], 'photo': result['photo'], 'source_url': result['source_url'],
        'price': 1900, 'category_id': 1, 'pos_slot': 24,
    }, headers=HEADERS)
    assert saved.status_code == 200
    assert next(item for item in saved.json()['products'] if item['name'] == result['name'])['source_url'] == url
