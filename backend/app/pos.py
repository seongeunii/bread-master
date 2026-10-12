"""사진에서 확인한 POS 위치. 사이트 분류와 독립적으로 관리합니다."""
from .learning import all_products
# category, (상품명, 0부터 시작하는 칸 위치). 빈 칸도 위치로 보존합니다.
LAYOUT = [
 ('휴면반죽단과자', [('소보루빵',0),('단팥빵',1),('슈크림빵',2),('단팥소보루',3)]),
 ('휴면반죽기타', [('추억의 소시지빵',5),('양파치즈브레드',6),('발효버터 소금빵',11),('메론크림빵',16)]),
 ('휴면반죽식빵', [('모닝토스트',0),('밤식빵',1),('맘모스브레드',4)]),
 ('페스츄리', [('프렌치크라상',0),('프렌치 뀐아망',1),('갈릭고구마페스츄리',2),('치즈소시지페스츄리',5)]),
 ('파이류', [('사각사각 애플파이',0)]),
 ('바게트', [('프랑스정통바게뜨',0),('플레인 베이글',5),('블랙올리브치즈 베이글',6)]),
 ('도우넛', [('찹쌀도넛',0),('미니 찹쌀도넛',1),('추억의 생도나스',2),('명품 고기잡채고로케',5),
           ('야채감자 샐러드고로케',6),('피자고로케',7),('핫도그도넛',10),('꽈배기도넛',11),
           ('다크초코츄잉스타',15),('케익꽈배기도넛',16),('카레 크로켓',21),('에그샐러드 크로켓',22),('초코쫀득츄러스',23)]),
]
CATEGORY_ORDER = ['휴면반죽단과자','휴면반죽기타','휴면반죽식빵','페스츄리','파이류','바게트','도우넛','선물류','날개냉장디저트','소트',
                  '완제단과자','완제기타','완제 식빵','버터케익','본사생크림쉬폰','점포생크림케익','음료','제조음료','점포샌드위치']
def catalog(db):
    pool = all_products(db)
    if not any(not p['is_sample'] for p in pool):
        # 예시 데이터만 있는 개발 DB도 사용할 수 있습니다.
        cats = [dict(r) for r in db.execute('SELECT id,name FROM categories ORDER BY id')]
        return {'categories': cats, 'products': [{**p, 'pos_slot': i} for c in cats for i,p in enumerate([p for p in pool if p['category_id']==c['id']])], 'basis':'sample'}
    products = []
    categories = []
    entries_by_category = dict(LAYOUT)
    for index,name in enumerate(CATEGORY_ORDER):
        entries = entries_by_category.get(name, [])
        id = 1001 + index
        categories.append({'id':id,'name':name})
        for product_name,slot in entries:
            matches = [p for p in pool if p['name']==product_name]
            # 동명 상품 페이지가 여러 개면 사진만으로 확정할 수 없어 제외합니다.
            if len(matches)==1:
                products.append({**matches[0], 'category_id':id,'category_name':name,'pos_slot':slot})
    return {'categories':categories,'products':products,'basis':'photo-reference', 'unmapped_count':len(pool)-len(products)}
