import { useEffect, useRef, useState } from 'react'
import { api, won } from './lib/api'
import type { Category, Product } from './lib/api'
import { BreadArt } from './components/BreadArt'
import { Catalog } from './features/catalog/Catalog'
import { Learning } from './features/learning/Learning'
import { Inventory } from './features/inventory/Inventory'
import { AccountPanel } from './features/account/AccountPanel'
import { StorePanel } from './features/account/StorePanel'
import { StoreAdmin } from './features/account/StoreAdmin'
import { useAccount } from './features/account/useAccount'
import './App.css'

type View = 'catalog' | 'learning' | 'inventory' | 'account' | 'manage' | 'progress' | 'settings'
export default function App() {
  const account = useAccount()
  const [route, setView] = useState<View | 'home'>('home')
  const [preview, setPreview] = useState(false)
  const isAdmin = account.session?.store_role === 'admin'
  const view = route === 'home' ? (isAdmin ? 'manage' : 'catalog') : route
  const adminNavigation = isAdmin && !preview
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
  }, [view, account.session?.user?.id])
  useEffect(() => { if (detail) dialog.current?.showModal() }, [detail])
  function navigate(next: View) {
    if (next === 'account') void account.refresh()
    if (next !== view && (next === 'catalog' || next === 'learning' || next === 'inventory')) setLoading(true)
    setView(next); setLearningKey(k => k + 1); setError('')
  }
  return <>
    <header className="topbar"><a className="brand" href="#" onClick={e => { e.preventDefault(); navigate(adminNavigation ? 'manage' : 'catalog') }}><span className="brand-mark">B</span><span>빵마스터<small>BREAD MASTER</small></span></a><nav aria-label="주 메뉴">{adminNavigation ? <>
      <button className={view === 'manage' ? 'active' : ''} onClick={() => navigate('manage')}>POS 메뉴 관리</button>
      <button className={view === 'progress' ? 'active' : ''} onClick={() => navigate('progress')}>근무자 학습 현황</button>
      <button className={view === 'settings' ? 'active' : ''} onClick={() => navigate('settings')}>매장 설정</button>
      <button onClick={() => { setPreview(true); navigate('catalog') }}>근무자 화면 미리보기</button>
    </> : <><button className={view === 'catalog' ? 'active' : ''} onClick={() => navigate('catalog')}>상품 도감</button><button className={view === 'learning' ? 'active' : ''} onClick={() => navigate('learning')}>상품명 퀴즈</button><button className={view === 'inventory' ? 'active' : ''} onClick={() => navigate('inventory')}>재고 등록</button>{isAdmin && <button onClick={() => { setPreview(false); navigate('manage') }}>관리자 화면으로 돌아가기</button>}</>}</nav>{account.session?.enabled === false ? <span className="demo-tag">로그인 없는 체험</span> : <button className="account-nav" onClick={() => navigate('account')}>{account.loading ? '계정 확인 중…' : account.session?.user ? '내 계정' : '로그인 · 회원가입'}</button>}</header>
    <main className="mx-auto max-w-6xl px-5 py-10 md:px-10">
      <div className="eyebrow">A LITTLE PRACTICE, A BETTER FIRST DAY</div>
      <div className="hero"><div><h1>{view === 'settings' ? '매장 설정' : view === 'progress' ? '근무자 학습 현황' : view === 'manage' ? 'POS 메뉴 관리' : view === 'account' ? '나의 빵마스터, 여기서 시작해요.' : view === 'catalog' ? '빵 하나씩, 자신감 한 겹씩.' : view === 'inventory' ? '재고 등록도, 차근차근 연습해요.' : '연습은 가볍게, 실전은 자신 있게.'}</h1><p>{(view === 'settings' || view === 'progress' || view === 'manage') ? 'POS 메뉴와 근무자 학습 현황을 확인해요.' : view === 'account' ? '계정을 만들고 다음 연습을 준비해요.' : view === 'catalog' ? '상품의 모습과 이름을 익히고, 다음 근무를 가볍게 준비해요.' : view === 'inventory' ? '상품을 고르고 총수량을 수정한 뒤, 등록과 저장을 연습해요.' : '카테고리부터 상품명, 배달과 POS까지. 원하는 단계를 골라 연습해요.'}</p></div><span className="hero-stamp">LEARN<br/>BAKE<br/>REPEAT</span></div>
      {account.loading && route === 'home' ? <p role="status">계정 확인 중…</p> : view === 'settings' && isAdmin ? <div className="account-panel"><StorePanel onManage={() => navigate('manage')}/></div> : (view === 'manage' || view === 'progress') ? <StoreAdmin key={view} tab={view === 'progress' ? 'progress' : 'menu'}/> : view === 'account' ? <AccountPanel user={account.session?.user ?? null} enabled={account.session?.enabled ?? false} loading={account.loading} connectionError={account.error} onRetry={() => void account.refresh()} onSignedIn={user => { setView('home'); setPreview(false); account.signedIn(user) }} onSignedOut={() => { setView('home'); setPreview(false); account.signedOut() }} onPractice={() => { setPreview(isAdmin); navigate('learning') }} onManage={() => { setPreview(false); void account.refresh(); navigate('manage') }}/> : <>
      <div className="sample-notice"><span>교육용 데모</span> {account.session?.user ? '승인된 매장 계정으로 완료한 연습은 학습 현황에 반영돼요.' : '로그인 없이 연습할 수 있어요. 비로그인 연습은 개인 학습 현황에 반영되지 않아요.'}</div>
      <div className="sample-notice"><span>교육용 도감</span> 공식 사이트 상품은 출처 사진과 이름을 사용합니다. 학습 분류는 사용자 제공 POS 카테고리로 통일했습니다. 예시 상품은 별도 표시됩니다.</div>
      {error && <div className="error" role="alert">{error} <button onClick={() => void load()}>다시 연결</button></div>}
      {loading ? <p role="status">상품을 불러오는 중이에요…</p> : products.length > 0 && (view === 'learning' ? <Learning key={learningKey} initialMode={null} products={products} categories={categories}/> : view === 'catalog' ? <Catalog products={products} onDetail={setDetail}/>  : null)}
      {products.length > 0 && <div hidden={view !== 'inventory' || loading}><Inventory accountId={account.session?.user?.id} key={account.session?.user?.id}/></div>}
      </>}
      <footer>빵마스터 · 신입 근무자를 위한 작은 연습실<span>독립적인 교육용 데모 · 실제 POS 연동 없음</span></footer>
    </main>
    <dialog ref={dialog} onClose={() => setDetail(null)} onClick={e => { if (e.target === e.currentTarget) dialog.current?.close() }} aria-labelledby="detail-title">{detail && <><button className="close" onClick={() => dialog.current?.close()} aria-label="상품 상세 닫기">×</button><div className="detail-art"><BreadArt kind={detail.illustration}/></div><span className="demo-tag">{detail.is_sample ? '예시 상품 · 일러스트' : detail.source_url ? 'POS 상품 · 공식 사이트 참고 사진' : '사용자 제공 POS 메뉴'}</span><h2 id="detail-title">{detail.name}</h2><p>{detail.category_name} · {detail.price_known ? won(detail.price) : '가격 미등록'}</p><p>{detail.description}</p>{detail.source_url && <a href={detail.source_url} target="_blank" rel="noreferrer">공식 상품 페이지 ↗</a>}<button className="primary" onClick={() => { dialog.current?.close(); navigate('learning') }}>퀴즈로 연습하기 →</button></>}</dialog>
  </>
}
