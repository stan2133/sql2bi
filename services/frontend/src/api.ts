import type {
  DashboardSpec,
  FiltersPayload,
  ImportResponse,
  QueryDataPayload,
  QueryReportResponse
} from './types'

function trimSlash(url: string): string {
  return url.endsWith('/') ? url.slice(0, -1) : url
}

export class Sql2BiApi {
  private readonly baseUrl: string
  private readonly sessionId: string

  constructor(baseUrl: string, sessionId: string) {
    this.baseUrl = trimSlash(baseUrl)
    this.sessionId = sessionId
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      headers: {
        'Content-Type': 'application/json',
        'X-SQL2BI-Session': this.sessionId,
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

  private async requestBlob(path: string, init?: RequestInit): Promise<Blob> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      headers: {
        'X-SQL2BI-Session': this.sessionId,
        ...(init?.headers || {})
      },
      ...init
    })

    if (!res.ok) {
      const text = await res.text()
      throw new Error(`HTTP ${res.status}: ${text}`)
    }

    return res.blob()
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

  async exportCsv(queryId: string, filters: Record<string, string>): Promise<Blob> {
    const params = new URLSearchParams()
    params.set('include_filters', 'true')
    Object.entries(filters).forEach(([k, v]) => {
      if (v.trim()) params.set(k, v)
    })

    return this.requestBlob(`/api/v1/queries/${encodeURIComponent(queryId)}/export.csv?${params.toString()}`)
  }

  async createQueryReport(
    queryId: string,
    payload: {
      theme?: string
      version?: string
      filters: Record<string, string>
      include_csv?: boolean
      chart_png_data_url?: string
    }
  ): Promise<QueryReportResponse> {
    return this.request(`/api/v1/reports/query/${encodeURIComponent(queryId)}`, {
      method: 'POST',
      body: JSON.stringify(payload)
    })
  }
}
