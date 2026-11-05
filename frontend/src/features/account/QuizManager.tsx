import { useEffect, useState } from 'react'
import { api } from '../../lib/api'
import type { Product, Category } from '../../lib/api'
import { BreadArt } from '../../components/BreadArt'
import './QuizManager.css'

type Group = { id: string; name: string; status: 'proposed' | 'approved' | 'dismissed'; enabled: boolean; reason: string; product_ids: number[] }
type State = { products: Product[]; categories: Category[]; groups: Group[]; recommendations_stale: boolean; recommendations_initialized: boolean }
type Draft = { id?: string; name: string; product_ids: number[]; enabled: boolean }

export function QuizManager() {
  const [data, setData] = useState<State>()
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [draft, setDraft] = useState<Draft>()
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    async function load() {
      try {
        let next = await api<State>('/store-admin/quiz-groups', undefined, controller.signal)
        if (!next.recommendations_initialized) next = await api<State>('/store-admin/quiz-groups/recommend', {}, controller.signal)
        if (!controller.signal.aborted) setData(next)
      } catch (err) { if (!controller.signal.aborted) setError(err instanceof Error ? err.message : '불러오지 못했어요.') }
    }
    void load()
    return () => controller.abort()
  }, [])

  async function mutate(path: string, body: unknown, message: string) {
    if (busy) return
    setBusy(true); setError(''); setNotice('')
    try {
      setData(await api<State>('/store-admin/quiz-groups' + path, body))
      setNotice(message)
      if (path === '/save') setDraft(undefined)
    } catch (err) { setError(err instanceof Error ? err.message : '저장하지 못했어요.') }
    finally { setBusy(false) }
  }

  function edit(group?: Group) {
    setDraft(group ? { id: group.id, name: group.name, product_ids: [...group.product_ids], enabled: group.status === 'approved' ? group.enabled : true } : { name: '', product_ids: [], enabled: true })
    setSearch(''); setCategory(''); setError(''); setNotice('')
  }

  const products = new Map(data?.products.map(product => [product.id, product]))
  const photoCount = (ids: number[]) => ids.filter(id => products.get(id)?.illustration && !products.get(id)?.manual_price).length
  const cards = (group: Group) => <article className="quiz-group" key={group.id}>
    <div className="quiz-group-heading"><h3>{group.name}</h3><span className={'quiz-status ' + (group.enabled ? 'enabled' : '')}>{group.status === 'proposed' ? '승인 대기' : group.status === 'dismissed' ? '추천 제외' : group.enabled && photoCount(group.product_ids) >= 2 ? '출제 중' : '출제 중지'}</span></div>
    <p className="quiz-reason">{group.reason}</p>
    <div className="quiz-products">{group.product_ids.map(id => { const p = products.get(id); return p && <div className="quiz-product" key={id}>
      {p.illustration ? <BreadArt kind={p.illustration}/> : <span className="quiz-no-photo">사진 필요</span>}
      <strong>{p.name}</strong><small>{p.category_name}</small>
    </div> })}</div>
    {photoCount(group.product_ids) < 2 && <p className="quiz-warning">사진이 있는 상품을 최소 두 개 연결해야 출제할 수 있어요.</p>}
    <div className="account-actions">
      <button type="button" className="account-secondary" onClick={() => edit(group)}>{group.status === 'proposed' ? '수정·승인' : '그룹 수정'}</button>
      {group.status === 'proposed' && <><button type="button" className="primary" disabled={photoCount(group.product_ids) < 2} onClick={() => void mutate('/save', { ...groupFields(group), status: 'approved', enabled: true }, '그룹을 승인하고 출제를 시작했어요.')}>승인 후 출제</button>
        <button type="button" className="account-secondary" onClick={() => void mutate('/save', { ...groupFields(group), status: 'dismissed', enabled: false }, '이 추천을 제외했어요.')}>추천 제외</button></>}
      {group.status === 'approved' && <button type="button" className="account-secondary" disabled={!group.enabled && photoCount(group.product_ids) < 2} onClick={() => void mutate('/save', { ...groupFields(group), status: 'approved', enabled: !group.enabled }, group.enabled ? '출제를 중지했어요.' : '출제를 시작했어요.')}>{group.enabled ? '출제 중지' : '출제 시작'}</button>}
      <button type="button" className="quiz-delete" onClick={() => { if (window.confirm('이 그룹을 삭제할까요? 기존 학습 기록은 보존돼요.')) void mutate('/' + group.id + '/delete', {}, '그룹을 삭제했어요.') }}>삭제</button>
    </div>
  </article>

  function groupFields(group: Group) { return { id: group.id, name: group.name, product_ids: group.product_ids } }

  return <section className="quiz-manager" aria-label="퀴즈 그룹 관리">
    <p className="quiz-intro">헷갈리는 상품을 묶어 두 가지 방향으로 연습해요. 이름으로 자동 추천한 그룹은 관리자가 승인한 뒤에 출제돼요.</p>
    {error && <p className="account-error" role="alert">{error}</p>}
    {notice && <p className="quiz-notice" role="status">{notice}</p>}
    {!data ? <p role="status">{error ? '페이지를 다시 열어 주세요.' : '상품과 추천을 준비하고 있어요…'}</p> : <fieldset disabled={busy} className="quiz-controls">
      {data.recommendations_stale && <p className="quiz-notice">메뉴가 추가되거나 이름이 바뀌었어요. 이름 추천을 갱신해 주세요.</p>}
      <div className="quiz-toolbar"><button type="button" className="primary" onClick={() => edit()}>직접 그룹 만들기</button>
        <button type="button" className="account-secondary" onClick={() => void mutate('/recommend', {}, '이름 추천을 갱신했어요. 기존 승인·제외·수정 내용은 유지돼요.')}>{busy ? '처리 중…' : '이름으로 자동 추천'}</button></div>
      {draft && <form className="quiz-editor" onSubmit={event => { event.preventDefault(); void mutate('/save', { ...draft, status: 'approved' }, draft.enabled ? '그룹을 저장하고 출제를 시작했어요.' : '출제를 중지한 상태로 그룹을 저장했어요.') }}>
        <h2>{draft.id ? '그룹 수정·승인' : '새 그룹 만들기'}</h2>
        <label>그룹 이름<input autoFocus required maxLength={60} value={draft.name} onChange={event => setDraft({ ...draft, name: event.target.value })}/></label>
        <div className="quiz-filters"><label>상품 검색<input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="이름으로 검색"/></label><label>POS 카테고리<select value={category} onChange={event => setCategory(event.target.value)}><option value="">전체 카테고리</option>{data.categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label></div>
        <p>선택 {draft.product_ids.length}개 · 사진 있음 {photoCount(draft.product_ids)}개. 상품 하나를 여러 그룹에 넣을 수 있어요.</p>
        <div className="quiz-picker">{data.products.filter(p => !p.manual_price && p.name.includes(search.trim()) && (!category || p.category_id === Number(category))).map(p => <label className={'quiz-product quiz-pick ' + (draft.product_ids.includes(p.id) ? 'selected' : '')} key={p.id}>
          <input type="checkbox" checked={draft.product_ids.includes(p.id)} onChange={event => setDraft({ ...draft, product_ids: event.target.checked ? [...draft.product_ids, p.id] : draft.product_ids.filter(id => id !== p.id) })}/>
          {p.illustration ? <BreadArt kind={p.illustration}/> : <span className="quiz-no-photo">사진 필요</span>}
          <strong>{p.name}</strong><small>{p.category_name}</small>
        </label>)}</div>
        <label className="quiz-enable"><input type="checkbox" checked={draft.enabled} onChange={event => setDraft({ ...draft, enabled: event.target.checked })}/>저장 후 퀴즈에 출제</label>
        {draft.enabled && photoCount(draft.product_ids) < 2 && <p className="quiz-warning">사진이 두 개 미만이에요. 사진을 등록하거나 출제를 중지한 상태로 저장하세요.</p>}
        <div className="account-actions"><button type="submit" className="primary" disabled={draft.product_ids.length < 2 || (draft.enabled && photoCount(draft.product_ids) < 2)}>그룹 저장</button><button type="button" className="account-secondary" onClick={() => setDraft(undefined)}>취소</button></div>
      </form>}
      <h2>추천 그룹 <small>{data.groups.filter(g => g.status === 'proposed').length}개</small></h2>
      <p>공통 단어·구문과 커피·모카 동의어를 비교해요. 사진 외형 비교는 아직 포함하지 않아요.</p>
      {data.groups.filter(g => g.status === 'proposed').map(cards)}
      {!data.groups.some(g => g.status === 'proposed') && <p className="quiz-empty">새 추천이 없어요. 직접 상품을 선택해 그룹을 만들 수 있어요.</p>}
      <h2>승인한 그룹 <small>{data.groups.filter(g => g.status === 'approved').length}개</small></h2>
      <p>사진 보고 이름 선택 / 이름 보고 사진 선택에 함께 적용돼요. 문제마다 보기 2~4개를 보여줘요.</p>
      {data.groups.filter(g => g.status === 'approved').map(cards)}
      {!data.groups.some(g => g.status === 'approved') && <p className="quiz-empty">추천을 승인하거나 직접 그룹을 만들어 보세요.</p>}
      <details><summary>제외한 추천 ({data.groups.filter(g => g.status === 'dismissed').length}개)</summary>{data.groups.filter(g => g.status === 'dismissed').map(cards)}</details>
    </fieldset>}
  </section>
}
