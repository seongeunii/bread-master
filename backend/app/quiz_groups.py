"""Store-owned, reviewable confusion groups. Name rules run locally, without external AI."""
import hashlib
import json
import re
import uuid
from collections import defaultdict
from typing import Literal, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .db import connect
from .pos import catalog
from .store_admin import require_admin, router


def signature(ids):
    return hashlib.sha256(json.dumps(sorted(set(ids))).encode()).hexdigest()


def fingerprint(products):
    return hashlib.sha256(json.dumps(sorted((p['id'], p['name']) for p in products), ensure_ascii=False).encode()).hexdigest()


def initialize_store_groups(db, store_id):
    # A separate marker preserves an intentionally empty group list across restarts.
    if db.execute('SELECT 1 FROM store_quiz_settings WHERE store_id=?', (store_id,)).fetchone():
        return
    legacy = defaultdict(list)
    for product in catalog(db, store_id)['products']:
        if product.get('name_group'):
            legacy[product['name_group']].append(product)
    for name, products in legacy.items():
        if len(products) < 2:
            continue
        group_id = uuid.uuid4().hex
        enabled = sum(bool(p['illustration']) and not p.get('manual_price') for p in products) >= 2
        db.execute('INSERT INTO store_quiz_groups(id,store_id,name,status,enabled,reason,candidate_key) VALUES(?,?,?,?,?,?,?)',
                   (group_id, store_id, name, 'approved', int(enabled), '기존 유사 상품 그룹에서 이전', signature(p['id'] for p in products)))
        db.executemany('INSERT INTO store_quiz_group_products VALUES(?,?)', [(group_id, p['id']) for p in products])
    db.execute('INSERT INTO store_quiz_settings(store_id) VALUES(?)', (store_id,))


def groups(db, store_id, include_deleted=False):
    rows = [dict(row) for row in db.execute('SELECT * FROM store_quiz_groups WHERE store_id=? ORDER BY rowid', (store_id,))]
    for row in rows:
        row['product_ids'] = [item[0] for item in db.execute('SELECT product_id FROM store_quiz_group_products WHERE group_id=? ORDER BY product_id', (row['id'],))]
        row['enabled'] = bool(row['enabled'])
        row.pop('store_id')
    return [row for row in rows if include_deleted or not row['deleted']]


def playable_groups(db, store_id, pool):
    available = {p['id'] for p in pool}
    return [ids for group in groups(db, store_id) if group['status'] == 'approved' and group['enabled']
            for ids in [[pid for pid in group['product_ids'] if pid in available]] if len(ids) >= 2]


def state(db, store_id):
    layout = catalog(db, store_id)
    saved = db.execute('SELECT fingerprint FROM store_quiz_settings WHERE store_id=?', (store_id,)).fetchone()
    return {**layout, 'groups': groups(db, store_id),
            'recommendations_initialized': bool(saved and saved['fingerprint'] is not None),
            'recommendations_stale': not saved or saved['fingerprint'] != fingerprint(layout['products'])}


def normalize(name):
    name = re.sub(r'\d+\s*/\s*\d+|[½¼¾]|\d+\s*(?:개입|입|개|원)', '', name)
    name = name.replace('예시', '').replace('빵', '')
    return re.sub(r'[^가-힣a-z]', '', name.casefold())


def recommend(products):
    buckets = defaultdict(set)
    names = {p['id']: normalize(p['name']) for p in products if not p.get('manual_price')}
    generic = {'크림', '생크림', '브레드', '케이크', '샌드위치', '상품'}
    for pid, name in names.items():
        for size in range(2, min(7, len(name) + 1)):
            for start in range(len(name) - size + 1):
                word = name[start:start + size]
                if not any(word in common for common in generic):
                    buckets[word].add(pid)
    candidates = {}
    for word, ids in buckets.items():
        if len(ids) < 2:
            continue
        key = signature(ids)
        # Keep the longest shared phrase for the same membership.
        if key not in candidates or len(word) > len(candidates[key][0]):
            candidates[key] = (word, ids, f'상품명에 “{word}” 포함')
    coffee = {pid for pid, name in names.items() if '커피' in name or '모카' in name}
    if len(coffee) >= 2:
        candidates[signature(coffee)] = ('커피·모카', coffee, '커피·모카 계열 (동의어 사전)')
    # Suppress meaningless interior fragments when a longer phrase covers their whole set.
    values = list(candidates.items())
    return [(key, word, ids, reason) for key, (word, ids, reason) in values
            if not any(word != other and word in other and ids <= other_ids
                       for _, (other, other_ids, _) in values)]


class GroupInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    id: Optional[str] = None
    name: str = Field(min_length=1, max_length=60)
    product_ids: list[int] = Field(min_length=2, max_length=500)
    status: Literal['proposed', 'approved', 'dismissed'] = 'approved'
    enabled: bool = True


@router.get('/quiz-groups')
def get_groups(scope=Depends(require_admin)):
    with connect() as db:
        return state(db, scope[1])


@router.post('/quiz-groups/recommend')
def refresh_groups(scope=Depends(require_admin)):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        products = catalog(db, scope[1])['products']
        existing = groups(db, scope[1], True)
        known = {g['candidate_key'] for g in existing} | {signature(g['product_ids']) for g in existing}
        for key, word, ids, reason in recommend(products):
            if key in known:
                continue
            group_id = uuid.uuid4().hex
            db.execute('INSERT INTO store_quiz_groups(id,store_id,name,status,reason,candidate_key) VALUES(?,?,?,?,?,?)',
                       (group_id, scope[1], word + ' 구분', 'proposed', reason, key))
            db.executemany('INSERT INTO store_quiz_group_products VALUES(?,?)', [(group_id, pid) for pid in ids])
        db.execute('UPDATE store_quiz_settings SET fingerprint=? WHERE store_id=?', (fingerprint(products), scope[1]))
        return state(db, scope[1])


@router.post('/quiz-groups/save')
def save_group(body: GroupInput, scope=Depends(require_admin)):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        old = db.execute('SELECT * FROM store_quiz_groups WHERE id=? AND store_id=? AND deleted=0', (body.id, scope[1])).fetchone() if body.id else None
        if body.id and old is None:
            raise HTTPException(404, '이 매장의 그룹을 찾을 수 없어요.')
        products = {p['id']: p for p in catalog(db, scope[1])['products']}
        ids = set(body.product_ids)
        if len(ids) < 2 or not ids <= products.keys():
            raise HTTPException(422, '이 매장의 서로 다른 상품을 두 개 이상 선택하세요.')
        enabled = body.enabled and body.status == 'approved'
        if enabled and sum(bool(products[pid]['illustration']) and not products[pid].get('manual_price') for pid in ids) < 2:
            raise HTTPException(422, '출제하려면 사진이 있는 상품이 최소 두 개 필요해요.')
        group_id = body.id or uuid.uuid4().hex
        if old:
            db.execute('UPDATE store_quiz_groups SET name=?,status=?,enabled=? WHERE id=? AND store_id=?',
                       (body.name, body.status, int(enabled), group_id, scope[1]))
            db.execute('DELETE FROM store_quiz_group_products WHERE group_id=?', (group_id,))
        else:
            db.execute('INSERT INTO store_quiz_groups(id,store_id,name,status,enabled,reason) VALUES(?,?,?,?,?,?)',
                       (group_id, scope[1], body.name, body.status, int(enabled), '관리자가 직접 구성'))
        db.executemany('INSERT INTO store_quiz_group_products VALUES(?,?)', [(group_id, pid) for pid in ids])
        return state(db, scope[1])


@router.post('/quiz-groups/{group_id}/delete')
def delete_group(group_id: str, scope=Depends(require_admin)):
    with connect() as db:
        changed = db.execute("UPDATE store_quiz_groups SET deleted=1,status='dismissed',enabled=0 WHERE id=? AND store_id=? AND deleted=0", (group_id, scope[1]))
        if changed.rowcount != 1:
            raise HTTPException(404, '이 매장의 그룹을 찾을 수 없어요.')
        return state(db, scope[1])
