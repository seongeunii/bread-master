import { useEffect, useRef, useState } from 'react'
import { api } from '../../lib/api'
import type { Category, InventoryPractice, InventoryProduct, InventorySave } from '../../lib/api'
import { BreadArt } from '../../components/BreadArt'
import './Inventory.css'

type Props = { categories: Category[] }
const STORAGE_KEY = 'bread-master-inventory-practice'
function quantities(practice: InventoryPractice): Record<number, number> {
  const values = Object.fromEntries(practice.products.map(p => [p.id, p.quantity]))
  for (const saved of Object.values(practice.saved_categories)) {
    for (const item of saved.items) values[item.product_id] = item.quantity
  }
  return values
}
export function Inventory({ categories }: Props) {
  const [practice, setPractice] = useState<InventoryPractice | null>(null)
  const [saved, setSaved] = useState<Record<number, number>>({})
  const [registered, setRegistered] = useState<Record<number, number>>({})
  const [category, setCategory] = useState(0)
  const [page, setPage] = useState(0)
  const [selected, setSelected] = useState<InventoryProduct | null>(null)
  const [quantity, setQuantity] = useState('')
  const [busy, setBusy] = useState(false)
  const [restoring, setRestoring] = useState(true)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [unavailable, setUnavailable] = useState(false)
  const inFlight = useRef(false)
  useEffect(() => {
    const controller = new AbortController()
    let id: string | null = null
    try { id = sessionStorage.getItem(STORAGE_KEY) } catch { /* 저장 공간 없이도 연습 가능 */ }
    if (id) {
      api<InventoryPractice>(`/inventory-practices/${id}`, undefined, controller.signal)
        .then(p => { const values = quantities(p); setPractice(p); setSaved(values); setRegistered(values) })
        .catch(e => { if (!controller.signal.aborted) { setError(e instanceof Error ? e.message : '재고 연습을 불러오지 못했어요.'); setUnavailable(true) } })
        .finally(() => { if (!controller.signal.aborted) setRestoring(false) })
    } else {
      // 비동기 초기화로 effect에서 동기 setState를 피합니다.
      Promise.resolve().then(() => { if (!controller.signal.aborted) setRestoring(false) })
    }
    return () => controller.abort()
  }, [])
  async function start() {
    if (inFlight.current) return
    inFlight.current = true; setBusy(true); setError(''); setMessage('')
    try {
      const p = await api<InventoryPractice>('/inventory-practices', {})
      const values = quantities(p)
      setPractice(p); setSaved(values); setRegistered(values); setCategory(0); setSelected(null); setQuantity(''); setPage(0); setUnavailable(false)
      try { sessionStorage.setItem(STORAGE_KEY, p.id) } catch { /* 저장 공간 없이도 연습 가능 */ }
    } catch (e) { setError(e instanceof Error ? e.message : '연습을 시작하지 못했어요.') }
    finally { inFlight.current = false; setBusy(false) }
  }
  const categoryProducts = practice?.products.filter(p => p.category_id === category) ?? []
  const dirty = categoryProducts.some(p => saved[p.id] !== registered[p.id])
  const unregistered = selected !== null && quantity !== String(registered[selected.id])
  const locked = dirty || unregistered
  const validQuantity = /^\d+$/.test(quantity) && Number(quantity) <= 9999
  const pendingCount = categoryProducts.filter(p => saved[p.id] !== registered[p.id]).length

  function selectCategory(id: number) {
    if (busy || id === category) return
    if (locked) { setError('카테고리를 이동하려면 수정한 수량을 등록한 뒤 저장해 주세요.'); return }
    setCategory(id); setSelected(null); setQuantity(''); setPage(0); setError(''); setMessage('')
  }
  function selectProduct(p: InventoryProduct) {
    if (busy) return
    if (unregistered && selected?.id !== p.id) { setError('현재 상품의 수량을 먼저 등록하거나 입력을 취소해 주세요.'); return }
    setSelected(p); setQuantity(String(registered[p.id])); setError('')
  }
  function register() {
    if (!selected || !validQuantity || busy) return
    const count = Number(quantity)
    setRegistered(values => ({ ...values, [selected.id]: count })); setQuantity(String(count))
    setError(''); setMessage(`${selected.name} 수량 ${count}개 등록. 카테고리 저장을 눌러 완료해 주세요.`)
  }
  async function saveCategory() {
    if (!practice || !category || inFlight.current) return
    if (unregistered) { setError('입력한 수량을 먼저 등록해 주세요.'); return }
    inFlight.current = true; setBusy(true); setError(''); setMessage('')
    const items = categoryProducts.map(p => ({ product_id: p.id, quantity: registered[p.id] }))
    try {
      const result = await api<InventorySave>(`/inventory-practices/${practice.id}/categories`, { category_id: category, items })
      setSaved(values => ({ ...values, ...Object.fromEntries(result.items.map(i => [i.product_id, i.quantity])) }))
      setPractice(previous => previous && ({ ...previous, saved_categories: { ...previous.saved_categories, [String(category)]: result } }))
      setMessage('카테고리 저장 완료! 이제 다른 카테고리로 이동할 수 있어요.')
    } catch (e) { setError(e instanceof Error ? e.message : '저장에 실패했어요. 수량은 유지되니 다시 저장해 주세요.') }
    finally { inFlight.current = false; setBusy(false) }
  }
  const pageSize = 4
  return <section className="inventory-practice" aria-label="재고 등록 연습">
    <div className="section-heading"><div><h2>재고 등록 연습</h2><p>퀴즈 없이 직접 수량을 수정하고 저장해 보세요.</p></div><span className="round-rule">연습용 재고 · 실제 재고와 연동 없음</span></div>
    <div className="inventory-guide"><b>상품 선택 → 총수량 수정 → 수량 등록 → 카테고리 저장</b><p>기존 3개에 새 빵 4개가 나오면 수량을 <strong>7개</strong>로 바꿔요. 변경하지 않은 상품은 기존 수량을 유지해요.</p></div>
    {error && <div role="alert" className="error">{error}</div>}
    {message && <div role="status" className="inventory-message">{message}</div>}
    {restoring ? <p role="status">저장한 재고 연습을 확인하는 중이에요…</p> : !practice ? <section className="practice-panel"><div><h2>연습용 POS를 열어볼까요?</h2><p>예시 상품의 초기 재고는 각각 3개예요. 원하는 수량으로 수정해 보세요.</p></div><button className="primary" onClick={() => void start()} disabled={busy}>{busy ? '준비 중…' : unavailable ? '새 재고 연습 시작' : '재고 연습 시작'}</button></section> : <section className="inventory-pos">
      <div className="pos-heading"><h3>재고 입력 POS</h3><span className={locked ? 'stock-state pending' : 'stock-state'}>{unregistered ? '수량 등록 필요' : dirty ? `${pendingCount}개 상품 저장 대기` : '저장됨 · 카테고리 이동 가능'}</span></div>
      <div className="categories" aria-label="재고 카테고리">{categories.filter(c => practice.products.some(p => p.category_id === c.id)).map(c => <button key={c.id} className={category === c.id ? 'selected' : ''} aria-pressed={category === c.id} aria-disabled={busy || (locked && category !== c.id)} onClick={() => selectCategory(c.id)}>{c.name}{practice.saved_categories[String(c.id)] ? ' ✓' : ''}{locked && category !== c.id ? ' 🔒' : ''}</button>)}</div>
      {!category ? <div className="empty">먼저 카테고리를 선택해 주세요.</div> : <>
        <div className="inventory-grid">{categoryProducts.slice(page * pageSize, (page + 1) * pageSize).map(p => <button key={p.id} className={`stock-card ${selected?.id === p.id ? 'current' : ''}`} disabled={busy} aria-pressed={selected?.id === p.id} onClick={() => selectProduct(p)}><div className="art"><BreadArt kind={p.illustration}/><span>예시 일러스트</span></div><div className="card-body"><h3>{p.name}</h3><p>재고 <b>{registered[p.id]}</b>개</p><small>{saved[p.id] !== registered[p.id] ? '변경됨 · 저장 대기' : '기존 수량'}</small></div></button>)}</div>
        <div className="pagination"><button disabled={busy || page === 0} onClick={() => setPage(p => p - 1)}>← 이전</button><span>{page + 1} / {Math.max(1, Math.ceil(categoryProducts.length / pageSize))}</span><button disabled={busy || (page + 1) * pageSize >= categoryProducts.length} onClick={() => setPage(p => p + 1)}>다음 →</button></div>
        <div className="inventory-bottom"><div className="quantity-editor">{selected ? <><div className="selected-stock"><small>선택한 상품</small><strong>{selected.name}</strong><span>저장된 재고 {saved[selected.id]}개 → 수정 후 {validQuantity ? Number(quantity) : '—'}개</span></div><div className="quantity-input"><button aria-label="재고 수량 감소" disabled={busy || !validQuantity || Number(quantity) === 0} onClick={() => setQuantity(String(Number(quantity) - 1))}>−</button><label>총 재고 수량<input type="number" min="0" max="9999" step="1" inputMode="numeric" value={quantity} onChange={e => setQuantity(e.target.value)} disabled={busy}/></label><button aria-label="재고 수량 증가" disabled={busy || !validQuantity || Number(quantity) === 9999} onClick={() => setQuantity(String(Number(quantity) + 1))}>＋</button></div><div className="quantity-actions"><button className="primary" disabled={busy || !validQuantity} onClick={register}>수량 등록</button><button className="secondary" disabled={busy || !unregistered} onClick={() => { setQuantity(String(registered[selected.id])); setError('') }}>입력 취소</button></div>{!validQuantity && <p className="quantity-error" role="alert">0~9999 사이의 정수 수량을 입력해 주세요.</p>}</> : <p>상품을 선택하면 이곳에서 수량을 수정할 수 있어요.</p>}</div><div className="category-save"><p>{dirty ? `${pendingCount}개 상품의 수정한 수량을 저장해요.` : '변경하지 않은 상품은 기존 수량을 유지해요.'}</p><button className="primary" disabled={busy || unregistered} onClick={() => void saveCategory()}>{busy ? '저장 중…' : '카테고리 저장'}</button><small>저장을 완료해야 다른 카테고리로 이동할 수 있어요.</small></div></div>
      </>}
      <small className="score-note">저장한 연습 재고는 이 브라우저 탭에서 새로고침해도 이어집니다. 등록만 하고 저장하지 않은 수량은 새로고침 시 복원되지 않아요.</small>
    </section>}
  </section>
}
