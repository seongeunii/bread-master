import { useRef, useState } from 'react'
import { api } from '../../lib/api'
import { BreadArt } from '../../components/BreadArt'
import './DeliveryAdvanced.css'

type Order = { id: string; lines: {product_id: number; name: string; quantity: number}[]; options: {id: number; illustration: string}[] }
type Grade = {is_correct: boolean; points: number; feedback: string; elapsed_ms: number; differences: {product_id: number; name: string; expected: number; actual: number}[]}
export function DeliveryAdvanced() {
  const [order, setOrder] = useState<Order | null>(null)
  const [cart, setCart] = useState<Record<number, number>>({})
  const [grade, setGrade] = useState<Grade | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [results, setResults] = useState<Grade[]>([])
  const started = useRef(0)
  const pending = useRef(false)
  async function start() {
    if (pending.current) return
    pending.current = true; setBusy(true); setError('')
    try {
      const next = await api<Order>('/delivery-orders', {})
      setOrder(next); setCart({}); setGrade(null); started.current = performance.now()
    } catch (e) { setError(e instanceof Error ? e.message : '주문 준비 실패') }
    finally { pending.current = false; setBusy(false) }
  }
  function add(id: number) {
    if (busy || grade) return
    setCart(c => ({...c, [id]: Math.min(99, (c[id] ?? 0) + 1)}))
  }
  function remove(id: number) {
    setCart(c => { const next = {...c}; if (next[id] > 1) next[id]--; else delete next[id]; return next })
  }
  async function submit() {
    if (!order || pending.current || grade) return
    pending.current = true; setBusy(true); setError('')
    try {
      const answer = await api<Grade>(`/delivery-orders/${order.id}/submit`, {
        items: Object.entries(cart).map(([id, quantity]) => ({product_id: Number(id), quantity})),
        elapsed_ms: Math.min(86400000, Math.round(performance.now() - started.current)),
      })
      setGrade(answer); setResults(r => [...r, answer])
    } catch (e) { setError(e instanceof Error ? e.message : '제출 실패. 다시 시도해 주세요.') }
    finally { pending.current = false; setBusy(false) }
  }
  const total = Object.values(cart).reduce((a, b) => a + b, 0)
  return <section className="delivery-advanced" aria-label="배달 심화 연습">
    <div className="scoreboard"><span>배달 심화 · 주문서 포장</span><span>{results.length}건 완료 · {results.reduce((sum, r) => sum + r.points, 0)}점</span></div>
    <p>사진을 한 번 누를 때마다 1개가 담겨요. 대부분 1개, 가끔 2개, 드물게 3~4개 주문이 들어와요. 주문당 상품과 수량이 모두 맞으면 20점이에요.</p>
    {error && <div className="error" role="alert">{error}</div>}
    {!order ? <button className="primary" disabled={busy} onClick={() => void start()}>{busy ? '주문 준비 중…' : '심화 배달 연습 시작'}</button> : <>
      <div className="delivery-workbench">
        <aside className="order-receipt" aria-label="예시 배달 주문서"><small>BREAD MASTER · 교육용 주문서</small><h2>배달 주문 접수</h2><p>주문번호 #{order.id.slice(0, 6).toUpperCase()}</p><hr/>{order.lines.map(line => <div className="receipt-line" key={line.product_id}><strong>{line.name}</strong><b>{line.quantity}개</b></div>)}<hr/><div className="receipt-line"><span>총 주문 수량</span><b>{order.lines.reduce((sum, l) => sum + l.quantity, 0)}개</b></div><p>상품명과 수량을 확인하고 빠짐없이 포장해 주세요.</p><small>실제 주문·개인정보가 없는 예시 주문서</small></aside>
        <div><h3>어떤 빵을 담을까요?</h3><p>후보 {order.options.length}개 · 사진을 반복해서 눌러 수량을 맞춰요.</p><div className="packing-candidates" aria-label="배달 후보 사진">{order.options.map((p, index) => <button key={p.id} disabled={busy || !!grade} onClick={() => add(p.id)} aria-label={`${index + 1}번 사진 담기`}><BreadArt kind={p.illustration}/><span>{index + 1}번 · 담기</span><small>{cart[p.id] ? `${cart[p.id]}개 담김` : '예시 일러스트'}</small></button>)}</div></div>
      </div>
      <section className="packing-cart" aria-label="포장 장바구니"><h3>장바구니 · {total}개</h3>{!total && <p>후보 사진을 눌러 빵을 담아 주세요.</p>}<div className="cart-items">{order.options.filter(p => cart[p.id]).map(p => <div key={p.id}><BreadArt kind={p.illustration}/><span>{order.options.findIndex(o => o.id === p.id) + 1}번 사진 · <b>{cart[p.id]}개</b></span><button disabled={busy || !!grade} onClick={() => remove(p.id)} aria-label={`${order.options.findIndex(o => o.id === p.id) + 1}번 사진 1개 빼기`}>1개 빼기</button></div>)}</div><div className="quantity-actions"><button className="secondary" disabled={busy || !!grade || !total} onClick={() => setCart({})}>장바구니 비우기</button><button className="primary" disabled={busy || !!grade || !total} onClick={() => void submit()}>{busy ? '확인 중…' : '포장 완료 · 제출'}</button></div></section>
      {grade && <section className={`feedback ${grade.is_correct ? 'correct' : 'mistake'}`} role="status"><h2>{grade.is_correct ? '😊' : '😠'} {grade.feedback}</h2><p>+{grade.points}점 · {(grade.elapsed_ms / 1000).toFixed(1)}초</p>{grade.differences.map(d => <p key={d.product_id}>{d.name} · 주문 {d.expected}개 / 담은 수량 {d.actual}개 {d.actual > d.expected ? '(초과)' : '(부족)'}</p>)}<button className="primary" disabled={busy} onClick={() => void start()}>다음 배달 주문 →</button></section>}
    </>}
    <small className="score-note">심화 점수는 현재 화면 기준이며 모드 변경·새로고침 시 초기화돼요.</small>
  </section>
}
