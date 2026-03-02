import type { DashboardSpec, FiltersPayload, ImportResponse, QueryDataPayload } from './types'

function trimSlash(url: string): string {
  return url.endsWith('/') ? url.slice(0, -1) : url
}

export class Sql2BiApi {
  private readonly baseUrl: string

  constructor(baseUrl: string) {
    this.baseUrl = trimSlash(baseUrl)
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      headers: {
        'Content-Type': 'application/json',
        ...(init?.headers || {})
      },
      ...init
    })

    if (!res.ok) {
      const text = await res.text()
      throw new Error(`HTTP ${res.status}: ${text}`)
    }

    return (await res.json()) as T
  }

  async health(): Promise<{ status: string; time: string }> {
    return this.request('/api/health')
  }

  async importSqlMd(sqlMdPath: string): Promise<ImportResponse> {
    return this.request('/api/v1/import/sql-md', {
      method: 'POST',
      body: JSON.stringify({ sql_md_path: sqlMdPath })
    })
  }

  async currentDashboard(): Promise<DashboardSpec> {
    return this.request('/api/v1/dashboard/current')
  }

  async filters(): Promise<FiltersPayload> {
    return this.request('/api/v1/filters')
  }

  async queryData(queryId: string, filters: Record<string, string>): Promise<QueryDataPayload> {
    const params = new URLSearchParams()
    params.set('include_filters', 'true')
    Object.entries(filters).forEach(([k, v]) => {
      if (v.trim()) params.set(k, v)
    })

    return this.request(`/api/v1/queries/${encodeURIComponent(queryId)}/data?${params.toString()}`)
  }
}
