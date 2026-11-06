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


def personal_learning(db, store_id, user_id, mistakes_only, offset):
    """Return only this member's completed, scored practice attempts.

    Store exercise snapshots preserve the answer result for question-based
    quizzes. Delivery/POS orders persist their result in delivery_orders.
    Inventory remains unscored and is intentionally excluded from mistakes.
    """
    rows = db.execute("""
        SELECT e.id, e.mode, e.snapshot, e.correct, e.completed_at,
               d.lines AS order_lines, d.result AS order_result
        FROM store_exercises e
        LEFT JOIN delivery_orders d ON d.id=e.id
        WHERE e.store_id=? AND e.user_id=? AND e.completed_at IS NOT NULL
          AND e.correct IS NOT NULL AND (?=0 OR e.correct=0)
        ORDER BY e.completed_at DESC, e.rowid DESC LIMIT 21 OFFSET ?
    """, (store_id, user_id, mistakes_only, offset)).fetchall()
    attempts = []
    for row in rows[:20]:
        item = dict(row)
        mode = item['mode']
        result = None
        product = None
        snapshot = None
        if item['snapshot']:
            try:
                snapshot = json.loads(item['snapshot'])
                result = snapshot.get('result') if isinstance(snapshot, dict) else None
                product = snapshot.get('product') if isinstance(snapshot, dict) else None
            except (TypeError, ValueError):
                pass
        if item['order_result']:
            try:
                result = json.loads(item['order_result'])
                lines = json.loads(item['order_lines'] or '[]')
                product = {'name': ', '.join(f"{line.get('name', '상품')} {line.get('quantity', 1)}개" for line in lines)}
            except (TypeError, ValueError):
                result = None
        if not result or not isinstance(result, dict):
            continue
        correct_product = result.get('correct_product') or product or {}
        attempts.append({
            'id': item['id'], 'mode': mode,
            'product_name': correct_product.get('name', '상품'),
            'category_name': correct_product.get('category_name'),
            'illustration': correct_product.get('illustration'),
            'is_correct': bool(item['correct']) if item['correct'] is not None else bool(result.get('is_correct')),
            'elapsed_ms': result.get('elapsed_ms'),
            'completed_at': item['completed_at'],
            'feedback': result.get('feedback'),
            'differences': result.get('differences', []),
            'can_retry': not item['correct'] and isinstance(snapshot, dict)
                         and bool(snapshot.get('question', {}).get('options')),
        })
    return attempts, len(rows) > 20
