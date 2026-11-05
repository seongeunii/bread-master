import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { MyProgress } from './StoreAdmin'
import { api } from '../../lib/api'

type StoreRequest = { user_id: string; display_name: string; email: string }
type Store = {
  id: string
  name: string
  role: 'admin' | 'worker'
  status: 'pending' | 'active'
  invite_code?: string
  requests?: StoreRequest[]
}

export function StorePanel({ onManage }: { onManage: () => void }) {
  const [store, setStore] = useState<Store | null | undefined>(undefined)
  const [mode, setMode] = useState<'join' | 'create'>('join')
  const [value, setValue] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    api<Store | null>('/stores/mine', undefined, controller.signal)
      .then(setStore)
      .catch(err => { if (!controller.signal.aborted) setError(err.message) })
    return () => controller.abort()
  }, [])

  async function perform(action: () => Promise<void>) {
    setBusy(true)
    setError('')
    try { await action() }
    catch (err) { setError(err instanceof Error ? err.message : '다시 시도해 주세요.') }
    finally { setBusy(false) }
  }

  async function refresh() {
    setStore(await api<Store | null>('/stores/mine'))
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    void perform(async () => {
      const created = mode === 'create'
        ? await api<Store>('/stores', { name: value.trim() })
        : await api<Store>('/stores/join', { code: value.trim() })
      setStore(created)
      setValue('')
    })
  }

  return <section className="store-panel" aria-label="근무 매장">
    <h3>근무 매장</h3>
    {error && <p role="alert" className="account-error">{error}</p>}
    {store === undefined ? (
      error ? <button className="account-secondary" disabled={busy} onClick={() => void perform(refresh)}>다시 불러오기</button>
        : <p role="status">매장 정보를 확인하고 있어요…</p>
    ) : store === null ? <>
      <div className="account-tabs" aria-label="매장 메뉴">
        <button disabled={busy} aria-pressed={mode === 'join'} onClick={() => { setMode('join'); setValue(''); setError('') }}>매장 참여</button>
        <button disabled={busy} aria-pressed={mode === 'create'} onClick={() => { setMode('create'); setValue(''); setError('') }}>매장 만들기</button>
      </div>
      <form onSubmit={submit}>
        <fieldset disabled={busy}>
          <label>{mode === 'join' ? '초대 코드' : '매장 이름'}
            <input required value={value} onChange={event => setValue(event.target.value)}
              maxLength={mode === 'join' ? 12 : 60} minLength={mode === 'join' ? 12 : 1}
              autoComplete="off" spellCheck={false}/>
          </label>
          <button className="primary account-submit">{mode === 'join' ? '참여 신청' : '매장 만들기'}</button>
        </fieldset>
      </form>
    </> : <>
      <p className="store-name">{store.name} · {store.status === 'pending' ? '승인 대기' : store.role === 'admin' ? '관리자' : '근무자'}</p>
      {store.status === 'pending' && <>
        <p>관리자가 승인하면 이 계정에 매장이 연결돼요.</p>
        <button className="account-secondary" disabled={busy} onClick={() => void perform(async () => {
          await api('/stores/cancel', {})
          await refresh()
        })}>신청 취소</button>
      </>}
      {store.role === 'admin' && <>
        <button className="primary" onClick={onManage}>매장 관리</button>
        <p>초대 코드 <code>{store.invite_code}</code></p>
        <small>참여할 근무자에게 이 코드를 알려 주세요.</small>
        <h4>승인 대기 신청</h4>
        {store.requests?.length ? <ul className="store-requests">{store.requests.map(request => <li key={request.user_id}>
          <strong>{request.display_name}</strong>
          <small>{request.email}</small>
          <div className="account-actions">
            <button className="primary" disabled={busy} onClick={() => void perform(async () => {
              await api(`/stores/requests/${request.user_id}/approve`, {})
              await refresh()
            })}>승인</button>
            <button className="account-secondary" disabled={busy} onClick={() => void perform(async () => {
              await api(`/stores/requests/${request.user_id}/reject`, {})
              await refresh()
            })}>거절</button>
          </div>
        </li>)}</ul> : <p>대기 중인 신청이 없어요.</p>}
      </>}
      <button className="account-secondary" disabled={busy} onClick={() => void perform(refresh)}>상태 새로고침</button>
      {store.status === 'active' && <MyProgress/>}
    </>}
  </section>
}
