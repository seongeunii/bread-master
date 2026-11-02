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
    assert client.get('/api/v1/auth/session').json() == {'enabled': True, 'user': None}
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
    assert client.get('/api/v1/auth/session').json() == {'enabled': False, 'user': None}
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
