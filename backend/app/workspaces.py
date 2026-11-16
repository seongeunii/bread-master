"""Private practice spaces and official-store session selection."""
import json
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from .auth import COOKIE_NAME, digest, protect_write, require_account
from .db import connect

router = APIRouter(prefix='/api/v1/workspaces', tags=['Workspaces'])


def available_workspaces(db, user_id):
    return [dict(row) for row in db.execute("""
        SELECT s.id,s.name,w.kind,'owner' AS role FROM stores s
        JOIN workspace_metadata w ON w.store_id=s.id
        WHERE w.kind='personal' AND w.owner_id=?
        UNION ALL
        SELECT s.id,s.name,w.kind,m.role FROM stores s
        JOIN workspace_metadata w ON w.store_id=s.id
        JOIN store_memberships m ON m.store_id=s.id
        WHERE w.kind='store' AND m.user_id=? AND m.status='active'
    """, (user_id,user_id))]


def restore_selection(db, token_hash, user_id):
    previous = db.execute('SELECT workspace_id FROM workspace_preferences WHERE user_id=?', (user_id,)).fetchone()
    spaces = available_workspaces(db, user_id)
    workspace_id = previous['workspace_id'] if previous else spaces[0]['id'] if spaces else None
    if workspace_id not in {space['id'] for space in spaces}:
        workspace_id = None
    db.execute('INSERT INTO workspace_selections VALUES(?,?)', (token_hash,workspace_id))


def current_workspace(db, request, user_id):
    token_hash = digest(request.cookies.get(COOKIE_NAME, ''))
    row = db.execute('SELECT workspace_id FROM workspace_selections WHERE token_hash=?', (token_hash,)).fetchone()
    if row is None:
        # Sessions issued before spaces existed keep their official-store access.
        restore_selection(db, token_hash, user_id)
        row = db.execute('SELECT workspace_id FROM workspace_selections WHERE token_hash=?', (token_hash,)).fetchone()
    return next((space for space in available_workspaces(db,user_id) if space['id'] == row['workspace_id']), None)


def select_workspace(db, request, user_id, workspace_id):
    space = next((space for space in available_workspaces(db,user_id) if space['id'] == workspace_id), None)
    if space is None:
        raise HTTPException(404, '이 공간에 접근할 수 없어요.')
    db.execute('INSERT INTO workspace_selections VALUES(?,?) ON CONFLICT(token_hash) DO UPDATE SET workspace_id=excluded.workspace_id',
               (digest(request.cookies.get(COOKIE_NAME, '')),workspace_id))
    db.execute('INSERT INTO workspace_preferences VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET workspace_id=excluded.workspace_id', (user_id,workspace_id))
    return space


def initialize_empty_workspace(db, store_id, kind, owner_id=None):
    db.execute('INSERT INTO workspace_metadata VALUES(?,?,?)', (store_id,kind,owner_id))
    db.execute('INSERT INTO store_categories VALUES(?,?)', (store_id,json.dumps([{'id':1,'name':'기본'}])))
    from .quiz_groups import initialize_store_groups
    initialize_store_groups(db,store_id)


def migrate_legacy_workspaces(db):
    from .pos import catalog
    for store in db.execute('SELECT id FROM stores WHERE id NOT IN (SELECT store_id FROM workspace_metadata)').fetchall():
        store_id = store['id']
        layout = catalog(db,store_id)
        db.execute('INSERT INTO store_categories VALUES(?,?) ON CONFLICT(store_id) DO NOTHING', (store_id,json.dumps(layout['categories'])))
        for product in layout['products']:
            db.execute('INSERT INTO workspace_product_metadata VALUES(?,?,?)', (store_id,product['id'],json.dumps(product)))
            db.execute('''INSERT INTO store_menus(store_id,product_id,category_id,pos_slot,name,price,illustration,name_group,source_url)
                VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(store_id,product_id) DO NOTHING''',
                (store_id,product['id'],product['category_id'],product['pos_slot'],product['name'],product['price'],product['illustration'],product.get('name_group'),product.get('source_url')))
        db.execute("INSERT INTO workspace_metadata VALUES(?,'store',NULL)", (store_id,))


@router.get('')
def list_workspaces(request: Request, account=Depends(require_account)):
    with connect() as db:
        return {'items': available_workspaces(db,account['id']), 'current': current_workspace(db,request,account['id'])}


@router.post('/personal', dependencies=[Depends(protect_write)])
def personal(request: Request, account=Depends(require_account)):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute("SELECT store_id FROM workspace_metadata WHERE owner_id=? AND kind='personal'", (account['id'],)).fetchone()
        store_id = row['store_id'] if row else uuid.uuid4().hex
        if not row:
            db.execute('INSERT INTO stores VALUES(?,?,?)', (store_id,'내 연습 공간',secrets.token_hex(6)))
            initialize_empty_workspace(db,store_id,'personal',account['id'])
        return select_workspace(db,request,account['id'],store_id)


class Selection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    workspace_id: str


@router.post('/select', dependencies=[Depends(protect_write)])
def choose(body: Selection, request: Request, account=Depends(require_account)):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        return select_workspace(db,request,account['id'],body.workspace_id)


@router.get('/readiness')
def readiness(request: Request, account=Depends(require_account)):
    from .store_learning import active_scope
    from .pos import catalog
    from .quiz_groups import playable_groups
    scope = active_scope(request)
    with connect() as db:
        products = [p for p in catalog(db,scope[1])['products'] if p['illustration'] and not p.get('manual_price')]
        return {'photo_count': len(products), 'similar_ready': bool(playable_groups(db,scope[1],products))}
