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

@pytest.mark.parametrize('mode', ['category', 'name', 'similar-photo', 'delivery', 'pos'])
def test_five_question_round_and_mode_payload(client, mode):
    seen = []
    for _ in range(5):
        q = client.post('/api/v1/questions', json={'mode': mode, 'exclude_ids': seen}).json()
        with db.connect() as conn:
            row = conn.execute('SELECT * FROM questions WHERE id=?', (q['id'],)).fetchone()
            target = conn.execute('SELECT * FROM products WHERE id=?', (row['product_id'],)).fetchone()
            if mode in ('name', 'similar-photo'):
                option_ids = [o['id'] for o in q['options']]
                groups = [conn.execute('SELECT name_group FROM products WHERE id=?', (id,)).fetchone()[0] for id in option_ids]
                assert len(option_ids) >= 2 and all(g == target['name_group'] for g in groups)
        assert target['id'] not in seen
        seen.append(target['id'])
        if mode in ('delivery', 'similar-photo'):
            assert q['prompt_name'] == target['name'] and q['illustration'] is None
            assert len(q['options']) == (4 if mode == 'delivery' else len(option_ids))
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

def test_inventory_save_total_and_isolation(client):
    practice = client.post('/api/v1/inventory-practices').json()
    other = client.post('/api/v1/inventory-practices').json()
    products = practice['products']
    category = products[0]['category_id']
    items = [{'product_id': p['id'], 'quantity': 3} for p in products if p['category_id'] == category]
    items[0]['quantity'] = 7
    items[-1]['quantity'] = 0
    path = f"/api/v1/inventory-practices/{practice['id']}"
    payload = {'category_id': category, 'items': items}
    assert client.post(path + '/categories', json=payload).json() == payload
    restored = client.get(path).json()
    assert restored['saved_categories'][str(category)] == payload
    assert client.get(f"/api/v1/inventory-practices/{other['id']}").json()['saved_categories'] == {}
    assert client.get('/api/v1/products').json() == sorted([{k: v for k, v in p.items() if k not in ('quantity', 'pos_slot')} for p in products], key=lambda p: p['id'])
    assert client.get('/api/v1/inventory-practices/missing').status_code == 404

@pytest.mark.parametrize('invalid', [-1, 1.5, True, '7', 10000])
def test_inventory_rejects_invalid_quantity(client, invalid):
    practice = client.post('/api/v1/inventory-practices').json()
    category = practice['products'][0]['category_id']
    items = [{'product_id': p['id'], 'quantity': 3} for p in practice['products'] if p['category_id'] == category]
    items[0]['quantity'] = invalid
    path = f"/api/v1/inventory-practices/{practice['id']}/categories"
    assert client.post(path, json={'category_id': category, 'items': items}).status_code == 422

def test_inventory_rejects_incomplete_duplicate_and_other_category(client):
    practice = client.post('/api/v1/inventory-practices').json()
    category = practice['products'][0]['category_id']
    items = [{'product_id': p['id'], 'quantity': 3} for p in practice['products'] if p['category_id'] == category]
    path = f"/api/v1/inventory-practices/{practice['id']}/categories"
    outside = next(p for p in practice['products'] if p['category_id'] != category)
    for invalid in [items[:-1], items + [items[0]], items[:-1] + [{'product_id': outside['id'], 'quantity': 3}]]:
        assert client.post(path, json={'category_id': category, 'items': invalid}).status_code == 422
    assert client.get(f"/api/v1/inventory-practices/{practice['id']}").json()['saved_categories'] == {}

def test_advanced_delivery_quantity_and_duplicate_submit(client, monkeypatch):
    from app import delivery
    monkeypatch.setattr(delivery, 'order_quantity', lambda: 3)
    order = client.post('/api/v1/delivery-orders', json={}).json()
    assert len(order['options']) == 12
    assert len({p['id'] for p in order['options']}) == 12
    assert all('name' not in p for p in order['options'])
    assert 2 <= len(order['lines']) <= 4
    assert all(line['quantity'] == 3 for line in order['lines'])
    payload = {'items': [{'product_id': l['product_id'], 'quantity': l['quantity']} for l in order['lines']], 'elapsed_ms': 4000}
    path = f"/api/v1/delivery-orders/{order['id']}/submit"
    result = client.post(path, json=payload).json()
    assert result['is_correct'] and result['points'] == 20 and not result['differences']
    assert client.post(path, json={'items': [], 'elapsed_ms': 9000}).json() == result

def test_advanced_delivery_missing_extra_and_wrong_counts(client):
    order = client.post('/api/v1/delivery-orders', json={}).json()
    expected = {l['product_id']: l['quantity'] for l in order['lines']}
    first = order['lines'][0]['product_id']
    extra = next(p['id'] for p in order['options'] if p['id'] not in expected)
    cart = {first: expected[first] + 1, extra: 1}
    result = client.post(f"/api/v1/delivery-orders/{order['id']}/submit", json={
        'items': [{'product_id': id, 'quantity': n} for id, n in cart.items()], 'elapsed_ms': 20
    }).json()
    assert not result['is_correct'] and result['points'] == 0
    assert result['feedback'] == '배달 실수! 손님이 화났어요.'
    diffs = {d['product_id']: d for d in result['differences']}
    assert diffs[first]['actual'] == expected[first] + 1
    assert diffs[extra]['expected'] == 0
    assert all(diffs[id]['actual'] == 0 for id in expected if id != first)

@pytest.mark.parametrize('items', [
    [{'product_id': 9999, 'quantity': 1}],
    [{'product_id': 1, 'quantity': 1}, {'product_id': 1, 'quantity': 2}],
    [{'product_id': 1, 'quantity': -1}],
    [{'product_id': 1, 'quantity': 1.5}],
    [{'product_id': 1, 'quantity': True}],
])
def test_advanced_delivery_invalid_cart(client, items):
    order = client.post('/api/v1/delivery-orders', json={}).json()
    assert client.post(f"/api/v1/delivery-orders/{order['id']}/submit",
                       json={'items': items, 'elapsed_ms': 1}).status_code == 422

def test_delivery_quantity_weights(monkeypatch):
    from app import delivery
    calls = []
    def choices(values, weights, k):
        calls.append((values, weights, k))
        return [1]
    monkeypatch.setattr(delivery.random, 'choices', choices)
    assert delivery.order_quantity() == 1
    assert calls == [([1, 2, 3, 4], [80, 16, 3, 1], 1)]

def test_official_catalog_import_is_idempotent_and_preserves_answers(client, tmp_path, monkeypatch):
    import json
    from scripts import import_paris
    monkeypatch.setattr(import_paris, 'DB_PATH', db.DB_PATH)
    q = client.post('/api/v1/questions', json={'mode': 'pos'}).json()
    manifest = tmp_path / 'products.json'
    manifest.write_text(json.dumps({'count': 1, 'products': [
        {'name': '공식 테스트 빵', 'source_url': 'https://www.paris.co.kr/product/test/',
         'image_url': 'https://www.paris.co.kr/test.png', 'site_categories': ['건강빵']}]}))
    assert import_paris.import_manifest(manifest) == 1
    assert import_paris.import_manifest(manifest) == 1
    rows = client.get('/api/v1/products').json()
    assert len(rows) == 1 and rows[0]['is_sample'] == 0 and rows[0]['price_known'] == 0
    with db.connect() as conn:
        assert conn.execute('SELECT COUNT(*) FROM products').fetchone()[0] == 13
        correct = conn.execute('SELECT correct_answer_id FROM questions WHERE id=?', (q['id'],)).fetchone()[0]
    # 공식 데이터 등록 전의 문제도 정답 상품을 찾을 수 있어야 합니다.
    assert client.post(f"/api/v1/questions/{q['id']}/answer", json={'selected_id':correct,'elapsed_ms':1}).json()['is_correct']
    assert [c['name'] for c in client.get('/api/v1/categories').json()] == ['건강빵']


def test_pos_mapping_is_independent_and_preserves_blank_slots(client):
    with db.connect() as conn:
        conn.execute("INSERT INTO products(name,price,category_id,illustration,description,is_sample) VALUES('フレンチ',0,1,'test','',0)")
        conn.execute("INSERT INTO products(name,price,category_id,illustration,description,is_sample) VALUES('프렌치크라상',0,1,'test','',0)")
        conn.execute("INSERT INTO products(name,price,category_id,illustration,description,is_sample) VALUES('치즈소시지페스츄리',0,1,'test','',0)")
    pos = client.get('/api/v1/pos-catalog').json()
    assert pos['basis'] == 'user-confirmed'
    assert pos['unmapped_count'] == 1
    matched = [p for p in pos['products'] if p.get('source_product_id') is not None]
    assert {p['pos_slot'] for p in matched} == {0, 5}
    assert all(p['category_name'] == '페스츄리' for p in matched)
    assert all(p['category_id'] != 1 for p in matched)
    question = client.post('/api/v1/questions', json={'mode':'pos'}).json()
    with db.connect() as conn:
        target = conn.execute('SELECT product_id FROM questions WHERE id=?', (question['id'],)).fetchone()[0]
    assert target in {p['id'] for p in pos['products']}
    practice = client.post('/api/v1/inventory-practices').json()
    assert {p['category_id'] for p in practice['products']} == {p['category_id'] for p in pos['products']}

def test_pos_checkout_checks_entire_cart(client):
    order = client.post('/api/v1/delivery-orders/pos/start', json={}).json()
    assert 1 <= len(order['lines']) <= 3
    assert len(order['options']) == 12
    correct = [{'product_id': l['product_id'], 'quantity': l['quantity']} for l in order['lines']]
    path = f"/api/v1/delivery-orders/pos/{order['id']}/submit"
    result = client.post(path, json={'items':correct,'elapsed_ms':500}).json()
    assert result['is_correct'] and result['points'] == 20
    assert '결제 연습 성공' in result['feedback']
    assert client.post(path,json={'items':[],'elapsed_ms':900}).json() == result

def test_pos_checkout_rejects_extra_product_as_wrong_answer(client):
    order = client.post('/api/v1/delivery-orders/pos/start',json={}).json()
    ids = {line['product_id'] for line in order['lines']}
    wrong = next(o['id'] for o in order['options'] if o['id'] not in ids)
    cart = [{'product_id':l['product_id'],'quantity':l['quantity']} for l in order['lines']]
    cart.append({'product_id':wrong,'quantity':1})
    result=client.post(f"/api/v1/delivery-orders/pos/{order['id']}/submit",json={'items':cart,'elapsed_ms':100}).json()
    assert not result['is_correct'] and result['points']==0
    assert result['differences'][0]['actual']==1 and result['differences'][0]['expected']==0

def test_user_pos_names_prices_and_positions(client):
    with db.connect() as conn:
        conn.execute("UPDATE products SET is_sample=0 WHERE id=1")
    layout=client.get('/api/v1/pos-catalog').json()
    rows=layout['products']
    assert len(rows)==78
    assert len({(p['category_id'],p['pos_slot']) for p in rows})==78
    by_name={p['name']:p for p in rows}
    assert by_name['감자쫀떡(2개입)']['price']==3900
    assert by_name['정통에그타르트']['pos_slot']==3
    assert by_name['올리브치아바타']['pos_slot']==13
    assert by_name['치즈감자치아바타']['pos_slot']==14
    assert by_name['소보루인생크림빵']['price']==3300
    assert by_name['행)묶음빵']['pos_slot']==19
    assert by_name['빵류']['manual_price'] and not by_name['빵류']['price_known']
    assert by_name['종이쇼핑백']['price']==100 and by_name['종이쇼핑백']['pos_slot']==23
    assert by_name['조각)로스팅호두파이']['illustration']==''
    practice=client.post('/api/v1/inventory-practices',json={}).json()
    assert all(not p['manual_price'] for p in practice['products'])
    assert len(practice['products'])==77
