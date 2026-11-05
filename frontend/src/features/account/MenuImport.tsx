import { useState } from 'react'
import type { Category } from '../../lib/api'
import { api } from '../../lib/api'

type Row = { name: string; price: string; category_id: number; slot: string; photo: string }

export function MenuImport({ categories, onSaved }: { categories: Category[]; onSaved: () => Promise<void> }) {
  const [rows, setRows] = useState<Row[]>([])
  const [requestId, setRequestId] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

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
          pos_slot: Number(row.slot) - 1, photo: row.photo.trim() || undefined,
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
    <summary>엑셀·CSV 일괄 등록</summary>
    <p>첫 행을 상품명,가격,카테고리,칸번호,사진주소 순서로 작성하세요. 칸번호는 1부터 시작해요. UTF-8 CSV 또는 XLSX 첫 시트, 최대 100행·2MB를 지원해요.</p>
    <p><a download="메뉴등록양식.csv" href={'data:text/csv;charset=utf-8,' + encodeURIComponent('\uFEFF상품명,가격,카테고리,칸번호,사진주소\n')}>CSV 양식 내려받기</a></p>
    <fieldset disabled={busy}>
      <label>메뉴 파일 선택<input type="file" accept=".csv,.xlsx" onChange={event => { void preview(event.target.files?.[0]); event.target.value = '' }}/></label>
      {error && <p role="alert" className="account-error">{error}</p>}
      {message && <p role="status">{message}</p>}
      {rows.length > 0 && <form onSubmit={event => { event.preventDefault(); void save() }}>
        <h3>등록 전 확인</h3>
        <p>새 메뉴를 추가합니다. 기존 상품과 겹치는 칸이 있으면 등록을 중단해요.</p>
        {rows.map((row, index) => <fieldset key={index} className="import-row">
          <legend>{index + 1}행</legend>
          <label>상품명<input required maxLength={80} value={row.name} onChange={event => change(index, { name: event.target.value })}/></label>
          <label>가격<input required type="number" min={0} max={100000000} value={row.price} onChange={event => change(index, { price: event.target.value })}/></label>
          <label>카테고리<select required value={row.category_id || ''} onChange={event => change(index, { category_id: Number(event.target.value) })}>
            <option value="">선택하세요</option>{categories.map(category => <option key={category.id} value={category.id}>{category.name}</option>)}
          </select></label>
          <label>칸번호<input required type="number" min={1} max={500} value={row.slot} onChange={event => change(index, { slot: event.target.value })}/></label>
          <label>사진주소<input type="url" maxLength={2048} value={row.photo} onChange={event => change(index, { photo: event.target.value })}/></label>
        </fieldset>)}
        <button className="primary" type="submit">확인한 메뉴 등록</button>
        <button className="account-secondary" type="button" onClick={() => setRows([])}>미리보기 닫기</button>
      </form>}
    </fieldset>
  </details>
}
