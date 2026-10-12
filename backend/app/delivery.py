"""여러 상품과 수량을 주문하는 배달 심화 연습."""
import json
import random
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from .db import connect
from .learning import all_products

router = APIRouter(prefix='/api/v1/delivery-orders', tags=['Delivery practice'])

def order_quantity():
    # 대부분 1개, 가끔 2개, 드물게 3~4개.
    return random.choices([1, 2, 3, 4], weights=[80, 16, 3, 1], k=1)[0]

class CartItem(BaseModel):
    product_id: int = Field(strict=True, gt=0)
    quantity: int = Field(strict=True, ge=1, le=99)

class Submission(BaseModel):
    items: list[CartItem] = Field(max_length=500)
    elapsed_ms: int = Field(strict=True, ge=0, le=86400000)

@router.post('')
def create_order(use_pos: bool = False):
    with connect() as db:
        from .pos import catalog
        pool = [p for p in catalog(db)['products'] if p['illustration'] and not p.get('manual_price')]
        if len(pool) < 3:
            raise HTTPException(409, '배달 심화에는 상품이 최소 3개 필요합니다.')
        candidates = random.sample(pool, len(pool) if use_pos else min(15, len(pool)))
        ordered = random.sample(candidates, random.randint(1 if use_pos else 2, min(3 if use_pos else 4, len(candidates))))
        lines = [{'product_id': p['id'], 'name': p['name'], 'quantity': order_quantity()} for p in ordered]
        options = [{'id': p['id'], 'illustration': p['illustration']} for p in (catalog(db)['products'] if use_pos else candidates)]
        id = str(uuid.uuid4())
        db.execute('INSERT INTO delivery_orders(id,lines,options) VALUES(?,?,?)', (id, json.dumps(lines), json.dumps(options)))
    return {'id': id, 'lines': lines, 'options': options, 'is_sample': True}

@router.post('/{order_id}/submit')
def submit_order(order_id: str, body: Submission):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM delivery_orders WHERE id=?', (order_id,)).fetchone()
        if row is None:
            raise HTTPException(404, '주문을 찾을 수 없습니다.')
        if row['result']:
            return json.loads(row['result'])
        cart = {i.product_id: i.quantity for i in body.items}
        allowed = {i['id'] for i in json.loads(row['options'])}
        if len(cart) != len(body.items) or not set(cart).issubset(allowed):
            raise HTTPException(422, '중복 상품이나 후보에 없는 상품은 제출할 수 없습니다.')
        lines = json.loads(row['lines'])
        expected = {i['product_id']: i['quantity'] for i in lines}
        correct = cart == expected
        names = {p['id']: p['name'] for p in all_products(db)}
        from .pos import catalog
        names.update({p['id']:p['name'] for p in catalog(db)['products']})
        differences = [{'product_id': id, 'name': names.get(id, '상품'), 'expected': expected.get(id, 0), 'actual': cart.get(id, 0)}
                       for id in sorted(set(cart) | set(expected)) if cart.get(id, 0) != expected.get(id, 0)]
        result = {'is_correct': correct, 'points': 20 if correct else 0, 'elapsed_ms': body.elapsed_ms,
                  'feedback': '배달 성공! 상품과 수량이 모두 맞아요.' if correct else '배달 실수! 손님이 화났어요.',
                  'differences': differences}
        db.execute('UPDATE delivery_orders SET result=? WHERE id=?', (json.dumps(result), order_id))
    return result


@router.post('/pos/start')
def create_pos_order():
    return create_order(True)

@router.post('/pos/{order_id}/submit')
def submit_pos_order(order_id: str, body: Submission):
    result = submit_order(order_id, body)
    return {**result, 'feedback': '결제 연습 성공! 상품과 수량이 모두 맞아요.' if result['is_correct'] else '결제 실수! 등록 상품과 수량을 다시 확인해요.'}
