"""로컬 개발용 API. 로그인과 관리자 기능은 다음 단계에서 추가합니다."""
from contextlib import asynccontextmanager
from typing import Literal, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from .db import connect, initialize

@asynccontextmanager
async def lifespan(app):
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
def categories():
    with connect() as db:
        from .pos import catalog
        return catalog(db)['categories']

@app.get('/api/v1/products')
def products(category_id: Optional[int] = None, q: str = ''):
    with connect() as db:
        from .pos import catalog
        from .learning import all_products
        raw = all_products(db)
        pos = catalog(db)['products']
        mapped = {p['id']:p for p in pos}
        rows = [mapped.get(p['id'], {**p, 'category_id':0, 'category_name':'POS 미분류', 'description':'POS 분류 확인이 필요한 상품입니다.'}) for p in raw]

    return [dict(row) for row in rows if (category_id is None or row['category_id'] == category_id)
            and q.strip().casefold() in row['name'].casefold()]

@app.get('/api/v1/products/{product_id}')
def product(product_id: int):
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
def question(body: QuestionRequest):
    from .learning import create_question
    return create_question(body.mode, body.exclude_ids)

class AnswerRequest(BaseModel):
    selected_id: int
    elapsed_ms: int = Field(ge=0, le=86400000)

@app.post('/api/v1/questions/{question_id}/answer')
def answer(question_id: str, body: AnswerRequest):
    from .learning import grade_answer
    return grade_answer(question_id, body.selected_id, body.elapsed_ms)

from .inventory import router as inventory_router
app.include_router(inventory_router)

from .delivery import router as delivery_router
app.include_router(delivery_router)

@app.get('/api/v1/pos-catalog')
def pos_catalog():
    from .pos import catalog
    with connect() as db:
        return catalog(db)

from .demo import install_limits
from .web import install as install_web
install_limits(app)
install_web(app)
