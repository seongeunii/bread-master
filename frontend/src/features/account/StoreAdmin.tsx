import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../../lib/api'
import { uploadMenuPhoto } from './uploadMenuPhoto'
import { MenuImport } from './MenuImport'
import { CategoryManager } from './CategoryManager'
import type { CategoryDraft } from './CategoryManager'
import type { Category, Question, Result } from '../../lib/api'
import { BreadArt } from '../../components/BreadArt'
import { QuestionChoices } from '../learning/QuestionChoices'
import { WorkerAssessmentResults } from '../learning/Assessment'
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

type LearningAttempt = {
  id: string
  mode: string
  product_name: string
  category_name: string | null
  illustration: string | null
  is_correct: boolean
  completed_at: string
  differences: { product_id: number; name: string; expected: number; actual: number }[]
  can_retry: boolean
}
type PersonalLearning = {
  attempts: LearningAttempt[]
  has_more: boolean
  by_mode: Record<string, { attempts: number; correct: number; accuracy: number }>
}

function ProgressSummary({ row }: { row: Progress }) {
  return <span>레벨 {row.level} · 연습 {row.attempts}회 · 채점 {row.scored}회 · 정답률 {row.accuracy === null ? '—' : `${row.accuracy}%`} · 최근 학습 {row.latest ? new Date(row.latest.replace(' ', 'T') + 'Z').toLocaleDateString('ko-KR') : '—'}</span>
}

const modeLabels: Record<string, string> = {
  category: '카테고리', name: '사진으로 상품명 찾기', 'similar-photo': '이름으로 상품 사진 찾기',
  delivery: '배달 기본', 'delivery-order': '배달 심화', 'pos-order': 'POS', pos: 'POS',
}

export function MyProgress() {
  const [row, setRow] = useState<Progress>()
  const [learning, setLearning] = useState<PersonalLearning>()
  const [mistakes, setMistakes] = useState(true)
  const [offset, setOffset] = useState(0)
  const [reload, setReload] = useState(0)
  const [question, setQuestion] = useState<Question>()
  const [answer, setAnswer] = useState<Result>()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const startedAt = useRef(0)

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([
      api<Progress>('/store-admin/my-progress', undefined, controller.signal),
      api<PersonalLearning>(`/store-admin/my-learning?mistakes_only=${mistakes}&offset=${offset}`, undefined, controller.signal),
    ]).then(([summary, history]) => { setRow(summary); setLearning(history) })
      .catch(err => { if (!controller.signal.aborted) setError(err.message) })
    return () => controller.abort()
  }, [mistakes, offset, reload])

  function refresh() {
    setError('')
    setLearning(undefined)
    setReload(value => value + 1)
  }

  async function perform(action: () => Promise<void>) {
    if (busy) return
    setBusy(true)
    setError('')
    try { await action() }
    catch (err) { setError(err instanceof Error ? err.message : '다시 시도해 주세요.') }
    finally { setBusy(false) }
  }

  function show(nextMistakes: boolean, nextOffset: number) {
    if (nextMistakes === mistakes && nextOffset === offset) return
    setLearning(undefined)
    setError('')
    setMistakes(nextMistakes)
    setOffset(nextOffset)
  }

  return <div className="account-note">
    <strong>내 학습 현황</strong><br/>
    {row && <ProgressSummary row={row}/>}
    <section className="personal-learning" aria-label="내 연습 기록">
      <h3>내 연습 기록</h3>
      <p>모드별 정답률은 지금까지 채점한 연습 기준이에요.</p>
      {learning && <div className="personal-mode-stats">{Object.entries(learning.by_mode).map(([mode, stats]) =>
        <span key={mode}>{modeLabels[mode] ?? mode} · {stats.correct}/{stats.attempts} 정답 · {stats.accuracy}%</span>)}</div>}
      <div className="account-tabs" aria-label="연습 기록 보기">
        <button disabled={busy || !!question} aria-pressed={mistakes} onClick={() => show(true, 0)}>오답 노트</button>
        <button disabled={busy || !!question} aria-pressed={!mistakes} onClick={() => show(false, 0)}>풀이 기록</button>
      </div>
      {error && <p role="alert">{error}</p>}
      {question ? <>
        <QuestionChoices question={question} selected={answer?.selected_id ?? null} disabled={busy || !!answer}
          onSelect={selected_id => void perform(async () => {
            setAnswer(await api<Result>(`/questions/${question.id}/answer`, {
              selected_id, elapsed_ms: Math.round(performance.now() - startedAt.current),
            }))
          })}/>
        {answer && <p role="status">{answer.feedback} 정답은 {answer.correct_product.name} · {answer.correct_product.category_name}이에요.</p>}
        <button className="secondary" disabled={busy} onClick={() => {
          setQuestion(undefined); setAnswer(undefined)
          if (answer) refresh()
        }}>목록으로 돌아가기</button>
      </> : !learning ? error ? <button className="secondary" onClick={refresh}>다시 불러오기</button>
        : <p role="status">불러오는 중이에요…</p> : <>
        {learning.attempts.length ? <ul className="personal-mistakes">{learning.attempts.map(item => <li key={item.id}>
          {item.illustration && <div className="history-art"><BreadArt kind={item.illustration}/></div>}
          <div><strong>{item.product_name}</strong>
            <small>{item.category_name ? `${item.category_name} · ` : ''}{modeLabels[item.mode] ?? item.mode} · {item.is_correct ? '정답' : '오답'}</small>
            <small>{new Date(item.completed_at.replace(' ', 'T') + 'Z').toLocaleString('ko-KR')}</small>
            {item.differences.map(diff => <small key={diff.product_id}>{diff.name} · 정답 {diff.expected}개 / 선택 {diff.actual}개</small>)}
            {item.can_retry && <button className="account-secondary" disabled={busy} onClick={() => void perform(async () => {
              setQuestion(await api<Question>(`/store-admin/my-learning/${item.id}/retry`, {}))
              startedAt.current = performance.now()
            })}>다시 풀기</button>}
          </div>
        </li>)}</ul> : <p>{mistakes ? '저장된 오답이 없어요.' : '채점한 연습이 아직 없어요.'}</p>}
        <div className="assessment-actions">
          {offset > 0 && <button className="secondary" disabled={busy} onClick={() => show(mistakes, offset - 20)}>이전 기록</button>}
          {learning.has_more && <button className="secondary" disabled={busy} onClick={() => show(mistakes, offset + 20)}>다음 기록</button>}
        </div>
      </>}
    </section>
  </div>
}

function WorkerProgress() {
  const [rows, setRows] = useState<Progress[]>()
  const [error, setError] = useState('')
  const [worker, setWorker] = useState<string>()
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
      : <ul className="store-requests">{rows.map(row => <li key={row.id}>
        <strong>{row.display_name}</strong><br/><ProgressSummary row={row}/>
        <div className="assessment-actions"><button className="secondary" aria-expanded={worker === row.id}
          onClick={() => setWorker(worker === row.id ? undefined : row.id)}>
          {worker === row.id ? '평가 결과 닫기' : '평가 결과 보기'}
        </button></div>
        {worker === row.id && <WorkerAssessmentResults workerId={row.id}/>}
      </li>)}</ul>}
  </section>
}

export function StoreAdmin({ tab = 'menu' }: { tab?: 'menu' | 'progress' }) {
  const [layout, setLayout] = useState<Layout>()
  const [category, setCategory] = useState(0)
  const [page, setPage] = useState(0)
  const [draft, setDraft] = useState<Draft>()
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    if (tab !== 'menu') return
    const controller = new AbortController()
    api<Layout>('/store-admin/menu', undefined, controller.signal)
      .then(data => { setLayout(data); setCategory(data.categories[0]?.id ?? 0) })
      .catch(err => { if (!controller.signal.aborted) setError(err.message) })
    return () => controller.abort()
  }, [tab])

  function edit(product?: Menu, slot = 0) {
    setError('')
    setNotice('')
    setDraft({
      product_id: product?.id,
      category_id: product?.category_id ?? category,
      pos_slot: product?.pos_slot ?? slot,
      name: product?.name ?? '',
      price: String(product?.price ?? ''),
      photo: product && (product.illustration.startsWith('https://') || product.illustration.startsWith('/api/v1/store-admin/photos/')) ? product.illustration : '',
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


  async function saveCategories(items: CategoryDraft[]) {
    if (busy) return
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const data = await api<Layout>('/store-admin/categories', { items })
      setLayout(data)
      if (!data.categories.some(item => item.id === category)) setCategory(data.categories[0].id)
      setDraft(undefined)
      setPage(0)
      setNotice('카테고리를 저장했어요.')
    } catch (err) {
      setError(err instanceof Error ? err.message : '저장하지 못했어요.')
    } finally { setBusy(false) }
  }

  async function uploadPhoto(file?: File) {
    if (!file || !draft || busy) return
    setError('')
    if (file.size > 5 * 1024 * 1024) { setError('사진은 5MB 이하로 올려 주세요.'); return }
    setBusy(true)
    try {
      const url = await uploadMenuPhoto(file)
      setDraft({ ...draft, photo: url })
      setNotice('사진을 올렸어요. 메뉴 저장을 눌러 반영하세요.')
    } catch (err) { setError(err instanceof Error ? err.message : '업로드에 실패했어요.') }
    finally { setBusy(false) }
  }

  return <section aria-label="매장 관리">
    {tab === 'progress' ? <WorkerProgress/> : <>
      {error && <p role="alert" className="account-error">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {layout && <MenuImport categories={layout.categories} onSaved={async () => { setLayout(await api<Layout>('/store-admin/menu')) }}/>}
      {layout && <CategoryManager key={JSON.stringify(layout.categories)} categories={layout.categories} occupied={new Set(layout.products.map(product => product.category_id))} busy={busy} onSave={items => void saveCategories(items)}/>}
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
            <label>사진 주소 (HTTPS) 또는 업로드 경로<input type="text" value={draft.photo} maxLength={2048} onChange={e => setDraft({ ...draft, photo: e.target.value })}/></label>
            <label>사진 파일 업로드<input type="file" accept="image/jpeg,image/png,image/webp" onChange={event => { void uploadPhoto(event.target.files?.[0]); event.target.value = '' }}/></label>
            <small>JPG·PNG·WebP, 최대 5MB. 사진을 올린 뒤 메뉴를 저장하세요.</small>
            {draft.photo && <img className="store-photo-preview" src={draft.photo} alt="등록할 상품 사진" referrerPolicy="no-referrer"/>}
            <small>유사 상품 그룹은 상단 퀴즈 관리에서 구성하세요.</small>
            <button className="primary" type="submit">메뉴 저장</button>
          </fieldset>
        </form> : <p>등록하거나 수정할 칸을 선택하세요.</p>}/> : !error && <p role="status">매장 메뉴를 불러오는 중…</p>}
    </>}
  </section>
}
