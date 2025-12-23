import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api, clearToken } from '../api/client'

type RiskCategory = 'SAFE' | 'SUSPICIOUS' | 'DANGEROUS'

type OrgSummary = {
  id: number
  name: string
}

type AdminStatsResponse = {
  total_scans: number
  risk_distribution: Record<RiskCategory, number>
  top_risky_domains: { domain: string; count: number }[]
  daily_scan_trend: { date: string; count: number }[]
}

function formatPercent(numerator: number, denominator: number): string {
  if (denominator <= 0) return '0%'
  const pct = (numerator / denominator) * 100
  return `${pct.toFixed(1)}%`
}

export default function Dashboard() {
  const navigate = useNavigate()

  const orgIdOverride = useMemo(() => import.meta.env.VITE_ORG_ID ?? null, [])

  const [orgs, setOrgs] = useState<OrgSummary[]>([])
  const [orgsLoading, setOrgsLoading] = useState(true)
  const [orgsError, setOrgsError] = useState<string | null>(null)
  const [orgIdentifier, setOrgIdentifier] = useState<string | null>(orgIdOverride)
  const [stats, setStats] = useState<AdminStatsResponse | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)
  const [refreshToken, setRefreshToken] = useState(0)

  const handleLogout = () => {
    clearToken()
    navigate('/')
  }

  const handleRefresh = () => {
    setRefreshToken((prev) => prev + 1)
  }

  useEffect(() => {
    let isMounted = true

    const loadOrgs = async () => {
      setOrgsLoading(true)
      setOrgsError(null)

      try {
        const data = await api.get<OrgSummary[]>('/api/admin/orgs')
        if (!isMounted) return
        setOrgs(data)
        if (!orgIdOverride && data.length > 0) {
          setOrgIdentifier(String(data[0].id))
        }
      } catch (e) {
        const message = e instanceof Error ? e.message : 'Failed to load organizations'
        if (isMounted) setOrgsError(message)
      } finally {
        if (isMounted) setOrgsLoading(false)
      }
    }

    void loadOrgs()

    return () => {
      isMounted = false
    }
  }, [orgIdOverride])

  useEffect(() => {
    let isMounted = true

    const run = async () => {
      if (!orgIdentifier) {
        if (isMounted) {
          setStats(null)
          setLoading(false)
        }
        return
      }

      setLoading(true)
      setError(null)

      try {
        // MVP query: org only. Add from/to later when the backend supports it.
        const qs = new URLSearchParams({ org_id: orgIdentifier })
        const data = await api.get<AdminStatsResponse>(`/api/admin/stats?${qs.toString()}`)
        if (isMounted) setStats(data)
      } catch (e) {
        const message = e instanceof Error ? e.message : 'Failed to load dashboard stats'
        if (isMounted) setError(message)
      } finally {
        if (isMounted) setLoading(false)
      }
    }

    void run()

    return () => {
      isMounted = false
    }
  }, [orgIdentifier, refreshToken])

  const totalScans = stats?.total_scans ?? 0
  const risk = stats?.risk_distribution ?? { SAFE: 0, SUSPICIOUS: 0, DANGEROUS: 0 }
  const selectedOrg = orgs.find((org) => String(org.id) === orgIdentifier)
  const isReadyForStats = !orgsLoading && !orgsError && Boolean(orgIdentifier)

  return (
    <div style={{ padding: '2rem' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ margin: 0 }}>LinkGuard Admin Dashboard</h1>
          <p style={{ margin: '0.25rem 0 0' }}>
            Org:{' '}
            <code>{selectedOrg ? `${selectedOrg.name} (#${selectedOrg.id})` : orgIdentifier ?? '—'}</code>
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button onClick={handleRefresh} disabled={loading || orgsLoading || !orgIdentifier}>
            Refresh stats
          </button>
          <button onClick={handleLogout}>Log out</button>
        </div>
      </header>

      <section style={{ marginTop: '2rem' }}>
        {orgsLoading && <p>Loading organizations…</p>}

        {!orgsLoading && orgsError && (
          <div style={{ border: '1px solid #ddd', padding: '1rem' }}>
            <p style={{ marginTop: 0 }}>
              <strong>Could not load organizations.</strong>
            </p>
            <p style={{ marginBottom: 0 }}>{orgsError}</p>
          </div>
        )}

        {!orgsLoading && !orgsError && orgs.length === 0 && (
          <div style={{ border: '1px solid #ddd', padding: '1rem' }}>
            <p style={{ marginTop: 0 }}>
              <strong>No organizations found.</strong>
            </p>
            <p style={{ marginBottom: 0 }}>
              Create an organization and API key first so scans can be attributed.
            </p>
          </div>
        )}

        {isReadyForStats && loading && <p>Loading stats…</p>}

        {isReadyForStats && !loading && error && (
          <div style={{ border: '1px solid #ddd', padding: '1rem' }}>
            <p style={{ marginTop: 0 }}>
              <strong>Could not load stats.</strong>
            </p>
            <p style={{ marginBottom: 0 }}>{error}</p>
            <p style={{ marginBottom: 0, marginTop: '0.75rem' }}>
              Tip: confirm your backend is running and that your admin token is present in localStorage.
            </p>
          </div>
        )}

        {isReadyForStats && !loading && !error && stats && (
          <div style={{ display: 'grid', gap: '1.25rem' }}>
            <div style={{ border: '1px solid #ddd', padding: '1rem' }}>
              <h2 style={{ marginTop: 0 }}>Total scans</h2>
              <p style={{ fontSize: '2rem', margin: 0 }}>{totalScans.toLocaleString()}</p>
            </div>

            <div style={{ border: '1px solid #ddd', padding: '1rem' }}>
              <h2 style={{ marginTop: 0 }}>Risk distribution</h2>
              <ul style={{ margin: 0, paddingLeft: '1.25rem' }}>
                <li>
                  SAFE: {risk.SAFE.toLocaleString()} ({formatPercent(risk.SAFE, totalScans)})
                </li>
                <li>
                  SUSPICIOUS: {risk.SUSPICIOUS.toLocaleString()} ({formatPercent(risk.SUSPICIOUS, totalScans)})
                </li>
                <li>
                  DANGEROUS: {risk.DANGEROUS.toLocaleString()} ({formatPercent(risk.DANGEROUS, totalScans)})
                </li>
              </ul>
            </div>

            <div style={{ border: '1px solid #ddd', padding: '1rem' }}>
              <h2 style={{ marginTop: 0 }}>Top risky domains</h2>
              {stats.top_risky_domains.length === 0 ? (
                <p style={{ margin: 0 }}>No data yet.</p>
              ) : (
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr>
                      <th style={{ textAlign: 'left', borderBottom: '1px solid #eee', padding: '0.5rem 0' }}>Domain</th>
                      <th style={{ textAlign: 'right', borderBottom: '1px solid #eee', padding: '0.5rem 0' }}>Count</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.top_risky_domains.map((row) => (
                      <tr key={row.domain}>
                        <td style={{ padding: '0.5rem 0' }}>{row.domain}</td>
                        <td style={{ padding: '0.5rem 0', textAlign: 'right' }}>{row.count.toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            <div style={{ border: '1px solid #ddd', padding: '1rem' }}>
              <h2 style={{ marginTop: 0 }}>Daily scan trend</h2>
              {stats.daily_scan_trend.length === 0 ? (
                <p style={{ margin: 0 }}>No data yet.</p>
              ) : (
                <ul style={{ margin: 0, paddingLeft: '1.25rem' }}>
                  {stats.daily_scan_trend.map((pt) => (
                    <li key={pt.date}>
                      {pt.date}: {pt.count.toLocaleString()}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </section>
    </div>
  )
}
