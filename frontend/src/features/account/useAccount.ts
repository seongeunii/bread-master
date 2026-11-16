import { useCallback, useEffect, useRef, useState } from 'react'
import { api, setWorkspaceContext } from '../../lib/api'

export type Account = { id: string; email: string; display_name: string; created_at: string }
export type Workspace = { id: string; name: string; kind: 'personal' | 'store'; role: 'owner' | 'admin' | 'worker' }
export type Session = { enabled: boolean; user: Account | null; store_role?: 'admin' | 'worker' | null; workspace: Workspace | null; workspaces: Workspace[] }

export function useAccount() {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const generation = useRef(0)
  const refresh = useCallback(async () => {
    const version = ++generation.current
    try {
      const next = await api<Session>('/auth/session')
      if (generation.current === version) {
        setError('')
        setWorkspaceContext(next.workspace?.id)
        setSession(next)
      }
    } catch (e) {
      if (generation.current === version) setError(e instanceof Error ? e.message : '계정에 연결하지 못했어요.')
      throw e
    } finally { if (generation.current === version) setLoading(false) }
  }, [])
  useEffect(() => {
    void Promise.resolve().then(() => refresh()).catch(() => {})
  }, [refresh])
  const signedIn = (_user: Account) => { void refresh().catch(() => {}) }
  const signedOut = () => {
    generation.current++
    setWorkspaceContext(undefined)
    setSession(previous => previous ? { ...previous, user: null, store_role: null, workspace: null, workspaces: [] } : previous)
  }
  return { session, loading, error, refresh, signedIn, signedOut }
}
