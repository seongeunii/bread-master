"""로컬 개발용 API. 로그인과 관리자 기능은 다음 단계에서 추가합니다."""
from contextlib import asynccontextmanager
import json
import random
import uuid
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
        return [dict(row) for row in db.execute('SELECT * FROM categories ORDER BY id')]

@app.get('/api/v1/products')
def products(category_id: Optional[int] = None, q: str = ''):
    with connect() as db:
        rows = db.execute('''SELECT p.*, c.name AS category_name FROM products p
                             JOIN categories c ON p.category_id=c.id ORDER BY p.id''').fetchall()
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
    mode: Literal['name', 'pos']

@app.post('/api/v1/questions')
def question(body: QuestionRequest):
    pool = products()
    if len(pool) < 4:
        raise HTTPException(409, '예시 상품이 최소 4개 필요합니다.')
    target = random.choice(pool)
    distractors = random.sample([p for p in pool if p['id'] != target['id']], 3)
    choices = [target] + distractors
    random.shuffle(choices)
    option_ids = [p['id'] for p in choices] if body.mode == 'name' else [p['id'] for p in pool]
    question_id = str(uuid.uuid4())
    with connect() as db:
        db.execute('INSERT INTO questions(id,mode,product_id,options) VALUES(?,?,?,?)',
                   (question_id, body.mode, target['id'], json.dumps(option_ids)))
    return {'id': question_id, 'mode': body.mode, 'illustration': target['illustration'],
            'is_sample': True,
            'options': [{'id': p['id'], 'name': p['name']} for p in choices] if body.mode == 'name' else []}

class AnswerRequest(BaseModel):
    selected_id: int
    elapsed_ms: int = Field(ge=0, le=86400000)

@app.post('/api/v1/questions/{question_id}/answer')
def answer(question_id: str, body: AnswerRequest):
    with connect() as db:
        row = db.execute('SELECT * FROM questions WHERE id=?', (question_id,)).fetchone()
        if row is None:
            raise HTTPException(404, '문제를 찾을 수 없습니다.')
        if body.selected_id not in json.loads(row['options']):
            raise HTTPException(422, '이 문제에서 선택할 수 없는 상품입니다.')
        db.execute('INSERT OR IGNORE INTO answers(question_id,selected_id,is_correct,elapsed_ms) VALUES(?,?,?,?)',
                   (question_id, body.selected_id, int(body.selected_id == row['product_id']), body.elapsed_ms))
        saved = db.execute('SELECT * FROM answers WHERE question_id=?', (question_id,)).fetchone()
    return {'is_correct': bool(saved['is_correct']), 'elapsed_ms': saved['elapsed_ms'],
            'selected_id': saved['selected_id'], 'correct_product': product(row['product_id'])}
