"""Store membership and approval for authenticated accounts."""
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .auth import protect_write, require_account
from .db import connect

router = APIRouter(prefix='/api/v1/stores', tags=['Stores'])


class StoreInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=60)


class JoinInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    code: str = Field(min_length=12, max_length=12, pattern=r'^[a-fA-F0-9]+$')


def membership(db, user_id):
    return db.execute('''
        SELECT s.id, s.name, s.invite_code, m.role, m.status
        FROM store_memberships m JOIN stores s ON s.id=m.store_id
        WHERE m.user_id=?
    ''', (user_id,)).fetchone()


@router.get('/mine')
def mine(account=Depends(require_account)):
    with connect() as db:
        row = membership(db, account['id'])
        if row is None:
            return None
        result = dict(row)
        result.pop('invite_code')
        if row['role'] == 'admin':
            result['invite_code'] = row['invite_code']
            result['requests'] = [dict(request) for request in db.execute('''
                SELECT m.user_id, u.display_name, u.email FROM store_memberships m
                JOIN users u ON u.id=m.user_id
                WHERE m.store_id=? AND m.status='pending' ORDER BY m.rowid
            ''', (row['id'],))]
        return result


def ensure_unaffiliated(db, user_id):
    # Serialize the check and insert, including simultaneous create and join requests.
    db.execute('BEGIN IMMEDIATE')
    if membership(db, user_id):
        raise HTTPException(409, '이미 연결된 매장이나 승인 대기 중인 신청이 있어요.')


@router.post('', status_code=201, dependencies=[Depends(protect_write)])
def create(body: StoreInput, account=Depends(require_account)):
    user_id = account['id']
    with connect() as db:
        ensure_unaffiliated(db, user_id)
        store_id = uuid.uuid4().hex
        db.execute('INSERT INTO stores VALUES (?, ?, ?)', (store_id, body.name, secrets.token_hex(6)))
        db.execute("INSERT INTO store_memberships VALUES (?, ?, 'admin', 'active')", (user_id, store_id))
    return mine(account)


@router.post('/join', status_code=201, dependencies=[Depends(protect_write)])
def join(body: JoinInput, account=Depends(require_account)):
    user_id = account['id']
    with connect() as db:
        ensure_unaffiliated(db, user_id)
        store = db.execute('SELECT id FROM stores WHERE invite_code=?', (body.code.lower(),)).fetchone()
        if store is None:
            raise HTTPException(404, '초대 코드를 확인해 주세요.')
        db.execute("INSERT INTO store_memberships VALUES (?, ?, 'worker', 'pending')", (user_id, store['id']))
    return mine(account)


@router.post('/cancel', status_code=204, dependencies=[Depends(protect_write)])
def cancel(account=Depends(require_account)):
    with connect() as db:
        db.execute("DELETE FROM store_memberships WHERE user_id=? AND status='pending'", (account['id'],))


@router.post('/requests/{user_id}/{decision}', status_code=204, dependencies=[Depends(protect_write)])
def decide(user_id: str, decision: str, account=Depends(require_account)):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = membership(db, account['id'])
        if row is None or row['role'] != 'admin' or row['status'] != 'active':
            raise HTTPException(403, '매장 관리자만 신청을 처리할 수 있어요.')
        if decision == 'approve':
            command = "UPDATE store_memberships SET status='active'"
        elif decision == 'reject':
            command = 'DELETE FROM store_memberships'
        else:
            raise HTTPException(404, '지원하지 않는 처리예요.')
        changed = db.execute(command + " WHERE user_id=? AND store_id=? AND status='pending'", (user_id, row['id']))
        if changed.rowcount != 1:
            raise HTTPException(404, '이 매장의 승인 대기 신청을 찾을 수 없어요.')
