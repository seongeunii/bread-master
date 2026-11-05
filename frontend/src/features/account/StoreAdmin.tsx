import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../../lib/api'
import type { Category } from '../../lib/api'
import { PosTerminal } from '../pos/PosTerminal'
import type { PosProduct } from '../pos/PosTerminal'

type Menu = PosProduct & { name_group?: string | null }
type Layout = { categories: Category[]; products: Menu[] }
type Draft = {
  product_id?: number
  category_id: number
  pos_slot: number
  name: string
  price: string
  photo: string
  name_group: string
}
type Progress = {
  id: string
  display_name: string
  attempts: number
  scored: number
  accuracy: number | null
  latest: string | null
  level: number
}

function ProgressSummary({ row }: { row: Progress }) {
  return <span>레벨 {row.level} · 연습 {row.attempts}회 · 채점 {row.scored}회 · 정답률 {row.accuracy === null ? '—' : `${row.accuracy}%`} · 최근 학습 {row.latest ? new Date(row.latest.replace(' ', 'T') + 'Z').toLocaleDateString('ko-KR') : '—'}</span>
}

export function MyProgress() {
  const [row, setRow] = useState<Progress>()
  const [error, setError] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    api<Progress>('/store-admin/my-progress', undefined, controller.signal).then(setRow)
      .catch(err => { if (!controller.signal.aborted) setError(err.message) })
    return () => controller.abort()
  }, [])
  return <div className="account-note"><strong>내 학습 현황</strong><br/>
    {error ? <span role="alert">{error}</span> : row ? <ProgressSummary row={row}/> : '불러오는 중…'}
  </div>
}

function WorkerProgress() {
  const [rows, setRows] = useState<Progress[]>()
  const [error, setError] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    api<Progress[]>('/store-admin/progress', undefined, controller.signal).then(setRows)
      .catch(err => { if (!controller.signal.aborted) setError(err.message) })
    return () => controller.abort()
  }, [])
  return <section aria-label="근무자 학습 현황">
    <h2>근무자 학습 현황</h2>
    <p>레벨 1에서 시작해 누적 정답 10회에 레벨 2, 30회에 레벨 3이 돼요. 재고 연습은 정답률에서 제외돼요.</p>
    {error ? <p role="alert">{error}</p> : !rows ? <p role="status">불러오는 중…</p> : rows.length === 0
      ? <p>승인된 근무자가 아직 없어요.</p>
      : <ul className="store-requests">{rows.map(row => <li key={row.id}><strong>{row.display_name}</strong><br/><ProgressSummary row={row}/></li>)}</ul>}
  </section>
}

export function StoreAdmin() {
  const [tab, setTab] = useState<'menu' | 'progress'>('menu')
  const [layout, setLayout] = useState<Layout>()
  const [category, setCategory] = useState(0)
  const [page, setPage] = useState(0)
  const [draft, setDraft] = useState<Draft>()
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    const controller = new AbortController()
    api<Layout>('/store-admin/menu', undefined, controller.signal)
      .then(data => { setLayout(data); setCategory(data.categories[0]?.id ?? 0) })
      .catch(err => { if (!controller.signal.aborted) setError(err.message) })
    return () => controller.abort()
  }, [])

  function edit(product?: Menu, slot = 0) {
    setError('')
    setNotice('')
    setDraft({
      product_id: product?.id,
      category_id: product?.category_id ?? category,
      pos_slot: product?.pos_slot ?? slot,
      name: product?.name ?? '',
      price: String(product?.price ?? ''),
      photo: product?.illustration.startsWith('https://') ? product.illustration : '',
      name_group: product?.name_group ?? '',
    })
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!draft || busy) return
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const { photo, price, ...fields } = draft
      const data = await api<Layout>('/store-admin/menu', { ...fields, price: Number(price), photo: photo.trim() || undefined })
      setLayout(data)
      setCategory(draft.category_id)
      setPage(Math.floor(draft.pos_slot / 25))
      setDraft(undefined)
      setNotice('메뉴를 저장했어요.')
    } catch (err) {
      setError(err instanceof Error ? err.message : '저장하지 못했어요.')
    } finally { setBusy(false) }
  }

  return <section aria-label="매장 관리">
    <div className="account-tabs" aria-label="관리 메뉴">
      <button aria-pressed={tab === 'menu'} onClick={() => setTab('menu')}>POS 메뉴 관리</button>
      <button aria-pressed={tab === 'progress'} onClick={() => setTab('progress')}>근무자 학습 현황</button>
    </div>
    {tab === 'progress' ? <WorkerProgress/> : <>
      {error && <p role="alert" className="account-error">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {layout ? <PosTerminal categories={layout.categories} products={layout.products} category={category}
        page={page} onCategory={id => { setCategory(id); setPage(0) }} onPage={setPage}
        onProduct={product => edit(product)} onBlank={slot => edit(undefined, slot)} disabled={busy}
        selected={draft?.product_id} controls={<p>빈 칸을 눌러 메뉴를 등록하거나 상품을 눌러 수정하세요.</p>}
        ledger={draft ? <form onSubmit={event => void save(event)} className="store-menu-form">
          <fieldset disabled={busy}>
            <label>메뉴 이름<input required maxLength={80} value={draft.name} onChange={e => setDraft({ ...draft, name: e.target.value })}/></label>
            <label>가격<input type="number" required min={0} max={100000000} value={draft.price} onChange={e => setDraft({ ...draft, price: e.target.value })}/></label>
            <label>카테고리<select value={draft.category_id} onChange={e => setDraft({ ...draft, category_id: Number(e.target.value) })}>
              {layout.categories.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select></label>
            <label>칸 번호<input type="number" required min={1} max={500} value={draft.pos_slot + 1} onChange={e => setDraft({ ...draft, pos_slot: Number(e.target.value) - 1 })}/></label>
            <label>사진 주소 (HTTPS)<input type="url" value={draft.photo} maxLength={2048} onChange={e => setDraft({ ...draft, photo: e.target.value })}/></label>
            <label>유사 상품 그룹<input value={draft.name_group} maxLength={60} onChange={e => setDraft({ ...draft, name_group: e.target.value })}/></label>
            <button className="primary" type="submit">메뉴 저장</button>
          </fieldset>
        </form> : <p>등록하거나 수정할 칸을 선택하세요.</p>}/> : !error && <p role="status">매장 메뉴를 불러오는 중…</p>}
    </>}
  </section>
}
