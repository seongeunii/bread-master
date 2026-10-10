import pytest
from fastapi.testclient import TestClient
from app import db
from app.main import app

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'test.db')
    with TestClient(app) as client:
        yield client

def test_catalog(client):
    assert len(client.get('/api/v1/products').json()) == 12
    rows = client.get('/api/v1/products?category_id=2&q=통밀').json()
    assert len(rows) == 1 and rows[0]['is_sample'] == 1
    assert client.get('/api/v1/products/9999').status_code == 404

def test_server_grading_and_duplicate(client):
    q = client.post('/api/v1/questions', json={'mode': 'name'}).json()
    assert len({o['id'] for o in q['options']}) >= 2
    assert 'product_id' not in q
    with db.connect() as conn:
        target = conn.execute('SELECT product_id FROM questions WHERE id=?', (q['id'],)).fetchone()[0]
    path = f"/api/v1/questions/{q['id']}/answer"
    result = client.post(path, json={'selected_id': target, 'elapsed_ms': 1200})
    assert result.json()['is_correct'] is True
    wrong = next(o['id'] for o in q['options'] if o['id'] != target)
    duplicate = client.post(path, json={'selected_id': wrong, 'elapsed_ms': 3000})
    assert duplicate.json()['is_correct'] is True
    assert duplicate.json()['elapsed_ms'] == 1200
    with db.connect() as conn:
        assert conn.execute('SELECT COUNT(*) FROM answers').fetchone()[0] == 1

def test_invalid_and_wrong_pos_answer(client):
    q = client.post('/api/v1/questions', json={'mode': 'pos'}).json()
    path = f"/api/v1/questions/{q['id']}/answer"
    assert client.post(path, json={'selected_id': 9999, 'elapsed_ms': 1}).status_code == 422
    assert client.post(path, json={'selected_id': 1, 'elapsed_ms': -1}).status_code == 422
    with db.connect() as conn:
        target = conn.execute('SELECT product_id FROM questions WHERE id=?', (q['id'],)).fetchone()[0]
    result = client.post(path, json={'selected_id': 2 if target == 1 else 1, 'elapsed_ms': 2100}).json()
    assert result['is_correct'] is False
    assert result['correct_product']['id'] == target
    assert client.post('/api/v1/questions/missing/answer', json={'selected_id': 1, 'elapsed_ms': 1}).status_code == 404

@pytest.mark.parametrize('mode', ['category', 'name', 'delivery', 'pos'])
def test_five_question_round_and_mode_payload(client, mode):
    seen = []
    for _ in range(5):
        q = client.post('/api/v1/questions', json={'mode': mode, 'exclude_ids': seen}).json()
        with db.connect() as conn:
            row = conn.execute('SELECT * FROM questions WHERE id=?', (q['id'],)).fetchone()
            target = conn.execute('SELECT * FROM products WHERE id=?', (row['product_id'],)).fetchone()
            if mode == 'name':
                option_ids = [o['id'] for o in q['options']]
                groups = [conn.execute('SELECT name_group FROM products WHERE id=?', (id,)).fetchone()[0] for id in option_ids]
                assert len(option_ids) >= 2 and all(g == target['name_group'] for g in groups)
        assert target['id'] not in seen
        seen.append(target['id'])
        if mode == 'delivery':
            assert q['prompt_name'] == target['name'] and q['illustration'] is None
            assert len(q['options']) == 4
            assert all('name' not in option and 'category_id' not in option for option in q['options'])
        else:
            assert q['prompt_name'] is None and q['illustration'] == target['illustration']
        result = client.post(f"/api/v1/questions/{q['id']}/answer", json={'selected_id': row['correct_answer_id'], 'elapsed_ms': 1000}).json()
        assert result['is_correct'] and result['points'] == 20
    assert len(set(seen)) == 5

def test_category_uses_category_id_not_product_id(client, monkeypatch):
    from app import learning
    monkeypatch.setattr(learning.random, 'choice', lambda pool: pool[-1])
    q = client.post('/api/v1/questions', json={'mode': 'category'}).json()
    with db.connect() as conn:
        row = conn.execute('SELECT * FROM questions WHERE id=?', (q['id'],)).fetchone()
        assert row['product_id'] == 12 and row['correct_answer_id'] == 1
    result = client.post(f"/api/v1/questions/{q['id']}/answer", json={'selected_id': 1, 'elapsed_ms': 1000}).json()
    assert result['is_correct'] and result['points'] == 20

def test_delivery_mistake_and_repeated_score(client):
    q = client.post('/api/v1/questions', json={'mode': 'delivery'}).json()
    with db.connect() as conn:
        target = conn.execute('SELECT product_id FROM questions WHERE id=?', (q['id'],)).fetchone()[0]
    wrong = next(o['id'] for o in q['options'] if o['id'] != target)
    path = f"/api/v1/questions/{q['id']}/answer"
    result = client.post(path, json={'selected_id': wrong, 'elapsed_ms': 1000, 'points': 1000}).json()
    assert result['points'] == 0 and result['feedback'] == '배달 실수! 손님이 화났어요.'
    repeat = client.post(path, json={'selected_id': target, 'elapsed_ms': 2000}).json()
    assert repeat == result

def test_initialize_preserves_existing_records(client):
    q = client.post('/api/v1/questions', json={'mode': 'pos'}).json()
    with db.connect() as conn:
        conn.execute('UPDATE questions SET correct_answer_id=NULL WHERE id=?', (q['id'],))
        target = conn.execute('SELECT product_id FROM questions WHERE id=?', (q['id'],)).fetchone()[0]
    db.initialize()
    db.initialize()
    result = client.post(f"/api/v1/questions/{q['id']}/answer", json={'selected_id': target, 'elapsed_ms': 1000})
    assert result.json()['is_correct'] is True
    assert len(client.get('/api/v1/products').json()) == 12
