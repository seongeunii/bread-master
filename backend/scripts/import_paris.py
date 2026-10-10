"""수집한 상품을 중복 없이 등록합니다. 예시 데이터와 기존 학습 기록은 유지."""
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
from app.db import initialize, connect, DB_PATH

def import_manifest(path):
    data = json.loads(Path(path).read_text())
    assert data['count'] == len(data['products'])
    initialize()
    if DB_PATH.exists():
        shutil.copy2(DB_PATH, DB_PATH.with_name('bread.before-paris-' + datetime.now().strftime('%Y%m%d%H%M%S') + '.db'))
    with connect() as db:
        count = 0
        for p in data['products']:
            category = p['site_categories'][0]
            row = db.execute('SELECT id FROM categories WHERE name=?', (category,)).fetchone()
            if not row:
                id = db.execute('SELECT COALESCE(MAX(id),0)+1 FROM categories').fetchone()[0]
                db.execute('INSERT INTO categories(id,name) VALUES(?,?)', (id, category))
            else: id = row['id']
            existing = db.execute('SELECT id FROM products WHERE source_url=?', (p['source_url'],)).fetchone()
            values = (p['name'], id, p['image_url'], '공식 사이트 브레드 상품 · 사이트 분류: ' + ', '.join(p['site_categories']), p['source_url'])
            if existing:
                db.execute('UPDATE products SET name=?,category_id=?,illustration=?,description=?,source_url=? WHERE id=?', values + (existing['id'],))
            else:
                db.execute('INSERT INTO products(name,category_id,illustration,description,source_url,price,is_sample,price_known) VALUES(?,?,?,?,?,0,0,0)', values)
            count += 1
    return count

if __name__ == '__main__':
    print('등록 완료:', import_manifest(Path(__file__).parents[1] / 'data/paris-bread.json'))
