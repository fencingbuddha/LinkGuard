import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { api, setToken } from '../api/client'

export default function Login() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()

    if (!email || !password) {
      setError('Please enter an email and password')
      return
    }

    setError(null)
    setLoading(true)

    try {
      type LoginResponse = { access_token?: string; token?: string }

      // Login should NOT require an existing bearer token.
      const res = await api.post<LoginResponse>(
        '/api/admin/login',
        { email, password },
        false
      )

      const token = res?.access_token ?? res?.token
      if (!token) {
        throw new Error('Login succeeded but no token was returned')
      }

      setToken(token)
      navigate('/dashboard')
    } catch (err: unknown) {
      const e = err as {
        response?: { data?: { detail?: unknown }; detail?: unknown }
        message?: unknown
      }

      const msg = 
      e?.response?.data?.detail ||
      e?.response?.detail ||
      e?.message ||
      'Login failed'

      setError(String(msg))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: 360, margin: '4rem auto' }}>
      <h1>LinkGuard Admin</h1>
      <p>Sign in to continue</p>

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: '1rem' }}>
          <label>Email</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            style={{ width: '100%' }}
          />
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <label>Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            style={{ width: '100%' }}
          />
        </div>

        {error && <p style={{ color: 'red' }}>{error}</p>}

        <button type="submit" disabled={loading}>
          {loading ? 'Signing in…' : 'Sign In'}
        </button>
      </form>
    </div>
  )
}