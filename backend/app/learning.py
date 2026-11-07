"""네 단계의 출제와 채점 규칙. 도감 API 및 화면과 분리합니다."""
import json
import random
import uuid
from fastapi import HTTPException
from .db import connect
from .store_learning import exercise, finish, remember

POINTS_PER_CORRECT = 20

def all_products(db):
    return [dict(r) for r in db.execute('''SELECT p.*, c.name AS category_name FROM products p
                                        JOIN categories c ON p.category_id=c.id
                                        WHERE p.is_sample=0 OR NOT EXISTS(SELECT 1 FROM products WHERE is_sample=0) ORDER BY p.id''')]

def build_question(db, mode, exclude_ids, scope=None):
    # 모든 퀴즈는 동일한 POS 분류를 사용합니다.
    from .pos import catalog
    layout = catalog(db, scope[1] if scope else None)
    if scope:
        pool = [p for p in layout['products'] if p['illustration'] and not p.get('manual_price')]
    else:
        pool = [p for p in layout['products'] if p.get('source_product_id', p['id']) is not None]
    pool.sort(key=lambda p: p['id'])
    eligible = [p for p in pool if p['id'] not in exclude_ids]
    matching_groups = []
    if mode in ('name', 'similar-photo'):
        if scope:
            from .quiz_groups import playable_groups
            matching_groups = playable_groups(db, scope[1], pool)
        else:
            matching_groups = [[p['id'] for p in pool if p.get('name_group') == group]
                               for group in {p.get('name_group') for p in pool} if group]
            matching_groups = [ids for ids in matching_groups if len(ids) >= 2]
        eligible = [p for p in eligible if any(p['id'] in ids for ids in matching_groups)]
        # A two-product store group must still support a full five-question round.
        if scope and not eligible and matching_groups:
            eligible = [p for p in pool if any(p['id'] in ids for ids in matching_groups)]
    if not eligible:
        raise HTTPException(409, '출제할 상품이 부족합니다. 유사 상품명 그룹 설정 또는 새로운 라운드가 필요합니다.')
    target = random.choice(eligible)
    if mode == 'category':
        active_categories = {p['category_id'] for p in pool}
        choices = [c for c in layout['categories'] if c['id'] in active_categories]
        correct_id = target['category_id']
    elif mode in ('name', 'similar-photo'):
        members = random.choice([ids for ids in matching_groups if target['id'] in ids])
        others = [p for p in pool if p['id'] in members and p['id'] != target['id']]
        selected = [target] + random.sample(others, min(3, len(others)))
        field = 'name' if mode == 'name' else 'illustration'
        choices = [{'id': p['id'], field: p[field]} for p in selected]
        correct_id = target['id']
    elif mode == 'delivery':
        if len(pool) < 4:
            raise HTTPException(409, '배달 연습에는 상품이 최소 4개 필요합니다.')
        pictures = [target] + random.sample([p for p in pool if p['id'] != target['id']], 3)
        # 이름과 카테고리를 보기에서 숨깁니다.
        choices = [{'id': p['id'], 'illustration': p['illustration']} for p in pictures]
        correct_id = target['id']
    elif mode == 'pos':
        if len(pool) >= 4:
            products = [target] + random.sample([p for p in pool if p['id'] != target['id']], 3)
            choices = [{'id': p['id'], 'name': p['name'], 'category_name': p['category_name']}
                       for p in products]
        else:
            choices = []
        correct_id = target['id']
    else:
        choices = []
        correct_id = target['id']
    random.shuffle(choices)
    allowed = [p['id'] for p in pool] if mode == 'pos' else [o['id'] for o in choices]
    question_id = str(uuid.uuid4())
    public = {'id': question_id, 'mode': mode, 'is_sample': True,
            'illustration': None if mode in ('delivery', 'similar-photo') else target['illustration'],
            'prompt_name': target['name'] if mode in ('delivery', 'similar-photo') else None,
            'options': choices}
    return public, target, correct_id, allowed


def create_question(mode, exclude_ids, scope=None):
    with connect() as db:
        public, target, correct_id, allowed = build_question(db, mode, exclude_ids, scope)
        if scope:
            remember(db, public['id'], scope, mode, {
                'product': target, 'correct_id': correct_id, 'options': allowed,
                'question': public,
            })
        else:
            db.execute('INSERT INTO questions(id,mode,product_id,options,correct_answer_id) VALUES(?,?,?,?,?)',
                       (public['id'], mode, target['id'], json.dumps(allowed), correct_id))
    return public


def retry_question(exercise_id, scope):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        tracked = exercise(db, exercise_id, scope)
        if not tracked or tracked['correct'] != 0 or not tracked['completed_at']:
            raise HTTPException(404, '복습할 오답을 찾을 수 없어요.')
        snapshot = json.loads(tracked['snapshot'])
        question = snapshot.get('question')
        if not question or not question['options']:
            raise HTTPException(409, '이 기록은 정답만 확인할 수 있어요.')
        question['id'] = str(uuid.uuid4())
        random.shuffle(question['options'])
        snapshot.pop('result', None)
        remember(db, question['id'], scope, tracked['mode'], snapshot)
        return question


def grade_answer(question_id, selected_id, elapsed_ms, scope=None):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        tracked = exercise(db, question_id, scope)
        if tracked:
            data = json.loads(tracked['snapshot'])
            if not isinstance(data, dict) or 'correct_id' not in data:
                raise HTTPException(404, '문제를 찾을 수 없습니다.')
            if selected_id not in data['options']:
                raise HTTPException(422, '이 문제에서 선택할 수 없는 답입니다.')
            if 'result' in data:
                return data['result']
            correct = selected_id == data['correct_id']
            result = answer_result(tracked['mode'], correct, elapsed_ms, selected_id, data['product'])
            data['result'] = result
            db.execute('UPDATE store_exercises SET snapshot=? WHERE id=?', (json.dumps(data), question_id))
            finish(db, question_id, correct)
            return result
        return grade_guest(db, question_id, selected_id, elapsed_ms)


def grade_guest(db, question_id, selected_id, elapsed_ms):
    row = db.execute('SELECT * FROM questions WHERE id=?', (question_id,)).fetchone()
    if row is None:
        raise HTTPException(404, '문제를 찾을 수 없습니다.')
    if selected_id not in json.loads(row['options']):
        raise HTTPException(422, '이 문제에서 선택할 수 없는 답입니다.')
    correct_id = row['correct_answer_id'] if row['correct_answer_id'] is not None else row['product_id']
    db.execute('INSERT OR IGNORE INTO answers(question_id,selected_id,is_correct,elapsed_ms) VALUES(?,?,?,?)',
               (question_id, selected_id, int(selected_id == correct_id), elapsed_ms))
    saved = db.execute('SELECT * FROM answers WHERE question_id=?', (question_id,)).fetchone()
    correct_product = dict(db.execute('SELECT p.*, c.name AS category_name FROM products p JOIN categories c ON p.category_id=c.id WHERE p.id=?', (row['product_id'],)).fetchone())
    # 모든 정답·오답 안내에 POS 이름과 분류를 적용합니다.
    from .pos import catalog
    correct_product = next((p for p in catalog(db)['products'] if p['id'] == row['product_id']), {**correct_product, 'category_name':'POS 미분류', 'category_id':0})
    return answer_result(row['mode'], bool(saved['is_correct']), saved['elapsed_ms'], saved['selected_id'], correct_product)


def answer_result(mode, correct, elapsed_ms, selected_id, correct_product):
    messages = {
        'category': ('카테고리 정답! 상품 위치를 잘 기억했어요.', '카테고리 실수! 다른 진열대에서 찾고 있었어요.'),
        'name': ('상품명 정답! 비슷한 이름도 정확히 구분했어요.', '상품명 실수! 비슷한 빵과 헷갈렸어요.'),
        'similar-photo': ('상품 사진 정답! 비슷한 빵도 정확히 구분했어요.', '상품 사진 실수! 이름에 맞는 빵을 다시 확인해요.'),
        'delivery': ('배달 성공! 손님이 기뻐해요.', '배달 실수! 손님이 화났어요.'),
        'pos': ('POS 등록 성공! 손님을 기다리게 하지 않았어요.', 'POS 등록 실수! 다른 상품을 찍었어요.'),
    }
    return {'is_correct': correct, 'elapsed_ms': elapsed_ms, 'selected_id': selected_id,
            'correct_product': correct_product, 'points': POINTS_PER_CORRECT if correct else 0,
            'feedback': messages[mode][0 if correct else 1]}
