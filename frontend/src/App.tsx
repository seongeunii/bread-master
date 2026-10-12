import { useEffect, useRef, useState } from 'react'
import { api, won } from './lib/api'
import type { Category, Product } from './lib/api'
import { BreadArt } from './components/BreadArt'
import { Catalog } from './features/catalog/Catalog'
import { Learning } from './features/learning/Learning'
import { Inventory } from './features/inventory/Inventory'
import './App.css'

type View = 'catalog' | 'learning' | 'inventory'
export default function App() {
  const [view, setView] = useState<View>('catalog')
  const [learningKey, setLearningKey] = useState(0)
  const [products, setProducts] = useState<Product[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [detail, setDetail] = useState<Product | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const dialog = useRef<HTMLDialogElement>(null)
  async function load() {
    setLoading(true); setError('')
    try {
      const [p, c] = await Promise.all([api<Product[]>('/products'), api<Category[]>('/categories')])
      setProducts(p); setCategories(c)
    } catch (e) { setError(e instanceof Error ? e.message : '연결 실패') }
    finally { setLoading(false) }
  }
  useEffect(() => {
    const controller = new AbortController()
    Promise.all([api<Product[]>('/products', undefined, controller.signal), api<Category[]>('/categories', undefined, controller.signal)])
      .then(([p, c]) => { setProducts(p); setCategories(c) })
      .catch(e => { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : '연결 실패') })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [])
  useEffect(() => { if (detail) dialog.current?.showModal() }, [detail])
  function navigate(next: View) {
    setView(next); setLearningKey(k => k + 1); setError('')
  }
  return <>
    <header className="topbar"><a className="brand" href="#" onClick={e => { e.preventDefault(); navigate('catalog') }}><span className="brand-mark">B</span><span>빵마스터<small>BREAD MASTER</small></span></a><nav aria-label="주 메뉴"><button className={view === 'catalog' ? 'active' : ''} onClick={() => navigate('catalog')}>상품 도감</button><button className={view === 'learning' ? 'active' : ''} onClick={() => navigate('learning')}>상품명 퀴즈</button><button className={view === 'inventory' ? 'active' : ''} onClick={() => navigate('inventory')}>재고 등록</button></nav><span className="demo-tag">개발용 데모</span></header>
    <main className="mx-auto max-w-6xl px-5 py-10 md:px-10">
      <div className="eyebrow">A LITTLE PRACTICE, A BETTER FIRST DAY</div>
      <div className="hero"><div><h1>{view === 'catalog' ? '빵 하나씩, 자신감 한 겹씩.' : view === 'inventory' ? '재고 등록도, 차근차근 연습해요.' : '연습은 가볍게, 실전은 자신 있게.'}</h1><p>{view === 'catalog' ? '상품의 모습과 이름을 익히고, 다음 근무를 가볍게 준비해요.' : view === 'inventory' ? '상품을 고르고 총수량을 수정한 뒤, 등록과 저장을 연습해요.' : '카테고리부터 상품명, 배달과 POS까지. 원하는 단계를 골라 연습해요.'}</p></div><span className="hero-stamp">LEARN<br/>BAKE<br/>REPEAT</span></div>
      <div className="sample-notice"><span>교육용 도감</span> 공식 사이트 상품은 출처 사진과 이름을 사용합니다. 분류는 사이트 기준이며 실제 POS와 다를 수 있어요. 예시 상품은 별도 표시됩니다.</div>
      {error && <div className="error" role="alert">{error} <button onClick={() => void load()}>다시 연결</button></div>}
      {loading ? <p role="status">상품을 불러오는 중이에요…</p> : products.length > 0 && (view === 'learning' ? <Learning key={learningKey} initialMode={null} products={products} categories={categories}/> : view === 'catalog' ? <Catalog products={products} onDetail={setDetail}/>  : null)}
      {!loading && products.length > 0 && <div hidden={view !== 'inventory'}><Inventory/></div>}
      <footer>빵마스터 · 신입 근무자를 위한 작은 연습실<span>독립적인 교육용 데모 · 실제 POS 연동 없음</span></footer>
    </main>
    <dialog ref={dialog} onClose={() => setDetail(null)} onClick={e => { if (e.target === e.currentTarget) dialog.current?.close() }} aria-labelledby="detail-title">{detail && <><button className="close" onClick={() => dialog.current?.close()} aria-label="상품 상세 닫기">×</button><div className="detail-art"><BreadArt kind={detail.illustration}/></div><span className="demo-tag">{detail.is_sample ? '예시 상품 · 일러스트' : '파리바게뜨 공식 사이트 상품'}</span><h2 id="detail-title">{detail.name}</h2><p>{detail.category_name} · {detail.price_known ? won(detail.price) : '가격 미등록'}</p><p>{detail.description}</p>{detail.source_url && <a href={detail.source_url} target="_blank" rel="noreferrer">공식 상품 페이지 ↗</a>}<button className="primary" onClick={() => { dialog.current?.close(); navigate('learning') }}>퀴즈로 연습하기 →</button></>}</dialog>
  </>
}
