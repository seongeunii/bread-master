import { useCallback, useEffect, useState } from 'react'
import { api } from '../../lib/api'

export type Account = { id: string; email: string; display_name: string; created_at: string }
type Session = { enabled: boolean; user: Account | null }

export function useAccount() {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const refresh = useCallback(async (signal?: AbortSignal) => {
    setLoading(true); setError('')
    try {
      const next = await api<Session>('/auth/session', undefined, signal)
      if (!signal?.aborted) setSession(next)
    } catch (e) {
      if (!signal?.aborted) setError(e instanceof Error ? e.message : '계정에 연결하지 못했어요.')
    } finally { if (!signal?.aborted) setLoading(false) }
  }, [])
  useEffect(() => {
    const controller = new AbortController()
    api<Session>('/auth/session', undefined, controller.signal)
      .then(next => { if (!controller.signal.aborted) setSession(next) })
      .catch(e => { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : '계정에 연결하지 못했어요.') })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [])
  const signedIn = (user: Account) => setSession({ enabled: true, user })
  const signedOut = () => setSession(previous => previous ? { ...previous, user: null } : previous)
  return { session, loading, error, refresh, signedIn, signedOut }
}
