"""로컬 개발용 API. 로그인과 관리자 기능은 다음 단계에서 추가합니다."""
from contextlib import asynccontextmanager
from typing import Literal, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from .db import connect, initialize

@asynccontextmanager
async def lifespan(app):
    initialize()
    yield

app = FastAPI(title='Bread Master · 예시 데이터', lifespan=lifespan)

@app.get('/api/v1/health')
def health():
    return {'status': 'ok', 'data': 'sample'}

@app.get('/api/v1/categories')
def categories():
    with connect() as db:
        return [dict(row) for row in db.execute('''SELECT * FROM categories WHERE id IN(
            SELECT category_id FROM products WHERE is_sample=0 OR NOT EXISTS(SELECT 1 FROM products WHERE is_sample=0)) ORDER BY id''')]

@app.get('/api/v1/products')
def products(category_id: Optional[int] = None, q: str = ''):
    with connect() as db:
        rows = db.execute('''SELECT p.*, c.name AS category_name FROM products p
                             JOIN categories c ON p.category_id=c.id WHERE p.is_sample=0 OR NOT EXISTS(SELECT 1 FROM products WHERE is_sample=0) ORDER BY p.id''').fetchall()
    return [dict(row) for row in rows if (category_id is None or row['category_id'] == category_id)
            and q.strip().casefold() in row['name'].casefold()]

@app.get('/api/v1/products/{product_id}')
def product(product_id: int):
    with connect() as db:
        row = db.execute('''SELECT p.*, c.name AS category_name FROM products p
                            JOIN categories c ON p.category_id=c.id WHERE p.id=?''', (product_id,)).fetchone()
    if row is None:
        raise HTTPException(404, '상품을 찾을 수 없습니다.')
    return dict(row)

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
