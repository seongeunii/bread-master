import { useState } from 'react'
import { PhotoRecognition } from './PhotoRecognition'
import type { MenuCandidate } from './menuCandidates'
import type { Category } from '../../lib/api'
import { api } from '../../lib/api'

type Row = MenuCandidate

export function MenuImport({ categories, onSaved }: { categories: Category[]; onSaved: () => Promise<void> }) {
  const [source, setSource] = useState<'file' | 'photo' | 'link'>('file')
  const [url, setUrl] = useState('')
  const [sourceUrl, setSourceUrl] = useState('')
  const [rows, setRows] = useState<Row[]>([])
  const [requestId, setRequestId] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  function candidates(next: MenuCandidate[]) {
    setRows(next)
    setRequestId(crypto.randomUUID())
    setError('')
    setMessage('')
    setSourceUrl('')
  }

  async function previewLink() {
    if (busy) return
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const result = await api<{ name: string; photo: string; source_url: string }>('/store-admin/import/link', { url: url.trim() })
      candidates([{ name: result.name, photo: result.photo, source_url: result.source_url, price: '', category_id: 0, slot: '', note: '매장 판매가·POS 분류·칸번호를 입력하세요.' }])
      setSourceUrl(result.source_url)
    } catch (err) { setError(err instanceof Error ? err.message : '상품 링크를 읽지 못했어요.') }
    finally { setBusy(false) }
  }

  async function preview(file?: File) {
    if (!file || busy) return
    setError('')
    setMessage('')
    if (file.size > 2 * 1024 * 1024) { setError('파일은 2MB 이하로 선택하세요.'); return }
    setBusy(true)
    try {
      const response = await fetch('/api/v1/store-admin/import/preview', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'X-Bread-Client': 'web' }, body: file,
      })
      const data = await response.json()
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '파일을 확인해 주세요.')
      setSourceUrl('')
      setRows(data.rows.map((row: Record<string, string>) => ({
        name: row['상품명'], price: row['가격'],
        category_id: categories.find(category => category.name === row['카테고리'])?.id ?? 0,
        slot: row['칸번호'], photo: row['사진주소'],
      })))
      setRequestId(crypto.randomUUID())
    } catch (err) { setError(err instanceof Error ? err.message : '파일을 읽지 못했어요.') }
    finally { setBusy(false) }
  }

  async function save() {
    if (busy) return
    setBusy(true)
    setError('')
    try {
      await api('/store-admin/import/save', {
        request_id: requestId,
        items: rows.map(row => ({
          name: row.name, price: Number(row.price), category_id: row.category_id,
          pos_slot: Number(row.slot) - 1, photo: row.photo.trim() || undefined, source_url: row.source_url,
        })),
      })
      setRows([])
      setMessage('메뉴를 일괄 등록했어요.')
      await onSaved()
    } catch (err) { setError(err instanceof Error ? err.message : '등록하지 못했어요.') }
    finally { setBusy(false) }
  }

  function change(index: number, patch: Partial<Row>) {
    setRows(rows.map((row, i) => i === index ? { ...row, ...patch } : row))
    setRequestId(crypto.randomUUID())
  }

  return <details className="category-manager">
    <summary>파일·POS 사진·상품 링크에서 등록</summary>
    <div className="account-tabs" aria-label="가져오기 방법">
      <button type="button" disabled={busy} aria-pressed={source === 'file'} onClick={() => setSource('file')}>엑셀·CSV</button>
      <button type="button" disabled={busy} aria-pressed={source === 'photo'} onClick={() => setSource('photo')}>POS 사진 인식</button>
      <button type="button" disabled={busy} aria-pressed={source === 'link'} onClick={() => setSource('link')}>상품 링크</button>
    </div>
    {source === 'photo' && <PhotoRecognition categories={categories} onCandidates={candidates}/>}
    {source === 'link' && <form onSubmit={event => { event.preventDefault(); void previewLink() }}>
      <p>파리바게뜨 공식 상품 상세 페이지에서 상품명·사진을 가져옵니다. 가격과 POS 위치는 확인 후 입력하세요.</p>
      <label>공식 상품 링크<input required type="url" maxLength={2048} value={url} disabled={busy} onChange={event => setUrl(event.target.value)} placeholder="https://www.paris.co.kr/product/…"/></label>
      <button type="submit" className="primary" disabled={busy}>링크에서 가져오기</button>
    </form>}
    {source === 'file' && <>
    <p>첫 행을 상품명,가격,카테고리,칸번호,사진주소 순서로 작성하세요. 칸번호는 1부터 시작해요. UTF-8 CSV 또는 XLSX 첫 시트, 최대 100행·2MB를 지원해요.</p>
    <p><a download="메뉴등록양식.csv" href={'data:text/csv;charset=utf-8,' + encodeURIComponent('\uFEFF상품명,가격,카테고리,칸번호,사진주소\n')}>CSV 양식 내려받기</a></p>
    <fieldset disabled={busy}>
      <label>메뉴 파일 선택<input type="file" accept=".csv,.xlsx" onChange={event => { void preview(event.target.files?.[0]); event.target.value = '' }}/></label>
    </fieldset></>}
    <fieldset disabled={busy}>
      {error && <p role="alert" className="account-error">{error}</p>}
      {message && <p role="status">{message}</p>}
      {rows.length > 0 && <form onSubmit={event => { event.preventDefault(); void save() }}>
        <h3>등록 전 확인</h3>
        {sourceUrl && <p><a href={sourceUrl} target="_blank" rel="noreferrer">공식 출처 확인 ↗</a></p>}
        {source === 'photo' && <p>인식한 이름·가격·칸을 원본과 대조하세요. 상품 사진은 메뉴 등록 후 별도로 연결할 수 있어요.</p>}
        <p>새 메뉴를 추가합니다. 기존 상품과 겹치는 칸이 있으면 등록을 중단해요.</p>
        {rows.map((row, index) => <fieldset key={index} className="import-row">
          <legend>{index + 1}행</legend>
          {row.note && <p className="candidate-note">{row.note}</p>}
          {row.photo && <img className="store-photo-preview" src={row.photo} alt="가져온 상품 사진" referrerPolicy="no-referrer"/>}
          <label>상품명<input required maxLength={80} value={row.name} onChange={event => change(index, { name: event.target.value })}/></label>
          <label>가격<input required type="number" min={0} max={100000000} value={row.price} onChange={event => change(index, { price: event.target.value })}/></label>
          <label>카테고리<select required value={row.category_id || ''} onChange={event => change(index, { category_id: Number(event.target.value) })}>
            <option value="">선택하세요</option>{categories.map(category => <option key={category.id} value={category.id}>{category.name}</option>)}
          </select></label>
          <label>칸번호<input required type="number" min={1} max={500} value={row.slot} onChange={event => change(index, { slot: event.target.value })}/></label>
          <label>사진주소<input type="url" maxLength={2048} value={row.photo} onChange={event => change(index, { photo: event.target.value })}/></label>
          <button type="button" className="account-secondary" onClick={() => { setRows(rows.filter((_, i) => i !== index)); setRequestId(crypto.randomUUID()) }}>이 후보 제외</button>
        </fieldset>)}
        <button className="primary" type="submit">확인한 메뉴 등록</button>
        <button className="account-secondary" type="button" onClick={() => setRows([])}>미리보기 닫기</button>
      </form>}
    </fieldset>
  </details>
}
