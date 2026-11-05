"""File preview and atomic menu registration after user confirmation."""
import csv
import hashlib
import io
import itertools
import zipfile

from fastapi import Depends, HTTPException, Request
from openpyxl import load_workbook
from pydantic import BaseModel, Field

from .db import connect
from .pos import catalog
from .store_admin import MenuInput, require_admin, router, save_menu_in_db

HEADERS = ['상품명', '가격', '카테고리', '칸번호', '사진주소']


@router.post('/import/preview')
async def preview(request: Request, scope=Depends(require_admin)):
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > 2 * 1024 * 1024:
            raise HTTPException(413, '등록 파일은 2MB 이하로 올려 주세요.')
    workbook = None
    try:
        if bytes(data).startswith(b'PK'):
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                if len(archive.infolist()) > 1000 or sum(item.file_size for item in archive.infolist()) > 20 * 1024 * 1024:
                    raise ValueError()
            workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=False)
            rows = workbook.active.iter_rows(values_only=True)
        else:
            rows = csv.reader(io.StringIO(bytes(data).decode('utf-8-sig')))
        header = [str(value or '').strip() for value in next(rows)]
        if header != HEADERS:
            raise HTTPException(422, '첫 행은 상품명,가격,카테고리,칸번호,사진주소 순서로 작성해 주세요.')
        result = []
        for row_index, row in enumerate(itertools.islice(rows, 101)):
            if row_index >= 100:
                raise ValueError()
            if not any(value is not None and str(value).strip() for value in row):
                continue
            if len(row) != 5 or len(result) >= 100:
                raise ValueError()
            result.append(dict(zip(HEADERS, [str(value).strip() if value is not None else '' for value in row])))
        if not result:
            raise ValueError()
        return {'rows': result}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, 'UTF-8 CSV 또는 정상 XLSX 파일의 첫 시트를 확인해 주세요. 최대 100행을 지원해요.')
    finally:
        if workbook:
            workbook.close()


class ImportInput(BaseModel):
    request_id: str = Field(pattern=r'^[a-f0-9-]{36}$')
    items: list[MenuInput] = Field(min_length=1, max_length=100)


@router.post('/import/save')
def commit(body: ImportInput, scope=Depends(require_admin)):
    if any(item.product_id is not None for item in body.items):
        raise HTTPException(422, '일괄 등록은 새 메뉴에 사용해 주세요.')
    payload = hashlib.sha256(body.model_dump_json(exclude={'request_id'}).encode()).hexdigest()
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        previous = db.execute('SELECT payload_hash FROM store_imports WHERE store_id=? AND request_id=?',
                              (scope[1], body.request_id)).fetchone()
        if previous:
            if previous['payload_hash'] != payload:
                raise HTTPException(409, '이미 사용한 등록 요청이에요. 파일을 다시 선택해 주세요.')
            return catalog(db, scope[1])
        for index, item in enumerate(body.items, 1):
            try:
                save_menu_in_db(db, item, scope)
            except HTTPException as error:
                raise HTTPException(error.status_code, f'{index}행: {error.detail}')
        db.execute('INSERT INTO store_imports VALUES(?,?,?)', (scope[1], body.request_id, payload))
        return catalog(db, scope[1])
