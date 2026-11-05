"""Store-scoped exercise ownership and progress."""
import json

from fastapi import HTTPException, Request

from .auth import find_account, protect_write


def active_scope(request: Request):
    account = find_account(request)
    if not account:
        return None
    from .db import connect
    with connect() as db:
        row = db.execute(
            "SELECT store_id, role FROM store_memberships WHERE user_id=? AND status='active'",
            (account['id'],),
        ).fetchone()
    if not row:
        return None
    if request.method == 'POST':
        protect_write(request)
    return (account['id'], row['store_id'], row['role'])


def remember(db, exercise_id, scope, mode, snapshot=None):
    if scope:
        db.execute(
            'INSERT INTO store_exercises(id,user_id,store_id,mode,snapshot) VALUES(?,?,?,?,?)',
            (exercise_id, scope[0], scope[1], mode, json.dumps(snapshot)),
        )


def exercise(db, exercise_id, scope):
    row = db.execute('SELECT * FROM store_exercises WHERE id=?', (exercise_id,)).fetchone()
    if row and (not scope or (row['user_id'], row['store_id']) != scope[:2]):
        raise HTTPException(404, '연습을 찾을 수 없습니다.')
    return row


def finish(db, exercise_id, correct):
    db.execute(
        'UPDATE store_exercises SET correct=?, completed_at=CURRENT_TIMESTAMP WHERE id=? AND completed_at IS NULL',
        (correct, exercise_id),
    )


def progress(db, store_id, user_id=None):
    rows = db.execute("""
        SELECT u.id, u.display_name, COUNT(e.completed_at) AS attempts,
               SUM(e.correct IS NOT NULL AND e.completed_at IS NOT NULL) AS scored,
               COALESCE(SUM(e.correct), 0) AS correct, MAX(e.completed_at) AS latest
        FROM store_memberships m JOIN users u ON u.id=m.user_id
        LEFT JOIN store_exercises e ON e.user_id=m.user_id AND e.store_id=m.store_id
        WHERE m.store_id=? AND m.status='active'
          AND ((? IS NULL AND m.role='worker') OR m.user_id=?)
        GROUP BY u.id ORDER BY u.display_name, u.id
    """, (store_id, user_id, user_id))
    result = []
    for row in rows:
        item = dict(row)
        item['accuracy'] = round(item['correct'] * 100 / item['scored'], 1) if item['scored'] else None
        item['level'] = 3 if item['correct'] >= 30 else 2 if item['correct'] >= 10 else 1
        result.append(item)
    return result
