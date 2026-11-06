"""Separate, server-scored assessments for approved store workers."""
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .db import connect
from .learning import build_question
from .pos import catalog
from .store_admin import require_admin, require_member

router = APIRouter(prefix='/api/v1/assessments', tags=['Assessments'])
PLAN = ('category', 'category', 'name', 'name', 'similar-photo', 'similar-photo',
        'delivery', 'delivery', 'pos', 'pos')
AREAS = {
    'category': 'category',
    'name': 'photo-to-name',
    'similar-photo': 'name-to-photo',
    'delivery': 'delivery',
    'pos': 'pos',
}


def require_worker(scope=Depends(require_member)):
    if scope[2] != 'worker':
        raise HTTPException(403, '승인된 근무자만 평가에 응시할 수 있어요.')
    return scope


def owned_assessment(db, assessment_id, scope):
    row = db.execute('SELECT * FROM assessments WHERE id=? AND user_id=? AND store_id=?',
                     (assessment_id, scope[0], scope[1])).fetchone()
    if row is None:
        raise HTTPException(404, '평가를 찾을 수 없어요.')
    return row


def active_assessment(db, scope):
    return db.execute('''SELECT * FROM assessments
        WHERE user_id=? AND store_id=? AND submitted_at IS NULL''', scope[:2]).fetchone()


def assessment_state(db, row):
    questions = db.execute('''SELECT question, selected_id FROM assessment_questions
        WHERE assessment_id=? ORDER BY position''', (row['id'],)).fetchall()
    return {
        'id': row['id'],
        'questions': [{**json.loads(item['question']), 'selected_id': item['selected_id']}
                      for item in questions],
    }


def result_summary(row):
    return {
        'id': row['id'], 'submitted_at': row['submitted_at'],
        'policy_version': row['policy_version'], **json.loads(row['result']),
    }


@router.get('/mine')
def mine(scope=Depends(require_worker), offset: int = Query(0, ge=0)):
    with connect() as db:
        active = active_assessment(db, scope)
        rows = db.execute('''SELECT * FROM assessments
            WHERE user_id=? AND store_id=? AND submitted_at IS NOT NULL
            ORDER BY submitted_at DESC, rowid DESC LIMIT 21 OFFSET ?''',
                          (*scope[:2], offset)).fetchall()
        return {'active': assessment_state(db, active) if active else None,
                'results': [result_summary(row) for row in rows[:20]], 'has_more': len(rows) > 20}


@router.post('/start')
def start(scope=Depends(require_worker)):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        active = active_assessment(db, scope)
        if active:
            return assessment_state(db, active)
        products = [p for p in catalog(db, scope[1])['products']
                    if p['illustration'] and not p.get('manual_price')]
        if len(products) < 4 or len({p['category_id'] for p in products}) < 2:
            raise HTTPException(409, '평가에는 사진이 등록된 상품 4개와 카테고리 2개 이상이 필요해요.')
        assessment_id = str(uuid.uuid4())
        db.execute('INSERT INTO assessments(id,user_id,store_id,policy_version) VALUES(?,?,?,?)',
                   (assessment_id, *scope[:2], 'mixed-v2-10'))
        excluded_by_mode = {mode: set() for mode in set(PLAN)}
        for position, mode in enumerate(PLAN):
            try:
                question, product, correct_id, _ = build_question(
                    db, mode, excluded_by_mode[mode], scope)
            except HTTPException as exc:
                if exc.status_code == 409 and mode in ('name', 'similar-photo'):
                    raise HTTPException(409, '사진이 있는 상품 2개 이상을 포함한 출제 중 유사 상품 그룹이 필요해요.') from exc
                raise
            excluded_by_mode[mode].add(product['id'])
            db.execute('''INSERT INTO assessment_questions(id,assessment_id,position,question,correct_id)
                          VALUES(?,?,?,?,?)''',
                       (question['id'], assessment_id, position, json.dumps(question), correct_id))
        return assessment_state(db, owned_assessment(db, assessment_id, scope))


class AssessmentAnswer(BaseModel):
    selected_id: int = Field(strict=True)


@router.post('/{assessment_id}/questions/{question_id}/answer')
def save_answer(assessment_id: str, question_id: str, body: AssessmentAnswer,
                scope=Depends(require_worker)):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = owned_assessment(db, assessment_id, scope)
        if row['submitted_at']:
            raise HTTPException(409, '이미 제출한 평가예요.')
        item = db.execute('SELECT * FROM assessment_questions WHERE id=? AND assessment_id=?',
                          (question_id, assessment_id)).fetchone()
        if item is None:
            raise HTTPException(404, '문제를 찾을 수 없어요.')
        options = json.loads(item['question'])['options']
        if body.selected_id not in {option['id'] for option in options}:
            raise HTTPException(422, '보기에서 답을 골라 주세요.')
        db.execute('UPDATE assessment_questions SET selected_id=? WHERE id=?',
                   (body.selected_id, question_id))
        return {'selected_id': body.selected_id}


@router.post('/{assessment_id}/submit')
def submit(assessment_id: str, scope=Depends(require_worker)):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = owned_assessment(db, assessment_id, scope)
        if row['submitted_at']:
            return result_summary(row)
        items = db.execute('SELECT * FROM assessment_questions WHERE assessment_id=? ORDER BY position',
                           (assessment_id,)).fetchall()
        if any(item['selected_id'] is None for item in items):
            raise HTTPException(409, '모든 문제에 답한 뒤 제출해 주세요.')
        areas = {}
        for item in items:
            area = AREAS[json.loads(item['question'])['mode']]
            counts = areas.setdefault(area, {'total': 0, 'correct': 0})
            counts['total'] += 1
            counts['correct'] += int(item['selected_id'] == item['correct_id'])
        result = {'score': round(100 * sum(counts['correct'] for counts in areas.values()) / len(items)),
                  'max_score': 100, 'areas': areas}
        db.execute('UPDATE assessments SET result=?, submitted_at=CURRENT_TIMESTAMP WHERE id=?',
                   (json.dumps(result), assessment_id))
        return result_summary(owned_assessment(db, assessment_id, scope))


@router.get('/store-results')
def store_results(worker_id: str = Query(max_length=64), scope=Depends(require_admin),
                  offset: int = Query(0, ge=0)):
    with connect() as db:
        worker = db.execute("""SELECT 1 FROM store_memberships
            WHERE store_id=? AND user_id=? AND role='worker' AND status='active'""",
                            (scope[1], worker_id)).fetchone()
        if not worker:
            raise HTTPException(404, '같은 매장의 승인된 근무자를 선택해 주세요.')
        rows = db.execute('''SELECT * FROM assessments
            WHERE store_id=? AND user_id=? AND submitted_at IS NOT NULL
            ORDER BY submitted_at DESC, rowid DESC LIMIT 21 OFFSET ?''',
                          (scope[1], worker_id, offset)).fetchall()
        return {'results': [result_summary(row) for row in rows[:20]], 'has_more': len(rows) > 20}
