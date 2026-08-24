import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'

import { getAuthConfig, login, logout, setAuthToken, setupLogin, validateSession } from '../../lib/api'

type AuthGateProps = {
  children: React.ReactNode
}

export function AuthGate({ children }: AuthGateProps) {
  const USERNAME_KEY = 'trustsignal_auth_username'
  const [loading, setLoading] = useState(true)
  const [requireLogin, setRequireLogin] = useState(false)
  const [setupRequired, setSetupRequired] = useState(false)
  const [authed, setAuthed] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [rememberUsername, setRememberUsername] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [headerActionsEl, setHeaderActionsEl] = useState<HTMLElement | null>(null)

  useEffect(() => {
    const handleExpired = () => {
      setAuthed(false)
      setError('Session expired. Please sign in again.')
    }

    const bootstrap = async () => {
      try {
        const config = await getAuthConfig()
        setRequireLogin(config.require_login)
        setSetupRequired(config.setup_required)
        if (!config.require_login) {
          setAuthed(true)
          return
        }
        const savedUsername = window.localStorage.getItem(USERNAME_KEY)
        if (savedUsername) {
          setUsername(savedUsername)
          setRememberUsername(true)
        }

        if (!config.setup_required) {
          const ok = await validateSession()
          setAuthed(ok)
          if (!ok) setAuthToken(null)
        } else {
          setAuthed(false)
        }
      } catch {
        setError('Unable to initialize authentication')
      } finally {
        setLoading(false)
      }
    }

    window.addEventListener('trustsignal-auth-expired', handleExpired)
    void bootstrap()
    return () => window.removeEventListener('trustsignal-auth-expired', handleExpired)
  }, [])

  useEffect(() => {
    setHeaderActionsEl(document.getElementById('header-actions'))
  }, [])

  const onSubmit = async () => {
    try {
      setError(null)
      if (setupRequired && password !== confirmPassword) {
        setError('Passwords do not match')
        return
      }
      if (setupRequired) {
        await setupLogin(username, password)
      }
      const token = await login(username, password)
      setAuthToken(token)
      if (rememberUsername) {
        window.localStorage.setItem(USERNAME_KEY, username.trim())
      } else {
        window.localStorage.removeItem(USERNAME_KEY)
      }
      setAuthed(true)
      setSetupRequired(false)
      setPassword('')
      setConfirmPassword('')
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Authentication failed')
    }
  }

  const onLogout = async () => {
    setAuthToken(null)
    setAuthed(false)
    try {
      await logout()
    } catch {
      // best effort logout
    }
  }

  if (loading) return <div className="rounded-xl border border-border bg-white p-6 text-sm text-slate-600">Loading…</div>
  if (!requireLogin) return <>{children}</>

  if (authed) {
    return (
      <>
        {headerActionsEl
          ? createPortal(
              <button
                type="button"
                onClick={() => void onLogout()}
                className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50"
              >
                Log out
              </button>,
              headerActionsEl,
            )
          : null}
        {children}
      </>
    )
  }

  return (
    <div className="mx-auto w-full max-w-md rounded-2xl border border-border bg-white p-6 shadow-soft">
      <h2 className="text-xl font-semibold text-ink">{setupRequired ? 'Create Admin Login' : 'Sign in'}</h2>
      <p className="mt-1 text-sm text-slate-600">
        {setupRequired ? 'Secure this workspace before continuing (minimum 12-character password).' : 'Authenticate to access TrustSignal.'}
      </p>

      <div className="mt-4 space-y-3">
        <input
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          placeholder="Username"
          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
        <div className="relative">
          <input
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Password"
            type={showPassword ? 'text' : 'password'}
            className="w-full rounded-md border border-slate-300 px-3 py-2 pr-10 text-sm"
          />
          <button
            type="button"
            onClick={() => setShowPassword((v) => !v)}
            className="absolute inset-y-0 right-2 my-auto flex h-7 w-7 items-center justify-center rounded text-slate-500 hover:bg-slate-100"
            aria-label={showPassword ? 'Hide password' : 'Show password'}
            title={showPassword ? 'Hide password' : 'Show password'}
          >
            {showPassword ? (
              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M17.94 17.94A10.94 10.94 0 0 1 12 20C7 20 2.73 16.89 1 12c.82-2.31 2.19-4.29 3.94-5.94" />
                <path d="M9.9 4.24A10.94 10.94 0 0 1 12 4c5 0 9.27 3.11 11 8a10.97 10.97 0 0 1-4.06 5.94" />
                <path d="M1 1l22 22" />
                <path d="M9.53 9.53A3.5 3.5 0 0 0 12 15.5c.7 0 1.36-.2 1.92-.55" />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8S1 12 1 12z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            )}
          </button>
        </div>
        {setupRequired ? (
          <input
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            placeholder="Confirm password"
            type={showPassword ? 'text' : 'password'}
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        ) : null}
        <label className="flex items-center gap-2 text-xs text-slate-600">
          <input
            type="checkbox"
            checked={rememberUsername}
            onChange={(event) => setRememberUsername(event.target.checked)}
          />
          Remember username
        </label>
        {setupRequired && confirmPassword && password !== confirmPassword ? (
          <p className="text-xs text-red-600">Passwords do not match</p>
        ) : null}
        {error ? <p className="text-xs text-red-600">{error}</p> : null}
        <button
          type="button"
          onClick={onSubmit}
          disabled={setupRequired && (!confirmPassword || password !== confirmPassword)}
          className="w-full rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {setupRequired ? 'Create account & continue' : 'Sign in'}
        </button>
      </div>
    </div>
  )
}
