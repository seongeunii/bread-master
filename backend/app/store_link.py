"""Preview public product metadata from supported official product URLs."""
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

import httpx
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from .auth import limit_attempt
from .store_admin import require_admin, router


class LinkInput(BaseModel):
    url: str = Field(min_length=1, max_length=2048)


def supported_url(value):
    try:
        parsed = urlsplit(value)
    except ValueError:
        raise HTTPException(422, '올바른 공식 상품 링크를 입력해 주세요.')
    path = unquote(parsed.path)
    if (parsed.scheme != 'https' or parsed.netloc != 'www.paris.co.kr'
            or parsed.query or parsed.fragment or '\\' in path
            or not path.startswith('/product/') or len(path.strip('/').split('/')) != 2
            or any(part in ('.', '..') for part in path.split('/'))):
        raise HTTPException(422, '파리바게뜨 공식 상품 상세 링크(https://www.paris.co.kr/product/…)를 입력해 주세요.')
    return value


class ProductMetadata(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.name = ''
        self.in_name = False

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        if tag == 'meta':
            self.meta[attributes.get('property', '')] = attributes.get('content', '')
        if tag == 'h1' and 'product-name' in attributes.get('class', '').split():
            self.in_name = True

    def handle_endtag(self, tag):
        if tag == 'h1':
            self.in_name = False

    def handle_data(self, data):
        if self.in_name:
            self.name += data


def parse_product(html, url):
    parser = ProductMetadata()
    parser.feed(html)
    name = parser.name.strip()
    image = parser.meta.get('og:image', '')
    try:
        image_url = urlsplit(image)
    except ValueError:
        raise HTTPException(422, '상품 사진 주소를 읽지 못했어요.')
    if (not name or len(name) > 80 or image_url.scheme != 'https'
            or not image_url.hostname or image_url.username or image_url.password):
        raise HTTPException(422, '상품명과 사진을 읽지 못했어요. 상세 페이지를 확인해 주세요.')
    return {'name': name, 'photo': image, 'source_url': url}


async def fetch_product(url):
    try:
        async with httpx.AsyncClient(timeout=12, follow_redirects=False, trust_env=False) as client:
            async with client.stream('GET', url, headers={'User-Agent': 'BreadMaster/1.0 product-preview'}) as response:
                if response.status_code != 200:
                    raise HTTPException(422, '상품 페이지가 이동했거나 열리지 않아요. 현재 상세 링크를 확인해 주세요.')
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > 2 * 1024 * 1024:
                        raise HTTPException(422, '상품 페이지가 너무 커서 읽지 못했어요.')
                return parse_product(bytes(content).decode('utf-8-sig', errors='replace'), url)
    except httpx.HTTPError:
        raise HTTPException(502, '공식 사이트에 연결하지 못했어요. 잠시 후 다시 시도해 주세요.')


@router.post('/import/link')
async def preview_link(body: LinkInput, scope=Depends(require_admin)):
    url = supported_url(body.url.strip())
    limit_attempt('product-link', scope[1], 30)
    return await fetch_product(url)
