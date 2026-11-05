import json
import pytest
from fastapi.testclient import TestClient
from app import db
from app.main import app
from app.quiz_groups import recommend, initialize_store_groups

H = {'X-Bread-Client': 'web'}


@pytest.fixture
def owner(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'quiz.db')
    for key in ('BREAD_DEMO', 'BREAD_ENV', 'RENDER', 'BREAD_PUBLIC_ORIGIN', 'BREAD_AUTH_COOKIE_SECURE'):
        monkeypatch.delenv(key, raising=False)
    with TestClient(app) as client:
        client.post('/api/v1/auth/register', json={'email': 'owner@example.com', 'password': 'bread-practice-2026', 'display_name': '관리자'}, headers=H).raise_for_status()
        store = client.post('/api/v1/stores', json={'name': '연습점'}, headers=H).json()
        yield client, store


def save(client, **changes):
    return client.post('/api/v1/store-admin/quiz-groups/save', json={
        'name': '테스트 그룹', 'product_ids': [1, 3], 'status': 'approved', 'enabled': True, **changes,
    }, headers=H)


def get(client):
    return client.get('/api/v1/store-admin/quiz-groups').json()


def pause_all(client):
    for group in get(client)['groups']:
        save(client, id=group['id'], name=group['name'], product_ids=group['product_ids'], enabled=False)


def test_name_recommendations_ignore_generic_words_and_support_aliases():
    names = ['8입)롤치즈빵', '1/2뜯어먹는롤치즈브레드', '아다지오커피번', '카페모카빵', '모카크림샌드빵', '우유크림빵', '단팥크림빵']
    result = recommend([{'id': i, 'name': name} for i, name in enumerate(names)])
    assert any(ids == {0, 1} and '롤치즈' in reason for _, _, ids, reason in result)
    assert any(ids == {2, 3, 4} and '동의어' in reason for _, _, ids, reason in result)
    assert not any(ids == {5, 6} for _, _, ids, _ in result)
    for names in [('우유생크림빵', '딸기생크림빵'), ('통밀브레드', '치즈브레드')]:
        assert not recommend([{'id': i, 'name': name} for i, name in enumerate(names)])


def test_legacy_groups_migrate_once_even_after_deletion_and_menu_edit(owner):
    client, store = owner
    original = get(client)['groups']
    assert len(original) == 4 and all(g['status'] == 'approved' for g in original)
    group = original[0]
    assert client.post('/api/v1/store-admin/quiz-groups/' + group['id'] + '/delete', json={}, headers=H).status_code == 200
    with db.connect() as conn:
        initialize_store_groups(conn, store['id'])
    assert len(get(client)['groups']) == 3
    menu = client.get('/api/v1/store-admin/menu').json()['products'][0]
    assert client.post('/api/v1/store-admin/menu', json={'product_id': menu['id'], 'category_id': menu['category_id'], 'pos_slot': menu['pos_slot'], 'name': '바뀐 이름', 'price': menu['price'], 'name_group': '주입할 그룹'}, headers=H).status_code == 200
    assert len(get(client)['groups']) == 3
    assert all(g['name'] != '주입할 그룹' for g in get(client)['groups'])
    # Existing stores missing the migration marker are migrated by startup too.
    with db.connect() as conn:
        conn.execute('DELETE FROM store_quiz_group_products')
        conn.execute('DELETE FROM store_quiz_groups')
        conn.execute('DELETE FROM store_quiz_settings')
    db.initialize()
    assert len(get(client)['groups']) == 4
    ids = [g['id'] for g in get(client)['groups']]
    db.initialize()
    assert ids == [g['id'] for g in get(client)['groups']]


def test_recommendations_preserve_edits_dismissals_and_deleted_groups(owner):
    client, _ = owner
    # Add related names with no legacy group to obtain a fresh recommendation.
    for slot, name in enumerate(['롤치즈빵', '뜯어먹는롤치즈브레드'], 20):
        client.post('/api/v1/store-admin/menu', json={'category_id': 1, 'pos_slot': slot, 'name': name, 'price': 1000, 'photo': 'https://example.com/photo.jpg'}, headers=H).raise_for_status()
    data = client.post('/api/v1/store-admin/quiz-groups/recommend', json={}, headers=H).json()
    assert not data['recommendations_stale']
    group = next(g for g in data['groups'] if g['status'] == 'proposed' and '롤치즈' in g['reason'])
    assert not group['enabled']
    assert save(client, id=group['id'], name='직접 수정한 이름', product_ids=group['product_ids'], status='dismissed', enabled=False).status_code == 200
    again = client.post('/api/v1/store-admin/quiz-groups/recommend', json={}, headers=H).json()
    assert next(g for g in again['groups'] if g['id'] == group['id'])['name'] == '직접 수정한 이름'
    assert next(g for g in again['groups'] if g['id'] == group['id'])['status'] == 'dismissed'
    client.post('/api/v1/store-admin/quiz-groups/' + group['id'] + '/delete', json={}, headers=H)
    again = client.post('/api/v1/store-admin/quiz-groups/recommend', json={}, headers=H).json()
    assert not any(set(g['product_ids']) == set(group['product_ids']) for g in again['groups'])


def test_approved_groups_drive_both_directions_and_snapshot_survives_change(owner):
    client, _ = owner
    pause_all(client)
    proposed = save(client, status='proposed', enabled=False).json()['groups'][-1]
    assert client.post('/api/v1/questions', json={'mode': 'name'}, headers=H).status_code == 409
    save(client, id=proposed['id'], product_ids=[1, 3])
    snapshots = []
    for mode in ('name', 'similar-photo'):
        q = client.post('/api/v1/questions', json={'mode': mode}, headers=H).json()
        assert {p['id'] for p in q['options']} == {1, 3}
        with db.connect() as conn:
            correct_id = json.loads(conn.execute('SELECT snapshot FROM store_exercises WHERE id=?', (q['id'],)).fetchone()[0])['correct_id']
        snapshots.append((q, correct_id))
    # Overlapping groups and a larger group must not blend all distractors.
    save(client, name='겹치는 그룹', product_ids=[1, 3, 5, 6, 7, 8])
    q = client.post('/api/v1/questions', json={'mode': 'similar-photo'}, headers=H).json()
    assert 2 <= len(q['options']) <= 4
    for group in get(client)['groups']:
        client.post('/api/v1/store-admin/quiz-groups/' + group['id'] + '/delete', json={}, headers=H)
    assert client.post('/api/v1/questions', json={'mode': 'similar-photo'}, headers=H).status_code == 409
    for q, correct_id in snapshots:
        result = client.post('/api/v1/questions/' + q['id'] + '/answer', json={'selected_id': correct_id, 'elapsed_ms': 1}, headers=H)
        assert result.status_code == 200 and result.json()['is_correct']


def test_photo_requirement_and_store_boundaries(owner):
    client, store = owner
    menu = client.post('/api/v1/store-admin/menu', json={'category_id': 1, 'pos_slot': 20, 'name': '사진 없는 상품', 'price': 1000}, headers=H).json()['products'][-1]
    assert save(client, product_ids=[1, menu['id']]).status_code == 422
    assert save(client, product_ids=[1, menu['id']], enabled=False).status_code == 200
    assert save(client, product_ids=[1, 999999999]).status_code == 422
    assert save(client, product_ids=[1, 1]).status_code == 422
    group = get(client)['groups'][0]
    assert client.post('/api/v1/store-admin/quiz-groups/recommend', json={}).status_code == 403
    with TestClient(app) as other:
        assert other.get('/api/v1/store-admin/quiz-groups').status_code == 403
        other.post('/api/v1/auth/register', json={'email': 'other@example.com', 'password': 'bread-practice-2026', 'display_name': '다른 점주'}, headers=H)
        other.post('/api/v1/stores', json={'name': '다른 매장'}, headers=H)
        assert save(other, id=group['id']).status_code == 404
        assert other.post('/api/v1/store-admin/quiz-groups/' + group['id'] + '/delete', json={}, headers=H).status_code == 404
        # Reuse that account as a worker of the first store to exercise the role gate.
        with db.connect() as conn:
            conn.execute("UPDATE store_memberships SET role='worker',store_id=? WHERE user_id=(SELECT id FROM users WHERE email='other@example.com')", (store['id'],))
        assert other.get('/api/v1/store-admin/quiz-groups').status_code == 403
        assert other.post('/api/v1/store-admin/quiz-groups/recommend', json={}, headers=H).status_code == 403


def test_uploaded_photo_survives_failed_import_and_retry_is_idempotent(owner):
    import io
    from PIL import Image
    client, _ = owner
    buffer = io.BytesIO()
    Image.new('RGB', (80, 60), 'brown').save(buffer, format='PNG')
    photo = client.post('/api/v1/store-admin/photos', content=buffer.getvalue(), headers={**H, 'Content-Type': 'image/png'}).json()['url']
    before = len(client.get('/api/v1/store-admin/menu').json()['products'])
    payload = {'request_id': '11111111-2222-3333-4444-555555555555', 'items': [
        {'name': '사진 있는 새 메뉴', 'price': 2000, 'category_id': 1, 'pos_slot': 20, 'photo': photo},
        {'name': '겹치는 칸 메뉴', 'price': 1000, 'category_id': 1, 'pos_slot': 0},
    ]}
    assert client.post('/api/v1/store-admin/import/save', json=payload, headers=H).status_code == 409
    assert len(client.get('/api/v1/store-admin/menu').json()['products']) == before
    assert client.get(photo).status_code == 200
    payload['items'][1]['pos_slot'] = 21
    result = client.post('/api/v1/store-admin/import/save', json=payload, headers=H)
    assert result.status_code == 200
    assert next(p for p in result.json()['products'] if p['name'] == '사진 있는 새 메뉴')['illustration'] == photo
    assert client.post('/api/v1/store-admin/import/save', json=payload, headers=H).status_code == 200
    assert len(client.get('/api/v1/store-admin/menu').json()['products']) == before + 2


@pytest.mark.parametrize('mode', ['name', 'similar-photo'])
def test_two_product_group_can_complete_five_question_round(owner, mode):
    client, _ = owner
    pause_all(client)
    save(client)
    completed = []
    for _ in range(5):
        response = client.post('/api/v1/questions', json={'mode': mode, 'exclude_ids': completed}, headers=H)
        assert response.status_code == 200
        q = response.json()
        assert {p['id'] for p in q['options']} == {1, 3}
        with db.connect() as conn:
            correct = json.loads(conn.execute('SELECT snapshot FROM store_exercises WHERE id=?', (q['id'],)).fetchone()[0])['correct_id']
        result = client.post('/api/v1/questions/' + q['id'] + '/answer', json={'selected_id': correct, 'elapsed_ms': 1}, headers=H)
        assert result.status_code == 200 and result.json()['points'] == 20
        completed.append(correct)
    assert set(completed[:2]) == {1, 3}
