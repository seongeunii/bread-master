"""공식 사이트 공개 목록을 차례로 수집. 이미지 URL·상품명·출처만 보관."""
import html
import json
import re
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

CATEGORIES = ['식빵', '간식빵', '건강빵', '도넛', '페스츄리/파이']
def collect(category=None):
    rows = {}
    page = 1
    while True:
        args = {'action':'pb_get_product_list', 'cat1':'브레드', 'per_page':12, 'paged':page}
        if category:
            args['cat2'] = category.replace('/', '-')
        url = 'https://www.paris.co.kr/wp-admin/admin-ajax.php?' + urlencode(args)
        with urlopen(url, timeout=30) as response:
            text = response.read().decode('utf-8-sig')
        total = int(re.search(r'data-total-count="(\d+)"', text)[1])
        found = []
        for block in re.findall(r'<li>(.*?)</li>', text, re.S):
            link = re.search(r'<a href="([^"]+)"', block)
            image = re.search(r'<img src="([^"]+)" class="product-tb"', block)
            name = re.search(r'<h3 class="product-name">(.*?)</h3>', block, re.S)
            if not (link and image and name): raise RuntimeError('상품 구조 확인 필요')
            found.append({'name':html.unescape(re.sub('<[^>]+>', '', name[1])).strip(),
                          'source_url':html.unescape(link[1]), 'image_url':html.unescape(image[1])})
        for row in found: rows[row['source_url']] = row
        print(category or '브레드 전체', page, len(rows), '/', total, flush=True)
        if len(rows) == total: return rows
        if not found or page > 100: raise RuntimeError('전체 수집 수량 불일치')
        page += 1
        time.sleep(.15)

if __name__ == '__main__':
    rows = collect()
    for category in CATEGORIES:
        for url in collect(category):
            if url in rows:
                rows[url].setdefault('site_categories', []).append(category)
    for row in rows.values():
        row.setdefault('site_categories', ['브레드 · 미분류'])
    manifest = {'source':'https://www.paris.co.kr/products/?cat1=브레드', 'collected_on':'2026-10-11',
                'count':len(rows), 'products':list(rows.values())}
    target = Path(__file__).parents[1] / 'data/paris-bread.json'
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print('완료', len(rows))
