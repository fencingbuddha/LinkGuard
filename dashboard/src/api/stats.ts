import { api } from './client'

export type AdminStatsResponse = {
  total_scans: number
  risk_distribution: Record<'SAFE' | 'SUSPICIOUS' | 'DANGEROUS', number>
  top_risky_domains: { domain: string; count: number }[]
  daily_scan_trend: { date: string; count: number }[]
}

export function fetchAdminStats(params: {
  orgId: string
  from?: string
  to?: string
}) {
  const qs = new URLSearchParams({
    org_id: params.orgId,
    ...(params.from && { from: params.from }),
    ...(params.to && { to: params.to }),
  })

  return api.get<AdminStatsResponse>(`/api/admin/stats?${qs.toString()}`)
}