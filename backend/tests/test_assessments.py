import json

from app import auth, db

from test_quiz_groups import H, owner  # noqa: F401


def register(client, name):
    response = client.post('/api/v1/auth/register', json={
        'email': f'{name}@example.com', 'password': 'bread-practice-2026', 'display_name': name,
    }, headers=H)
    response.raise_for_status()
    return response.json()['id'], client.cookies[auth.COOKIE_NAME]


def switch(client, token=None):
    client.cookies.clear()
    if token:
        client.cookies.set(auth.COOKIE_NAME, token)


def approve_worker(client, owner_token, invite, name):
    switch(client)
    worker_id, worker_token = register(client, name)
    client.post('/api/v1/stores/join', json={'code': invite}, headers=H).raise_for_status()
    switch(client, owner_token)
    client.post(f'/api/v1/stores/requests/{worker_id}/approve', json={}, headers=H).raise_for_status()
    return worker_id, worker_token


def test_assessment_resume_submit_and_store_summary_are_isolated(owner):
    client, store = owner
    owner_token = client.cookies[auth.COOKIE_NAME]
    worker, token = approve_worker(client, owner_token, store['invite_code'], 'worker')
    other_worker, other_token = approve_worker(client, owner_token, store['invite_code'], 'coworker')

    def post(path, body=None):
        return client.post('/api/v1' + path, json=body or {}, headers=H)

    assert post('/assessments/start').status_code == 403
    switch(client)
    assert post('/assessments/start').status_code == 403
    switch(client, token)
    exam = post('/assessments/start').json()
    path = f"/assessments/{exam['id']}"
    assert [q['mode'] for q in exam['questions']] == [
        'category', 'category', 'name', 'name', 'similar-photo',
        'similar-photo', 'delivery', 'delivery', 'pos', 'pos',
    ]
    assert all(question['options'] for question in exam['questions'])
    assert post('/assessments/start').json() == exam
    assert post(path + '/submit').status_code == 409

    with db.connect() as conn:
        keys = dict(conn.execute('SELECT id,correct_id FROM assessment_questions').fetchall())
    for index, question in enumerate(exam['questions']):
        assert 'correct_id' not in question
        answer_path = f"{path}/questions/{question['id']}/answer"
        correct_id = keys[question['id']]
        assert post(f"/questions/{question['id']}/answer", {'selected_id': correct_id, 'elapsed_ms': 100}).status_code == 404
        selected_id = correct_id if index else next(o['id'] for o in question['options'] if o['id'] != correct_id)
        assert post(answer_path, {'selected_id': -999}).status_code == 422
        assert post(answer_path, {'selected_id': selected_id}).json() == {'selected_id': selected_id}

    switch(client, other_token)
    assert post(path + '/submit').status_code == 404
    assert client.get('/api/v1/assessments/store-results', params={'worker_id': worker}).status_code == 403
    switch(client, owner_token)
    assert client.get('/api/v1/assessments/store-results', params={'worker_id': worker}).json()['results'] == []
    switch(client, token)
    db.initialize()
    resumed = client.get('/api/v1/assessments/mine').json()['active']
    assert resumed['id'] == exam['id']
    assert all(question['selected_id'] is not None for question in resumed['questions'])
    result = post(path + '/submit').json()
    assert result['score'] == 90 and result['max_score'] == 100
    assert result['areas'] == {
        'category': {'correct': 1, 'total': 2},
        'photo-to-name': {'correct': 2, 'total': 2},
        'name-to-photo': {'correct': 2, 'total': 2},
        'delivery': {'correct': 2, 'total': 2},
        'pos': {'correct': 2, 'total': 2},
    }
    assert post(path + '/submit').json() == result
    assert post(answer_path, {'selected_id': selected_id}).status_code == 409
    assert client.get('/api/v1/assessments/mine').json()['active'] is None
    assert client.get('/api/v1/store-admin/my-progress').json()['attempts'] == 0

    switch(client, owner_token)
    assert client.get('/api/v1/assessments/store-results', params={'worker_id': worker}).json()['results'] == [result]
    assert client.get('/api/v1/assessments/store-results', params={'worker_id': other_worker}).json()['results'] == []
    assert set(result) == {'id', 'submitted_at', 'policy_version', 'score', 'max_score', 'areas'}
    switch(client)
    register(client, 'another-owner')
    post('/stores', {'name': '다른 연습점'}).raise_for_status()
    assert client.get('/api/v1/assessments/store-results', params={'worker_id': worker}).status_code == 404


def test_mistake_retry_keeps_original_and_reuses_snapshot(owner):
    client, _ = owner
    q = client.post('/api/v1/questions', json={'mode': 'category'}, headers=H).json()
    with db.connect() as conn:
        snapshot = json.loads(conn.execute('SELECT snapshot FROM store_exercises WHERE id=?', (q['id'],)).fetchone()[0])
    wrong_id = next(o['id'] for o in q['options'] if o['id'] != snapshot['correct_id'])
    url = f"/api/v1/questions/{q['id']}/answer"
    assert not client.post(url, json={'selected_id': wrong_id, 'elapsed_ms': 200}, headers=H).json()['is_correct']
    path = '/api/v1/store-admin/my-learning'
    assert client.get(path, params={'mistakes_only': True}).json()['attempts'][0]['can_retry']
    retry = client.post(f"{path}/{q['id']}/retry", json={}, headers=H).json()
    assert retry['id'] != q['id']
    assert {o['id'] for o in q['options']} == {o['id'] for o in retry['options']}
    result = client.post(f"/api/v1/questions/{retry['id']}/answer", json={
        'selected_id': snapshot['correct_id'], 'elapsed_ms': 200,
    }, headers=H).json()
    assert result['is_correct']
    history = client.get(path, params={'mistakes_only': True}).json()
    assert [row['id'] for row in history['attempts']] == [q['id']]
    assert history['by_mode']['category'] == {'attempts': 2, 'correct': 1, 'accuracy': 50}
