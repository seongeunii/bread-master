"""Store category editing and normalized photo storage."""
import io
import json
import uuid
import warnings
from typing import Optional

from fastapi import Depends, HTTPException, Request, Response
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field

from .db import connect
from .pos import catalog
from .store_admin import require_admin, require_member, router

MAX_UPLOAD_BYTES = 5 * 1024 * 1024


class CategoryInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    id: Optional[int] = None
    name: str = Field(min_length=1, max_length=40)


class CategoriesInput(BaseModel):
    items: list[CategoryInput] = Field(min_length=1, max_length=50)


@router.post('/categories')
def save_categories(body: CategoriesInput, scope=Depends(require_admin)):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        current = catalog(db, scope[1])
        current_ids = {c['id'] for c in current['categories']}
        ids = [c.id for c in body.items if c.id is not None]
        names = [c.name.casefold() for c in body.items]
        if len(ids) != len(set(ids)) or len(names) != len(set(names)):
            raise HTTPException(422, '카테고리 이름이나 ID가 중복돼요.')
        if not set(ids).issubset(current_ids):
            raise HTTPException(422, '이 매장에 없는 카테고리예요.')
        occupied = {p['category_id'] for p in current['products']}
        if not occupied.issubset(ids):
            raise HTTPException(409, '상품이 남아 있는 카테고리는 상품을 옮긴 뒤 삭제해 주세요.')
        next_id = max(100000, *current_ids) + 1
        categories = []
        for item in body.items:
            category_id = item.id
            if category_id is None:
                category_id = next_id
                next_id += 1
            categories.append({'id': category_id, 'name': item.name})
        db.execute('INSERT INTO store_categories(store_id,items) VALUES(?,?) '
                   'ON CONFLICT(store_id) DO UPDATE SET items=excluded.items',
                   (scope[1], json.dumps(categories)))
        return catalog(db, scope[1])


@router.post('/photos', status_code=201)
async def upload_photo(request: Request, scope=Depends(require_admin)):
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, '사진은 5MB 이하로 올려 주세요.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as original:
                if original.format not in ('JPEG', 'PNG', 'WEBP') or original.width * original.height > 16000000:
                    raise ValueError()
                image = ImageOps.exif_transpose(original)
                image.thumbnail((1200, 1200))
                if image.mode in ('RGBA', 'LA') or 'transparency' in image.info:
                    rgba = image.convert('RGBA')
                    background = Image.new('RGB', rgba.size, 'white')
                    background.paste(rgba, mask=rgba.getchannel('A'))
                    image = background
                else:
                    image = image.convert('RGB')
                output = io.BytesIO()
                image.save(output, format='JPEG', quality=85)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombWarning, Image.DecompressionBombError):
        raise HTTPException(422, '정상적인 JPG·PNG·WebP 사진을 선택해 주세요.')
    data = output.getvalue()
    photo_id = uuid.uuid4().hex
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        total = db.execute('SELECT COALESCE(SUM(length(data)),0) FROM store_photos WHERE store_id=?', (scope[1],)).fetchone()[0]
        if total + len(data) > 32 * 1024 * 1024:
            raise HTTPException(409, '매장 사진 저장 한도 32MB에 도달했어요.')
        db.execute('INSERT INTO store_photos VALUES(?,?,?)', (photo_id, scope[1], data))
    return {'url': f'/api/v1/store-admin/photos/{photo_id}'}


@router.get('/photos/{photo_id}')
def photo(photo_id: str, scope=Depends(require_member)):
    with connect() as db:
        row = db.execute('SELECT data FROM store_photos WHERE id=? AND store_id=?', (photo_id, scope[1])).fetchone()
    if row is None:
        raise HTTPException(404, '사진을 찾을 수 없어요.')
    return Response(row['data'], media_type='image/jpeg', headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
