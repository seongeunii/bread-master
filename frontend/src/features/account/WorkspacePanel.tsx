import { useState } from 'react'
import { api } from '../../lib/api'
import type { Session } from './useAccount'
import { MyProgress } from './StoreAdmin'

export function WorkspacePanel({ session, onChanged, onManage, onPractice }: {
  session: Session | null
  onChanged: () => Promise<void>
  onManage: () => void
  onPractice: () => void
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const space = session?.workspace
  const personal = session?.workspaces.find(item => item.kind === 'personal')
  async function choose(id?: string) {
    if (busy) return
    setBusy(true); setError('')
    try {
      if (id) await api('/workspaces/select', { workspace_id: id })
      else await api('/workspaces/personal', {})
      await onChanged()
    } catch (err) { setError(err instanceof Error ? err.message : '공간을 열지 못했어요.') }
    finally { setBusy(false) }
  }
  return <section className="workspace-panel" aria-label="내 연습 공간">
    <h3>{space ? '현재 사용 공간' : '어떻게 시작할까요?'}</h3>
    {space ? <div className="workspace-current"><strong>{space.name}</strong><small>{space.kind === 'personal' ? '개인 연습 · 나만 확인하는 자료와 기록' : space.role === 'admin' ? '공식 매장 · 관리자' : '공식 매장 · 근무자'}</small>
      <div className="account-actions"><button className="primary" onClick={onPractice}>연습하러 가기</button>
        {space.role !== 'worker' && <button className="account-secondary" onClick={onManage}>{space.kind === 'personal' ? '내 POS 관리' : '매장 메뉴 관리'}</button>}</div>
    </div> : <p>내 자료로 연습하거나 아래에서 매장에 참여·등록할 수 있어요.</p>}
    {error && <p role="alert" className="account-error">{error}</p>}
    <div className="workspace-card"><strong>개인 연습 공간</strong><p>받은 POS 사진과 메뉴를 직접 등록하고 연습해요.</p>
      <button className="account-secondary" disabled={busy || space?.id === personal?.id && !!personal} onClick={() => void choose(personal?.id)}>{busy ? '연결 중…' : personal ? space?.id === personal.id ? '사용 중' : '개인 공간으로 이동' : '내 자료로 연습하기'}</button>
    </div>
    {session?.workspaces.filter(item => item.kind === 'store').map(item => <div className="workspace-card" key={item.id}><strong>{item.name}</strong><p>{item.role === 'admin' ? '매장 관리자' : '매장 근무자'}</p><button className="account-secondary" disabled={busy || space?.id === item.id} onClick={() => void choose(item.id)}>{space?.id === item.id ? '사용 중' : '이 매장으로 이동'}</button></div>)}
    {space && <MyProgress key={space.id}/>}
  </section>
}
