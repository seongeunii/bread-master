"""네 단계의 출제와 채점 규칙. 도감 API 및 화면과 분리합니다."""
import json
import random
import uuid
from fastapi import HTTPException
from .db import connect

POINTS_PER_CORRECT = 20

def all_products(db):
    return [dict(r) for r in db.execute('''SELECT p.*, c.name AS category_name FROM products p
                                        JOIN categories c ON p.category_id=c.id
                                        WHERE p.is_sample=0 OR NOT EXISTS(SELECT 1 FROM products WHERE is_sample=0) ORDER BY p.id''')]

def create_question(mode, exclude_ids):
    with connect() as db:
        pool = all_products(db)
        if mode == 'pos':
            from .pos import catalog
            pool = catalog(db)['products']
        eligible = [p for p in pool if p['id'] not in exclude_ids]
        if mode in ('name', 'similar-photo'):
            # 비슷한 이름은 명시적으로 분류합니다. 카테고리가 같다는 이유로 섞지 않습니다.
            eligible = [p for p in eligible if p['name_group'] and
                        sum(other['name_group'] == p['name_group'] for other in pool) >= 2]
        if not eligible:
            raise HTTPException(409, '출제할 상품이 부족합니다. 유사 상품명 그룹 설정 또는 새로운 라운드가 필요합니다.')
        target = random.choice(eligible)
        if mode == 'category':
            active_categories = {p['category_id'] for p in pool}
            choices = [dict(r) for r in db.execute('SELECT id,name FROM categories ORDER BY id') if r['id'] in active_categories]
            correct_id = target['category_id']
        elif mode == 'name':
            choices = [{'id': p['id'], 'name': p['name']} for p in pool if p['name_group'] == target['name_group']]
            correct_id = target['id']
        elif mode == 'similar-photo':
            choices = [{'id': p['id'], 'illustration': p['illustration']} for p in pool if p['name_group'] == target['name_group']]
            correct_id = target['id']
        elif mode == 'delivery':
            if len(pool) < 4:
                raise HTTPException(409, '배달 연습에는 상품이 최소 4개 필요합니다.')
            pictures = [target] + random.sample([p for p in pool if p['id'] != target['id']], 3)
            # 이름과 카테고리를 보기에서 숨깁니다.
            choices = [{'id': p['id'], 'illustration': p['illustration']} for p in pictures]
            correct_id = target['id']
        else:
            choices = []
            correct_id = target['id']
        random.shuffle(choices)
        allowed = [p['id'] for p in pool] if mode == 'pos' else [o['id'] for o in choices]
        question_id = str(uuid.uuid4())
        db.execute('INSERT INTO questions(id,mode,product_id,options,correct_answer_id) VALUES(?,?,?,?,?)',
                   (question_id, mode, target['id'], json.dumps(allowed), correct_id))
    return {'id': question_id, 'mode': mode, 'is_sample': True,
            'illustration': None if mode in ('delivery', 'similar-photo') else target['illustration'],
            'prompt_name': target['name'] if mode in ('delivery', 'similar-photo') else None,
            'options': choices}

def grade_answer(question_id, selected_id, elapsed_ms):
    with connect() as db:
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
        if row['mode'] == 'pos':
            from .pos import catalog
            correct_product = next((p for p in catalog(db)['products'] if p['id'] == row['product_id']), correct_product)
    correct = bool(saved['is_correct'])
    messages = {
        'category': ('카테고리 정답! 상품 위치를 잘 기억했어요.', '카테고리 실수! 다른 진열대에서 찾고 있었어요.'),
        'name': ('상품명 정답! 비슷한 이름도 정확히 구분했어요.', '상품명 실수! 비슷한 빵과 헷갈렸어요.'),
        'similar-photo': ('상품 사진 정답! 비슷한 빵도 정확히 구분했어요.', '상품 사진 실수! 이름에 맞는 빵을 다시 확인해요.'),
        'delivery': ('배달 성공! 손님이 기뻐해요.', '배달 실수! 손님이 화났어요.'),
        'pos': ('POS 등록 성공! 손님을 기다리게 하지 않았어요.', 'POS 등록 실수! 다른 상품을 찍었어요.'),
    }
    return {'is_correct': correct, 'elapsed_ms': saved['elapsed_ms'], 'selected_id': saved['selected_id'],
            'correct_product': correct_product, 'points': POINTS_PER_CORRECT if correct else 0,
            'feedback': messages[row['mode']][0 if correct else 1]}
