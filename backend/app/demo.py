"""공개 데모만 사용하는 시작·제한 설정. 로컬 학습 DB는 변경하지 않습니다."""
import os
import time
from collections import deque
from pathlib import Path
from starlette.responses import JSONResponse
from .db import initialize, connect

def enabled():
    return os.environ.get('BREAD_DEMO') == '1'

def prepare():
    if not os.environ.get('BREAD_DB_PATH'):
        raise RuntimeError('데모에는 별도 BREAD_DB_PATH 설정이 필요합니다.')
    initialize()
    with connect() as db:
        imported = db.execute('SELECT COUNT(*) FROM products WHERE is_sample=0').fetchone()[0]
    if not imported:
        from scripts.import_paris import import_manifest
        import_manifest(Path(__file__).parents[1] / 'data/paris-bread.json', backup=False)

def install_limits(app, limit=300, window=60):
    # 단일 데모 인스턴스 전체 쓰기 요청에 상한을 둡니다. IP나 개인정보를 보관하지 않습니다.
    writes = deque()
    last_cleanup = 0.0
    @app.middleware('http')
    async def demo_limits(request, call_next):
        nonlocal last_cleanup
        if enabled() and request.method == 'POST' and request.url.path.startswith('/api/'):
            now = time.monotonic()
            while writes and writes[0] <= now-window:
                writes.popleft()
            if len(writes) >= limit:
                return JSONResponse({'detail':'데모 이용량이 많아요. 잠시 후 다시 시도해 주세요.'}, status_code=429, headers={'Retry-After':str(window)})
            writes.append(now)
            if now-last_cleanup >= window:
                with connect() as db:
                    db.execute('DELETE FROM answers WHERE question_id NOT IN (SELECT id FROM questions ORDER BY rowid DESC LIMIT 2000)')
                    db.execute('DELETE FROM questions WHERE id NOT IN (SELECT id FROM questions ORDER BY rowid DESC LIMIT 2000)')
                    db.execute('DELETE FROM delivery_orders WHERE id NOT IN (SELECT id FROM delivery_orders ORDER BY rowid DESC LIMIT 500)')
                    db.execute('DELETE FROM inventory_practices WHERE id NOT IN (SELECT id FROM inventory_practices ORDER BY rowid DESC LIMIT 100)')
                last_cleanup = now
        response = await call_next(request)
        if enabled():
            response.headers['X-Content-Type-Options'] = 'nosniff'
        return response
