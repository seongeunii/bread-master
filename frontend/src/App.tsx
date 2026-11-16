import { useEffect, useRef, useState } from 'react'
import { api, won } from './lib/api'
import type { Category, Product } from './lib/api'
import { BreadArt } from './components/BreadArt'
import { Catalog } from './features/catalog/Catalog'
import { Learning } from './features/learning/Learning'
import { Assessment } from './features/learning/Assessment'
import { Inventory } from './features/inventory/Inventory'
import { AccountPanel } from './features/account/AccountPanel'
import { StorePanel } from './features/account/StorePanel'
import { QuizManager } from './features/account/QuizManager'
import { StoreAdmin } from './features/account/StoreAdmin'
import { useAccount } from './features/account/useAccount'
import './App.css'

type View = 'catalog' | 'learning' | 'inventory' | 'account' | 'manage' | 'progress' | 'settings' | 'quiz-manage' | 'assessment'
export default function App() {
  const account = useAccount()
  if (account.loading) return <main className="account-panel"><p role="status">계정과 공간을 확인하고 있어요…</p></main>
  return <WorkspaceApp key={`${account.session?.user?.id ?? 'guest'}:${account.session?.workspace?.id ?? 'none'}`} account={account}/>
}

function WorkspaceApp({ account }: { account: ReturnType<typeof useAccount> }) {
  const [route, setView] = useState<View | 'home'>('home')
  const [preview, setPreview] = useState(false)
  const space = account.session?.workspace
  const personal = space?.kind === 'personal'
  const canManage = space?.role === 'admin' || space?.role === 'owner'
  const isAdmin = space?.role === 'admin'
  const isWorker = account.session?.store_role === 'worker'
  const needsSpace = !!account.session?.user && !space
  const view = needsSpace || account.error ? 'account' : route === 'home' ? (isAdmin ? 'manage' : 'catalog') : route
  const adminNavigation = isAdmin && !preview
  const [learningKey, setLearningKey] = useState(0)
  const [products, setProducts] = useState<Product[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [readiness, setReadiness] = useState<{ photo_count: number; similar_ready: boolean }>()
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
    if (needsSpace || account.error) return () => controller.abort()
    Promise.all([api<Product[]>('/products', undefined, controller.signal), api<Category[]>('/categories', undefined, controller.signal), space ? api<{ photo_count: number; similar_ready: boolean }>('/workspaces/readiness', undefined, controller.signal) : Promise.resolve(undefined)])
      .then(([p, c, ready]) => { if (!controller.signal.aborted) { setProducts(p); setCategories(c); setReadiness(ready) } })
      .catch(e => { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : '연결 실패') })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [view, account.session?.user?.id, needsSpace, account.error, space])
  useEffect(() => { if (detail) dialog.current?.showModal() }, [detail])
  function navigate(next: View) {
    if (next !== view && ['manage', 'quiz-manage', 'learning', 'inventory'].includes(view)
      && !window.confirm('입력이나 연습을 저장·종료했는지 확인해 주세요. 다른 화면으로 이동할까요?')) return
    if (next !== view && (next === 'catalog' || next === 'learning' || next === 'inventory')) setLoading(true)
    setView(next); setLearningKey(k => k + 1); setError('')
  }
  const [switching, setSwitching] = useState(false)
  async function switchSpace(id: string) {
    if (switching || id === space?.id) return
    if (!window.confirm('진행 중인 입력이나 연습을 저장·종료했는지 확인해 주세요. 다른 공간으로 이동할까요?')) return
    setSwitching(true)
    try { await api('/workspaces/select', { workspace_id: id }); await account.refresh() }
    catch (err) { setError(err instanceof Error ? err.message : '공간 전환에 실패했어요.') }
    finally { setSwitching(false) }
  }
  return <>
    {switching && <div className="workspace-overlay" role="status">공간을 전환하고 있어요…</div>}
    <header className="topbar"><a className="brand" href="#" onClick={e => { e.preventDefault(); navigate(adminNavigation ? 'manage' : 'catalog') }}><span className="brand-mark">B</span><span>빵마스터<small>BREAD MASTER</small></span></a>{account.session?.user && <label className="workspace-switch">사용 공간<select disabled={switching} aria-label="사용 공간" value={space?.id ?? ''} onChange={event => { void switchSpace(event.target.value) }}><option value="" disabled>공간을 선택하세요</option>{account.session.workspaces.map(item => <option key={item.id} value={item.id}>{item.name} · {item.kind === 'personal' ? '개인 연습' : item.role === 'admin' ? '매장 관리자' : '매장 근무자'}</option>)}</select></label>}<nav aria-label="주 메뉴">{adminNavigation ? <>
      <button className={view === 'manage' ? 'active' : ''} onClick={() => navigate('manage')}>POS 메뉴 관리</button>
      <button className={view === 'quiz-manage' ? 'active' : ''} onClick={() => navigate('quiz-manage')}>퀴즈 관리</button>
      <button className={view === 'progress' ? 'active' : ''} onClick={() => navigate('progress')}>근무자 학습 현황</button>
      <button className={view === 'settings' ? 'active' : ''} onClick={() => navigate('settings')}>매장 설정</button>
      <button onClick={() => { setPreview(true); navigate('catalog') }}>근무자 화면 미리보기</button>
    </> : <><button className={view === 'catalog' ? 'active' : ''} onClick={() => navigate('catalog')}>상품 도감</button><button className={view === 'learning' ? 'active' : ''} onClick={() => navigate('learning')}>상품명 퀴즈</button>{personal && <><button className={view === 'manage' ? 'active' : ''} onClick={() => navigate('manage')}>내 POS 관리</button><button className={view === 'quiz-manage' ? 'active' : ''} onClick={() => navigate('quiz-manage')}>퀴즈 관리</button></>}{isWorker && <button className={view === 'assessment' ? 'active' : ''} onClick={() => navigate('assessment')}>업무 평가</button>}<button className={view === 'inventory' ? 'active' : ''} onClick={() => navigate('inventory')}>재고 등록</button>{isAdmin && <button onClick={() => { setPreview(false); navigate('manage') }}>관리자 화면으로 돌아가기</button>}</>}</nav>{account.session?.enabled === false ? <span className="demo-tag">로그인 없는 체험</span> : <button className="account-nav" onClick={() => navigate('account')}>{account.loading ? '계정 확인 중…' : account.session?.user ? '내 계정' : '로그인 · 회원가입'}</button>}</header>
    <main className="mx-auto max-w-6xl px-5 py-10 md:px-10">
      {error && ['account', 'manage', 'settings', 'progress', 'quiz-manage'].includes(view) && <p role="alert" className="account-error">{error}</p>}
      <div className="eyebrow">A LITTLE PRACTICE, A BETTER FIRST DAY</div>
      <div className="hero"><div><h1>{view === 'assessment' ? '업무 평가' : view === 'quiz-manage' ? '퀴즈 관리' : view === 'settings' ? '매장 설정' : view === 'progress' ? '근무자 학습 현황' : view === 'manage' ? (personal ? '내 POS 관리' : 'POS 메뉴 관리') : view === 'account' ? '나의 빵마스터, 여기서 시작해요.' : view === 'catalog' ? '빵 하나씩, 자신감 한 겹씩.' : view === 'inventory' ? '재고 등록도, 차근차근 연습해요.' : '연습은 가볍게, 실전은 자신 있게.'}</h1><p>{view === 'assessment' ? '매장 상품을 얼마나 익혔는지 확인해요.' : view === 'quiz-manage' ? '헷갈리는 상품 그룹을 구성하고 퀴즈 출제를 관리해요.' : (view === 'settings' || view === 'progress' || view === 'manage') ? 'POS 메뉴와 근무자 학습 현황을 확인해요.' : view === 'account' ? '계정을 만들고 다음 연습을 준비해요.' : view === 'catalog' ? '상품의 모습과 이름을 익히고, 다음 근무를 가볍게 준비해요.' : view === 'inventory' ? '상품을 고르고 총수량을 수정한 뒤, 등록과 저장을 연습해요.' : '카테고리부터 상품명, 배달과 POS까지. 원하는 단계를 골라 연습해요.'}</p></div><span className="hero-stamp">LEARN<br/>BAKE<br/>REPEAT</span></div>
      {account.loading && route === 'home' ? <p role="status">계정 확인 중…</p> : view === 'assessment' ? (isWorker ? <Assessment key={account.session?.user?.id}/> : <p>승인된 근무자 계정으로 이용해 주세요.</p>) : view === 'quiz-manage' && canManage ? <QuizManager/> : view === 'settings' && isAdmin ? <div className="account-panel"><StorePanel onChanged={() => account.refresh()} onManage={() => navigate('manage')}/></div> : (view === 'manage' || view === 'progress') ? <StoreAdmin key={view} tab={view === 'progress' ? 'progress' : 'menu'}/> : view === 'account' ? <AccountPanel session={account.session} onWorkspaceChanged={() => account.refresh()} user={account.session?.user ?? null} enabled={account.session?.enabled ?? false} loading={account.loading} connectionError={account.error} onRetry={() => { void account.refresh().catch(() => {}) }} onSignedIn={user => { setView('home'); setPreview(false); account.signedIn(user) }} onSignedOut={() => { setView('home'); setPreview(false); account.signedOut() }} onPractice={() => { setPreview(isAdmin); navigate('learning') }} onManage={() => { setPreview(false); navigate('manage') }}/> : <>
      <div className="sample-notice"><span>교육용 데모</span> {account.session?.user ? `${space?.name ?? '선택한 공간'}에서 완료한 연습은 이 공간의 학습 현황에 반영돼요.` : '로그인 없이 연습할 수 있어요. 비로그인 연습은 개인 학습 현황에 반영되지 않아요.'}</div>
      <div className="sample-notice"><span>교육용 도감</span> 공식 사이트 상품은 출처 사진과 이름을 사용합니다. 학습 분류는 사용자 제공 POS 카테고리로 통일했습니다. 예시 상품은 별도 표시됩니다.</div>
      {error && <div className="error" role="alert">{error} <button onClick={() => void load()}>다시 연결</button></div>}
      {!loading && !products.length && space && !error && <section className="workspace-empty"><h2>아직 등록한 상품이 없어요</h2><p>{canManage ? '메뉴와 POS 사진을 등록해 나만의 연습을 준비하세요.' : '매장 관리자가 상품을 등록하면 연습을 시작할 수 있어요.'}</p>{canManage && <button className="primary" onClick={() => navigate('manage')}>메뉴 등록하기</button>}</section>}
      {loading ? <p role="status">상품을 불러오는 중이에요…</p> : products.length > 0 && (view === 'learning' ? <Learning key={learningKey} initialMode={null} products={products} categories={categories} readiness={readiness} onManage={canManage ? () => navigate('manage') : undefined}/> : view === 'catalog' ? <Catalog products={products} onDetail={setDetail}/>  : null)}
      {products.length > 0 && <div hidden={view !== 'inventory' || loading}><Inventory accountId={space ? `${account.session?.user?.id}:${space.id}` : undefined} key={space?.id ?? 'guest'}/></div>}
      </>}
      <footer>빵마스터 · 신입 근무자를 위한 작은 연습실<span>독립적인 교육용 데모 · 실제 POS 연동 없음</span></footer>
    </main>
    <dialog ref={dialog} onClose={() => setDetail(null)} onClick={e => { if (e.target === e.currentTarget) dialog.current?.close() }} aria-labelledby="detail-title">{detail && <><button className="close" onClick={() => dialog.current?.close()} aria-label="상품 상세 닫기">×</button><div className="detail-art"><BreadArt kind={detail.illustration}/></div><span className="demo-tag">{detail.is_sample ? '예시 상품 · 일러스트' : detail.source_url ? 'POS 상품 · 공식 사이트 참고 사진' : '사용자 제공 POS 메뉴'}</span><h2 id="detail-title">{detail.name}</h2><p>{detail.category_name} · {detail.price_known ? won(detail.price) : '가격 미등록'}</p><p>{detail.description}</p>{detail.source_url && <a href={detail.source_url} target="_blank" rel="noreferrer">공식 상품 페이지 ↗</a>}<button className="primary" onClick={() => { dialog.current?.close(); navigate('learning') }}>퀴즈로 연습하기 →</button></>}</dialog>
  </>
}
