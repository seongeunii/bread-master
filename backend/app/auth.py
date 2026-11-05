"""이메일 계정과 서버 세션. 역할·매장 소속은 후속 기능에서 연결합니다.

쿠키에는 무작위 토큰만, DB에는 토큰의 SHA-256 해시만 저장합니다.
공개 임시 데모에서는 계정 API를 닫아 개인정보를 수집하지 않습니다.
"""
import hashlib
import os
import secrets
import sqlite3
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from pwdlib import PasswordHash

from .db import connect

COOKIE_NAME = 'bread_session'
SESSION_SECONDS = 24 * 60 * 60
passwords = PasswordHash.recommended()
# 존재하지 않는 계정도 비밀번호 검증 비용을 지불합니다.
DUMMY_HASH = passwords.hash(secrets.token_urlsafe(32))
router = APIRouter(prefix='/api/v1/auth', tags=['Account'])


def enabled():
    return os.environ.get('BREAD_DEMO') != '1'


def validate_configuration():
    """운영 계정을 임시 파일시스템에서 무심코 활성화하지 않도록 시작 시 검사."""
    if not enabled() or not (os.environ.get('RENDER') == 'true' or os.environ.get('BREAD_ENV') == 'production'):
        return
    from . import db
    origin = urlsplit(os.environ.get('BREAD_PUBLIC_ORIGIN', ''))
    if (origin.scheme != 'https' or not origin.netloc or origin.path not in ('', '/')
            or origin.query or origin.fragment or origin.username or origin.password):
        raise RuntimeError('계정 운영에는 HTTPS BREAD_PUBLIC_ORIGIN 설정이 필요합니다.')
    if os.environ.get('BREAD_AUTH_COOKIE_SECURE') != '1':
        raise RuntimeError('계정 운영에는 BREAD_AUTH_COOKIE_SECURE=1이 필요합니다.')
    path = Path(db.DB_PATH).resolve()
    temporary_roots = {Path('/tmp').resolve(), Path('/var/tmp').resolve(), Path(tempfile.gettempdir()).resolve()}
    temporary = any(path == p or p in path.parents for p in temporary_roots)
    if os.environ.get('BREAD_DATA_PERSISTENT') != '1' or temporary or not os.environ.get('BREAD_DB_PATH'):
        raise RuntimeError('계정 운영에는 영속 저장소의 BREAD_DB_PATH와 BREAD_DATA_PERSISTENT=1이 필요합니다.')


def require_enabled():
    if not enabled():
        raise HTTPException(503, '체험용 데모에서는 회원가입과 로그인을 제공하지 않습니다.')


def protect_write(request: Request):
    require_enabled()
    # 일반 폼은 이 헤더를 보낼 수 없고, 타 출처 JS는 CORS 사전 요청을 통과할 수 없습니다.
    # 인증 API에 임의의 출처를 허용하는 CORS 설정을 추가하지 않습니다.
    if request.headers.get('X-Bread-Client') != 'web':
        raise HTTPException(403, '앱에서 다시 요청해 주세요.')
    if request.headers.get('sec-fetch-site') == 'cross-site':
        raise HTTPException(403, '다른 사이트에서 보낸 요청은 허용하지 않습니다.')
    origin = request.headers.get('origin')
    expected = os.environ.get('BREAD_PUBLIC_ORIGIN', str(request.base_url)).rstrip('/')
    if origin is not None and origin != expected:
        raise HTTPException(403, '다른 사이트에서 보낸 요청은 허용하지 않습니다.')


def digest(value: str):
    return hashlib.sha256(value.encode()).hexdigest()


def limit_attempt(scope: str, identity: str, limit: int, window: int = 900):
    """DB 기반 단일 인스턴스 제한. 재시작으로 시도 횟수가 초기화되지 않습니다."""
    now = int(time.time())
    key = digest(f'{scope}:{identity}')
    with connect() as db:
        db.execute('DELETE FROM auth_attempts WHERE expires_at <= ?', (now,))
        db.execute('''INSERT INTO auth_attempts(key_hash, attempts, expires_at) VALUES (?,1,?)
                      ON CONFLICT(key_hash) DO UPDATE SET attempts=attempts+1''', (key, now + window))
        row = db.execute('SELECT attempts, expires_at FROM auth_attempts WHERE key_hash=?', (key,)).fetchone()
    if row['attempts'] > limit:
        raise HTTPException(429, '시도가 많아요. 잠시 후 다시 시도해 주세요.',
                            headers={'Retry-After': str(max(1, row['expires_at'] - now))})


class Credentials(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator('email', mode='before')
    @classmethod
    def normalize_email(cls, value):
        return value.strip().casefold() if isinstance(value, str) else value


class Registration(Credentials):
    password: str = Field(min_length=10, max_length=128)
    display_name: str = Field(min_length=1, max_length=30)

    @field_validator('display_name')
    @classmethod
    def clean_name(cls, value):
        value = value.strip()
        if not value or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError('표시 이름을 확인해 주세요.')
        return value


class Account(BaseModel):
    id: str
    email: str
    display_name: str
    created_at: str


class SessionStatus(BaseModel):
    enabled: bool
    user: Optional[Account]
    store_role: Optional[str] = None


def find_account(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    if not enabled() or not token or len(token) > 128:
        return None
    with connect() as db:
        return db.execute('''SELECT u.id,u.email,u.display_name,u.created_at FROM users u
                             JOIN auth_sessions s ON s.user_id=u.id
                             WHERE s.token_hash=? AND s.expires_at>?''',
                          (digest(token), int(time.time()))).fetchone()


def require_account(request: Request):
    require_enabled()
    account = find_account(request)
    if account is None:
        raise HTTPException(401, '로그인이 필요합니다.')
    return dict(account)


def start_session(db, request: Request, response: Response, user_id: str):
    old = request.cookies.get(COOKIE_NAME)
    if old and len(old) <= 128:
        db.execute('DELETE FROM auth_sessions WHERE token_hash=?', (digest(old),))
    now = int(time.time())
    db.execute('DELETE FROM auth_sessions WHERE expires_at<=?', (now,))
    token = secrets.token_urlsafe(32)
    db.execute('INSERT INTO auth_sessions VALUES (?,?,?)', (digest(token), user_id, now + SESSION_SECONDS))
    secure = os.environ.get('BREAD_AUTH_COOKIE_SECURE') == '1' or request.url.scheme == 'https'
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_SECONDS,
                        expires=datetime.fromtimestamp(now + SESSION_SECONDS, timezone.utc),
                        httponly=True, secure=secure, samesite='strict', path='/')


@router.get('/session', response_model=SessionStatus)
def session(request: Request):
    account = find_account(request)
    role = None
    if account:
        with connect() as db:
            member = db.execute("SELECT role FROM store_memberships WHERE user_id=? AND status='active'", (account['id'],)).fetchone()
            role = member['role'] if member else None
    return {'enabled': enabled(), 'user': dict(account) if account else None, 'store_role': role}


@router.get('/me', response_model=Account)
def me(account=Depends(require_account)):
    return account


@router.post('/register', response_model=Account, status_code=201, dependencies=[Depends(protect_write)])
def register(body: Registration, request: Request, response: Response):
    limit_attempt('register-ip', request.client.host if request.client else 'unknown', 10)
    user_id = str(uuid.uuid4())
    password_hash = passwords.hash(body.password)
    try:
        with connect() as db:
            db.execute('INSERT INTO users(id,email,display_name,password_hash) VALUES (?,?,?,?)',
                       (user_id, str(body.email).casefold(), body.display_name, password_hash))
            start_session(db, request, response, user_id)
            account = db.execute('SELECT id,email,display_name,created_at FROM users WHERE id=?', (user_id,)).fetchone()
    except sqlite3.IntegrityError:
        raise HTTPException(409, '이미 가입된 이메일입니다. 로그인해 주세요.')
    return dict(account)


@router.post('/login', response_model=Account, dependencies=[Depends(protect_write)])
def login(body: Credentials, request: Request, response: Response):
    limit_attempt('login-ip', request.client.host if request.client else 'unknown', 30)
    limit_attempt('login-email', str(body.email).casefold(), 10)
    with connect() as db:
        row = db.execute('SELECT * FROM users WHERE email=?', (str(body.email).casefold(),)).fetchone()
    if not passwords.verify(body.password, row['password_hash'] if row else DUMMY_HASH) or row is None:
        raise HTTPException(401, '이메일 또는 비밀번호를 확인해 주세요.')
    with connect() as db:
        start_session(db, request, response, row['id'])
    return dict(row)


@router.post('/logout', status_code=204, dependencies=[Depends(protect_write)])
def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE_NAME)
    if token and len(token) <= 128:
        with connect() as db:
            db.execute('DELETE FROM auth_sessions WHERE token_hash=?', (digest(token),))
    response.delete_cookie(COOKIE_NAME, path='/', httponly=True, samesite='strict',
                           secure=os.environ.get('BREAD_AUTH_COOKIE_SECURE') == '1' or request.url.scheme == 'https')


def install(app):
    app.include_router(router)

    @app.exception_handler(RequestValidationError)
    async def safe_validation(request, exc):
        if request.url.path.startswith('/api/v1/auth/'):
            from starlette.responses import JSONResponse
            # Pydantic 기본 오류의 input 필드에 비밀번호가 들어가지 않게 합니다.
            return JSONResponse({'detail': '입력 내용을 확인해 주세요. 이메일 형식, 이름 1~30자, 가입 비밀번호 10~128자가 필요합니다.'}, status_code=422)
        return await request_validation_exception_handler(request, exc)

    @app.middleware('http')
    async def auth_headers(request, call_next):
        response = await call_next(request)
        if request.url.path.startswith('/api/v1/'):
            response.headers['Cache-Control'] = 'no-store'
            response.headers['X-Content-Type-Options'] = 'nosniff'
        return response
