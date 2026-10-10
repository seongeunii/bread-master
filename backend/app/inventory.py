"""재고 입력 연습 전용 API. 실제 재고 및 상품 정보는 변경하지 않습니다."""
import json
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from .db import connect
from .learning import all_products

router = APIRouter(prefix='/api/v1/inventory-practices', tags=['Inventory practice'])

class InventoryItem(BaseModel):
    product_id: int = Field(strict=True, gt=0)
    quantity: int = Field(strict=True, ge=0, le=9999)

class CategorySubmission(BaseModel):
    category_id: int = Field(strict=True, gt=0)
    items: list[InventoryItem] = Field(min_length=1, max_length=500)

@router.post('')
def start_practice():
    with connect() as db:
        catalog = []
        for p in all_products(db):
            catalog.append({**p, 'quantity': 3})
        if not catalog:
            raise HTTPException(409, '등록 연습에 사용할 상품이 없습니다.')
        practice_id = str(uuid.uuid4())
        db.execute('INSERT INTO inventory_practices(id,catalog) VALUES(?,?)', (practice_id, json.dumps(catalog)))
    return {'id': practice_id, 'products': catalog, 'saved_categories': {}}

@router.get('/{practice_id}')
def get_practice(practice_id: str):
    with connect() as db:
        row = db.execute('SELECT * FROM inventory_practices WHERE id=?', (practice_id,)).fetchone()
    if row is None:
        raise HTTPException(404, '재고 연습을 찾을 수 없습니다.')
    return {'id': row['id'], 'products': json.loads(row['catalog']), 'saved_categories': json.loads(row['saved_categories'])}

@router.post('/{practice_id}/categories')
def save_category(practice_id: str, body: CategorySubmission):
    with connect() as db:
        # 두 요청이 동시에 저장해도 다른 카테고리 결과를 덮어쓰지 않습니다.
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM inventory_practices WHERE id=?', (practice_id,)).fetchone()
        if row is None:
            raise HTTPException(404, '재고 연습을 찾을 수 없습니다.')
        expected = [p for p in json.loads(row['catalog']) if p['category_id'] == body.category_id]
        if not expected:
            raise HTTPException(422, '이 연습에 없는 카테고리입니다.')
        submitted = {item.product_id: item.quantity for item in body.items}
        if len(submitted) != len(body.items):
            raise HTTPException(422, '같은 상품을 중복 제출할 수 없습니다.')
        if set(submitted) != {p['id'] for p in expected}:
            raise HTTPException(422, '현재 카테고리의 상품 수량을 빠짐없이 전달해 주세요.')
        result = {'category_id': body.category_id, 'items': [item.model_dump() for item in body.items]}
        saved = json.loads(row['saved_categories'])
        saved[str(body.category_id)] = result
        db.execute('UPDATE inventory_practices SET saved_categories=? WHERE id=?', (json.dumps(saved), practice_id))
    return result
