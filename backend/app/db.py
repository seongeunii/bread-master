"""SQLite 연결과 개발용 예시 데이터. 실제 베이커리 상품이 아닙니다."""
import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.environ.get('BREAD_DB_PATH', Path(__file__).parents[1] / 'bread.db'))
SEED = [
    (1, '예시 버터 크루아상', 3200, 1, 'croissant', '겹겹이 접힌 반달 모양의 예시 상품입니다.'),
    (2, '예시 초코 데니시', 3500, 1, 'danish', '초콜릿 줄무늬가 있는 사각형 예시 상품입니다.'),
    (3, '예시 통밀 식빵', 4800, 2, 'loaf', '곡물 무늬가 있는 통밀 식빵 예시입니다.'),
    (4, '예시 우유 식빵', 4500, 2, 'milk', '부드러운 흰 속살을 표현한 식빵 예시입니다.'),
    (5, '예시 소금빵', 2800, 1, 'salt', '길쭉한 모양과 소금 알갱이를 표현한 예시입니다.'),
    (6, '예시 딸기 케이크', 6500, 3, 'cake', '딸기가 올라간 조각 케이크 예시입니다.'),
    (7, '예시 에그 샌드위치', 5900, 4, 'sandwich', '달걀과 채소를 표현한 샌드위치 예시입니다.'),
    (8, '예시 치즈 샌드위치', 6200, 4, 'cheese', '치즈와 채소를 표현한 샌드위치 예시입니다.'),
]

def connect():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys = ON')
    return db

def initialize():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS categories(id INTEGER PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS products(
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, price INTEGER NOT NULL CHECK(price >= 0),
            category_id INTEGER NOT NULL REFERENCES categories(id), illustration TEXT NOT NULL,
            description TEXT NOT NULL, is_sample INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS questions(
            id TEXT PRIMARY KEY, mode TEXT NOT NULL, product_id INTEGER NOT NULL REFERENCES products(id),
            options TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS answers(
            question_id TEXT PRIMARY KEY REFERENCES questions(id), selected_id INTEGER NOT NULL,
            is_correct INTEGER NOT NULL, elapsed_ms INTEGER NOT NULL,
            answered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        ''')
        db.executemany('INSERT OR IGNORE INTO categories VALUES (?, ?)',
                       [(1, '페이스트리'), (2, '식빵'), (3, '케이크'), (4, '샌드위치')])
        db.executemany('INSERT OR IGNORE INTO products(id,name,price,category_id,illustration,description) VALUES(?,?,?,?,?,?)', SEED)
