"""교육용 API. 계정 인증과 학습 기능을 별도 모듈에서 관리합니다."""
from contextlib import asynccontextmanager
from typing import Literal, Optional
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from .db import connect, initialize
from .store_learning import active_scope

@asynccontextmanager
async def lifespan(app):
    from .auth import validate_configuration
    validate_configuration()
    from .demo import enabled, prepare
    if enabled():
        prepare()
    else:
        initialize()
    yield

app = FastAPI(title='Bread Master · 예시 데이터', lifespan=lifespan)

@app.get('/api/v1/health')
def health():
    from .demo import enabled
    return {'status': 'ok', 'data': 'demo' if enabled() else 'sample'}

@app.get('/api/v1/categories')
def categories(scope=Depends(active_scope)):
    with connect() as db:
        from .pos import catalog
        return catalog(db, scope[1] if scope else None)['categories']

@app.get('/api/v1/products')
def products(category_id: Optional[int] = None, q: str = '', scope=Depends(active_scope)):
    with connect() as db:
        from .pos import catalog
        from .learning import all_products
        raw = all_products(db)
        pos = catalog(db, scope[1] if scope else None)['products']
        mapped = {p['id']:p for p in pos}
        rows = pos if scope else [mapped.get(p['id'], {**p, 'category_id':0, 'category_name':'POS 미분류', 'description':'POS 분류 확인이 필요한 상품입니다.'}) for p in raw]

    return [dict(row) for row in rows if (category_id is None or row['category_id'] == category_id)
            and q.strip().casefold() in row['name'].casefold()]

@app.get('/api/v1/products/{product_id}')
def product(product_id: int, scope=Depends(active_scope)):
    if scope:
        from .pos import catalog
        with connect() as db:
            for item in catalog(db, scope[1])['products']:
                if item['id'] == product_id:
                    return item
        raise HTTPException(404, '상품을 찾을 수 없습니다.')
    with connect() as db:
        row = db.execute('''SELECT p.*, c.name AS category_name FROM products p
                            JOIN categories c ON p.category_id=c.id WHERE p.id=?''', (product_id,)).fetchone()
    if row is None:
        raise HTTPException(404, '상품을 찾을 수 없습니다.')
    with connect() as db:
        from .pos import catalog
        mapped = next((p for p in catalog(db)['products'] if p['id']==product_id), None)
    return mapped or {**dict(row), 'category_id':0, 'category_name':'POS 미분류', 'description':'POS 분류 확인이 필요한 상품입니다.'}

class QuestionRequest(BaseModel):
    mode: Literal['category', 'name', 'similar-photo', 'delivery', 'pos']
    exclude_ids: list[int] = Field(default_factory=list, max_length=100)

@app.post('/api/v1/questions')
def question(body: QuestionRequest, scope=Depends(active_scope)):
    from .learning import create_question
    return create_question(body.mode, body.exclude_ids, scope)

class AnswerRequest(BaseModel):
    selected_id: int
    elapsed_ms: int = Field(ge=0, le=86400000)

@app.post('/api/v1/questions/{question_id}/answer')
def answer(question_id: str, body: AnswerRequest, scope=Depends(active_scope)):
    from .learning import grade_answer
    return grade_answer(question_id, body.selected_id, body.elapsed_ms, scope)

from .inventory import router as inventory_router
app.include_router(inventory_router)

from .delivery import router as delivery_router
app.include_router(delivery_router)

@app.get('/api/v1/pos-catalog')
def pos_catalog(scope=Depends(active_scope)):
    from .pos import catalog
    with connect() as db:
        return catalog(db, scope[1] if scope else None)

from .demo import install_limits
from .auth import install as install_auth
from .stores import router as stores_router
from .web import install as install_web
install_limits(app)
install_auth(app)
app.include_router(stores_router)
from .store_admin import router as store_admin_router
from . import store_catalog, store_import, store_link
from . import quiz_groups
app.include_router(store_admin_router)
from .assessments import router as assessments_router
app.include_router(assessments_router)
install_web(app)
