"""사진에서 확인한 POS 위치. 사이트 분류와 독립적으로 관리합니다."""
from .learning import all_products
CATEGORY_ORDER = ['휴면반죽단과자','휴면반죽기타','휴면반죽식빵','페스츄리','파이류','바게트','도우넛','선물류','날개냉장디저트','소트',
                  '완제단과자','완제기타','완제 식빵','버터케익','본사생크림쉬폰','점포생크림케익','음료','제조음료','점포샌드위치']
def base_catalog(db):
    pool = all_products(db)
    if not any(not p['is_sample'] for p in pool):
        # 예시 데이터만 있는 개발 DB도 사용할 수 있습니다.
        cats = [dict(r) for r in db.execute('SELECT id,name FROM categories ORDER BY id')]
        return {'categories': cats, 'products': [{**p, 'pos_slot': i} for c in cats for i,p in enumerate([p for p in pool if p['category_id']==c['id']])], 'basis':'sample'}
    import json
    from pathlib import Path
    entries = json.loads((Path(__file__).parents[1] / 'data/pos-layout.json').read_text())['entries']
    categories = [{'id':1001+i,'name':name} for i,name in enumerate(CATEGORY_ORDER)]
    category_ids = {c['name']:c['id'] for c in categories}
    products = []
    used = set()
    for entry in entries:
        matches = [p for p in pool if p['name'] == entry['source_name']] if entry['source_name'] else []
        source = matches[0] if len(matches)==1 else None
        category_id = category_ids[entry['category']]
        if source:
            used.add(source['id'])
        products.append({
            **(source or {}),
            'id': source['id'] if source else 1000000 + category_id*100 + entry['slot'],
            'source_product_id': source['id'] if source else None,
            'name_group':entry.get('name_group'),
            'name': entry['name'], 'price':entry['price'] or 0, 'price_known':entry['price'] is not None,
            'category_id':category_id, 'category_name':entry['category'], 'pos_slot':entry['slot'],
            'illustration':source['illustration'] if source else '',
            'source_url': source.get('source_url') if source else None,
            'is_sample':False, 'manual_price':entry['manual_price'],
            'description':'사용자 제공 POS 상품명·가격. 사진은 공식 사이트 참고 이미지입니다.' if source else '사용자 제공 POS 메뉴. 상품 사진 연결은 확인이 필요합니다.',
            'image_status':'reference' if source else 'missing',
        })
    return {'categories':categories,'products':products,'basis':'user-confirmed',
            'unmapped_count':len(pool)-len(used)}

def catalog(db, store_id=None):
    layout = base_catalog(db)
    if store_id is None:
        return layout
    import json
    saved = db.execute('SELECT items FROM store_categories WHERE store_id=?', (store_id,)).fetchone()
    if saved:
        layout = {**layout, 'categories': json.loads(saved['items'])}
    products = {p['id']: p for p in layout['products']}
    categories = {c['id']: c['name'] for c in layout['categories']}
    for row in db.execute('SELECT * FROM store_menus WHERE store_id=?', (store_id,)):
        menu = dict(row)
        menu.pop('store_id')
        product_id = menu.pop('product_id')
        products[product_id] = {
            **products.get(product_id, {}), **menu, 'id': product_id,
            'category_name': categories.get(menu['category_id'], '매장 POS'),
            'is_sample': False, 'price_known': True, 'manual_price': False,
            'description': '매장에서 등록한 POS 메뉴입니다.',
            'image_status': 'reference' if menu['illustration'] else 'missing',
        }
    for product in products.values():
        product['category_name'] = categories.get(product['category_id'], product['category_name'])
    return {**layout, 'products': list(products.values()), 'basis': 'store'}
