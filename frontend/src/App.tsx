import { useEffect, useRef, useState } from 'react'
import { api, won } from './lib/api'
import type { Category, Mode, Product, Question, Result } from './lib/api'
import { BreadArt } from './components/BreadArt'
import { ProductCard } from './components/ProductCard'
import './App.css'

type View = 'catalog' | Mode
const views: { id: View; label: string }[] = [{ id: 'catalog', label: '상품 도감' }, { id: 'name', label: '상품명 퀴즈' }, { id: 'pos', label: 'POS 연습' }]
export default function App() {
  const [view, setView] = useState<View>('catalog')
  const [products, setProducts] = useState<Product[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [category, setCategory] = useState(0)
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(0)
  const [detail, setDetail] = useState<Product | null>(null)
  const [question, setQuestion] = useState<Question | null>(null)
  const [result, setResult] = useState<Result | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const start = useRef(0)
  const submitting = useRef(false)
  const dialog = useRef<HTMLDialogElement>(null)
  const generation = useRef(0)

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
    generation.current++; setView(next); setCategory(0); setPage(0); setSearch('')
    setQuestion(null); setResult(null); setError(''); setBusy(false); submitting.current = false
  }
  async function nextQuestion() {
    const current = ++generation.current
    setBusy(true); setError(''); setResult(null); setQuestion(null)
    try {
      const q = await api<Question>('/questions', { mode: view })
      if (current !== generation.current) return
      setQuestion(q); setCategory(0); setPage(0); start.current = performance.now()
    } catch (e) { if (current === generation.current) setError(e instanceof Error ? e.message : '출제 실패') }
    finally { if (current === generation.current) setBusy(false) }
  }
  async function submit(selected_id: number, elapsed_ms: number) {
    if (!question || result || busy || submitting.current) return
    submitting.current = true; setBusy(true); setError('')
    const current = generation.current
    try {
      const r = await api<Result>(`/questions/${question.id}/answer`, { selected_id, elapsed_ms })
      if (current === generation.current) setResult(r)
    } catch (e) { if (current === generation.current) setError(e instanceof Error ? e.message : '제출 실패') }
    finally { if (current === generation.current) { submitting.current = false; setBusy(false) } }
  }
  const filtered = products.filter(p => (!category || p.category_id === category) && (view !== 'catalog' || p.name.includes(search.trim())))
  const pageSize = 4
  const visible = view === 'pos' ? filtered.slice(page * pageSize, (page + 1) * pageSize) : filtered
  return <>
    <header className="topbar"><a className="brand" href="#" onClick={e => { e.preventDefault(); navigate('catalog') }}><span className="brand-mark">B</span><span>빵마스터<small>BREAD MASTER</small></span></a><nav aria-label="주 메뉴">{views.map(v => <button key={v.id} className={view === v.id ? 'active' : ''} onClick={() => navigate(v.id)}>{v.label}</button>)}</nav><span className="demo-tag">개발용 데모</span></header>
    <main className="mx-auto max-w-6xl px-5 py-10 md:px-10">
      <div className="eyebrow">A LITTLE PRACTICE, A BETTER FIRST DAY</div>
      <div className="hero"><div><h1>{view === 'catalog' ? '빵 하나씩, 자신감 한 겹씩.' : view === 'name' ? '사진을 보고 이름을 맞혀요.' : '계산대 앞에서 더 자신 있게.'}</h1><p>{view === 'catalog' ? '상품의 모습과 이름을 익히고, 다음 근무를 가볍게 준비해요.' : view === 'name' ? '네 가지 보기 중 알맞은 상품명을 선택해 보세요.' : '카테고리를 고르고 상품을 찾아보세요. 실제 결제는 진행되지 않아요.'}</p></div><span className="hero-stamp">LEARN<br/>BAKE<br/>REPEAT</span></div>
      <div className="sample-notice"><span>예시 데이터</span> 모든 상품명·가격·분류와 일러스트는 개발용이며 실제 베이커리 정보가 아닙니다.</div>
      {error && <div className="error" role="alert">{error} {loading ? '' : products.length === 0 && <button onClick={() => void load()}>다시 연결</button>}</div>}
      {loading ? <p role="status">상품을 불러오는 중이에요…</p> : products.length > 0 && <>
        {view === 'catalog' ? <><div className="section-heading"><div><h2>상품 도감</h2><p>{filtered.length}개의 예시 상품</p></div><label className="search">상품명 검색<input value={search} onChange={e => setSearch(e.target.value)} placeholder="어떤 빵을 찾고 있나요?" /></label></div></> : <section className="practice-panel"><div><span className="eyebrow">{view === 'pos' ? 'POS PRACTICE' : 'NAME QUIZ'}</span><h2>{question ? '이 상품을 찾아주세요' : '한 문제씩 편하게 연습해요'}</h2><p>정답은 서버에서 확인하고, 선택까지 걸린 시간을 기록해요.</p></div>{question ? <div className="question-art"><BreadArt kind={question.illustration}/><small>예시 일러스트</small></div> : <button className="primary" onClick={() => void nextQuestion()} disabled={busy}>{busy ? '준비 중…' : '연습 시작 →'}</button>}</section>}
        {(view === 'catalog' || (view === 'pos' && question)) && <><div className="categories" aria-label="카테고리"><button className={category === 0 ? 'selected' : ''} onClick={() => { setCategory(0); setPage(0) }} aria-pressed={category === 0}>전체</button>{categories.map(c => <button key={c.id} className={category === c.id ? 'selected' : ''} aria-pressed={category === c.id} onClick={() => { setCategory(c.id); setPage(0) }}>{c.name}</button>)}</div><div className="product-grid">{visible.map(p => <ProductCard key={p.id} product={p} disabled={view === 'pos' && (busy || !!result)} onSelect={p => view === 'catalog' ? setDetail(p) : void submit(p.id, Math.round(performance.now() - start.current))} />)}</div>{!visible.length && <div className="empty">검색 결과가 없어요. 다른 상품명을 입력해 주세요.</div>}{view === 'pos' && <div className="pagination"><button disabled={page === 0} onClick={() => setPage(p => p - 1)}>← 이전</button><span>{page + 1} / {Math.max(1, Math.ceil(filtered.length / pageSize))}</span><button disabled={(page + 1) * pageSize >= filtered.length} onClick={() => setPage(p => p + 1)}>다음 →</button></div>}</>}
        {view === 'name' && question && <div className="choices">{question.options.map((o, i) => <button key={o.id} disabled={busy || !!result} onClick={() => void submit(o.id, Math.round(performance.now() - start.current))}><span>{i + 1}</span>{o.name}</button>)}</div>}
        {result && <section className={`feedback ${result.is_correct ? 'correct' : ''}`} role="status"><div><h2>{result.is_correct ? '정답이에요!' : '다음에는 기억할 수 있어요.'}</h2><p>{result.correct_product.name} · {result.correct_product.category_name}</p><small>선택까지 {(result.elapsed_ms / 1000).toFixed(1)}초</small></div><button className="primary" onClick={() => void nextQuestion()} disabled={busy}>다음 문제 →</button></section>}
      </>}
      <footer>빵마스터 · 신입 근무자를 위한 작은 연습실<span>독립적인 교육용 데모 · 실제 POS 연동 없음</span></footer>
    </main>
    <dialog ref={dialog} onClose={() => setDetail(null)} onClick={e => { if (e.target === e.currentTarget) dialog.current?.close() }} aria-labelledby="detail-title">{detail && <><button className="close" onClick={() => dialog.current?.close()} aria-label="상품 상세 닫기">×</button><div className="detail-art"><BreadArt kind={detail.illustration}/></div><span className="demo-tag">예시 상품 · 일러스트</span><h2 id="detail-title">{detail.name}</h2><p>{detail.category_name} · {won(detail.price)}</p><p>{detail.description}</p><button className="primary" onClick={() => { dialog.current?.close(); navigate('name') }}>퀴즈로 연습하기 →</button></>}</dialog>
  </>
}
