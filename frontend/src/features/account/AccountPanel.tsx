import { useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../../lib/api'
import type { Account } from './useAccount'
import { StorePanel } from './StorePanel'
import './Account.css'

type Props = {
  user: Account | null
  enabled: boolean
  loading: boolean
  connectionError: string
  onRetry: () => void
  onSignedIn: (user: Account) => void
  onSignedOut: () => void
  onPractice: () => void
}

export function AccountPanel({ user, enabled, loading, connectionError, onRetry, onSignedIn, onSignedOut, onPractice }: Props) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy) return
    setError('')
    if (mode === 'register' && password !== confirmation) {
      setError('비밀번호 확인이 일치하지 않아요.'); return
    }
    if (mode === 'register' && !name.trim()) { setError('이름을 입력해 주세요.'); return }
    setBusy(true)
    try {
      const account = await api<Account>(`/auth/${mode}`, {
        email: email.trim(), password, ...(mode === 'register' ? { display_name: name.trim() } : {}),
      })
      setPassword(''); setConfirmation(''); onSignedIn(account)
    } catch (e) { setError(e instanceof Error ? e.message : '다시 시도해 주세요.') }
    finally { setBusy(false) }
  }
  async function logout() {
    if (busy) return
    setBusy(true); setError('')
    try {
      await api<void>('/auth/logout', {})
      setEmail(''); setPassword(''); setConfirmation(''); onSignedOut()
    } catch (e) { setError(e instanceof Error ? e.message : '로그아웃에 실패했어요.') }
    finally { setBusy(false) }
  }
  function switchMode(next: 'login' | 'register') {
    setMode(next); setError(''); setPassword(''); setConfirmation('')
  }

  return <section className="account-panel" aria-labelledby="account-title">
    <p className="eyebrow">MY BREAD MASTER</p>
    {loading ? <p role="status">로그인 상태를 확인하고 있어요…</p>
      : connectionError ? <><h2 id="account-title">계정에 연결하지 못했어요</h2><p role="alert">{connectionError}</p><button className="primary" onClick={onRetry}>다시 연결</button></>
      : !enabled ? <><h2 id="account-title">지금은 로그인 없는 체험 모드예요</h2><p>상품 학습과 업무 연습을 바로 이용할 수 있어요.</p><button className="primary" onClick={onPractice}>체험 시작하기</button></>
      : user ? <>
        <h2 id="account-title">{user.display_name}님의 계정</h2>
        <p className="account-intro">오늘도 빵 하나씩, 차근차근 익혀 봐요.</p>
        <dl className="account-details"><dt>이름</dt><dd>{user.display_name}</dd><dt>이메일</dt><dd>{user.email}</dd></dl>
        <StorePanel key={user.id}/>
        <p className="account-note">현재 연습 결과는 계정에 저장되지 않아요.</p>
        {error && <p role="alert" className="account-error">{error}</p>}
        <div className="account-actions"><button className="primary" onClick={onPractice}>연습하러 가기</button><button className="account-secondary" disabled={busy} onClick={() => void logout()}>{busy ? '로그아웃 중…' : '로그아웃'}</button></div>
      </> : <>
        <h2 id="account-title">{mode === 'login' ? '다시 만나서 반가워요' : '빵마스터와 함께 시작해요'}</h2>
        <p className="account-intro">{mode === 'login' ? '이메일로 내 계정에 로그인하세요.' : '계정을 만들면 바로 로그인돼요.'}</p>
        <div className="account-tabs" aria-label="계정 메뉴"><button aria-pressed={mode === 'login'} disabled={busy} onClick={() => switchMode('login')}>로그인</button><button aria-pressed={mode === 'register'} disabled={busy} onClick={() => switchMode('register')}>회원가입</button></div>
        <form onSubmit={event => void submit(event)}>
          <fieldset disabled={busy}>
            {mode === 'register' && <label htmlFor="account-name">이름<input id="account-name" name="name" autoComplete="nickname" value={name} onChange={e => setName(e.target.value)} required maxLength={30} placeholder="사용할 이름을 입력해 주세요"/></label>}
            <label htmlFor="account-email">이메일<input id="account-email" name="email" type="email" autoComplete="username" value={email} onChange={e => setEmail(e.target.value)} required maxLength={254} placeholder="name@example.com" autoCapitalize="none" spellCheck={false}/></label>
            <label htmlFor="account-password">비밀번호<input id="account-password" name="password" type="password" autoComplete={mode === 'register' ? 'new-password' : 'current-password'} value={password} onChange={e => setPassword(e.target.value)} required minLength={mode === 'register' ? 10 : 1} maxLength={128} aria-describedby={mode === 'register' ? 'password-guide' : undefined}/></label>
            {mode === 'register' && <><small id="password-guide">10~128자로 입력해 주세요.</small><label htmlFor="account-confirm">비밀번호 확인<input id="account-confirm" name="password-confirm" type="password" autoComplete="new-password" value={confirmation} onChange={e => setConfirmation(e.target.value)} required maxLength={128}/></label></>}
            {error && <p role="alert" className="account-error">{error}</p>}
            <button className="primary account-submit" type="submit">{busy ? '확인하고 있어요…' : mode === 'login' ? '로그인' : '가입하고 시작하기'}</button>
          </fieldset>
        </form>
        <p className="account-note">현재 연습 결과는 계정에 저장되지 않아요. 가입 후 근무 매장에 참여할 수 있어요.</p>
      </>}
  </section>
}
