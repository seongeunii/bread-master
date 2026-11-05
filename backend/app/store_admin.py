"""POS menu edits and learning summaries for the current store."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .db import connect
from .pos import catalog
from .store_learning import active_scope, progress

router = APIRouter(prefix='/api/v1/store-admin', tags=['Store management'])


def require_member(scope=Depends(active_scope)):
    if not scope:
        raise HTTPException(403, '승인된 매장 소속이 필요해요.')
    return scope


def require_admin(scope=Depends(require_member)):
    if scope[2] != 'admin':
        raise HTTPException(403, '매장 관리자만 이용할 수 있어요.')
    return scope


class MenuInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    product_id: Optional[int] = None
    category_id: int
    pos_slot: int = Field(ge=0, le=499)
    name: str = Field(min_length=1, max_length=80)
    price: int = Field(ge=0, le=100000000)
    photo: Optional[str] = Field(default=None, max_length=2048, pattern=r'^(https://[^\s]+|/api/v1/store-admin/photos/[a-f0-9]{32})$')
    name_group: str = Field(default='', max_length=60)


@router.get('/menu')
def menus(scope=Depends(require_admin)):
    with connect() as db:
        return catalog(db, scope[1])


@router.post('/menu')
def save_menu(body: MenuInput, scope=Depends(require_admin)):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        return save_menu_in_db(db, body, scope)


def save_menu_in_db(db, body, scope):
    layout = catalog(db, scope[1])
    if body.category_id not in {c['id'] for c in layout['categories']}:
        raise HTTPException(422, '매장 POS 카테고리를 선택해 주세요.')
    existing = next((p for p in layout['products'] if p['id'] == body.product_id), None)
    if body.product_id is not None and not existing:
        raise HTTPException(404, '메뉴를 찾을 수 없어요.')
    if any(p['id'] != body.product_id and p['category_id'] == body.category_id
           and p['pos_slot'] == body.pos_slot for p in layout['products']):
        raise HTTPException(409, '이미 메뉴가 등록된 칸이에요.')
    photo = body.photo if body.photo is not None else existing['illustration'] if existing else ''
    if photo.startswith('/api/v1/store-admin/photos/'):
        photo_id = photo.rsplit('/', 1)[-1]
        if not db.execute('SELECT 1 FROM store_photos WHERE id=? AND store_id=?', (photo_id, scope[1])).fetchone():
            raise HTTPException(422, '이 매장에 업로드한 사진을 선택해 주세요.')
    product_id = body.product_id
    if product_id is None:
        product_id = db.execute('SELECT COALESCE(MAX(product_id), 999999999)+1 FROM store_menus WHERE product_id>=1000000000').fetchone()[0]
    db.execute("""
        INSERT INTO store_menus(store_id,product_id,category_id,pos_slot,name,price,illustration,name_group)
        VALUES(?,?,?,?,?,?,?,?)
        ON CONFLICT(store_id,product_id) DO UPDATE SET category_id=excluded.category_id,
        pos_slot=excluded.pos_slot,name=excluded.name,price=excluded.price,
        illustration=excluded.illustration,name_group=excluded.name_group
    """, (scope[1], product_id, body.category_id, body.pos_slot, body.name, body.price, photo, body.name_group or None))
    return catalog(db, scope[1])


@router.get('/progress')
def workers(scope=Depends(require_admin)):
    with connect() as db:
        return progress(db, scope[1])


@router.get('/my-progress')
def my_progress(scope=Depends(require_member)):
    with connect() as db:
        return progress(db, scope[1], scope[0])[0]
