export type FilterDef = {
  id?: string
  field: string
  suggested_widget?: string
  operators?: string[]
  is_time?: boolean
  value_format?: string | null
}

export type WidgetSpec = {
  id: string
  query_id: string
  title: string
  chart: string
  position: { x: number; y: number; w: number; h: number }
  fields: {
    metrics: string[]
    dimensions: string[]
    time_fields: string[]
  }
  filters?: string[]
  dsl_filters?: FilterDef[]
  datasource?: string
  refresh?: string
}

export type DashboardPage = {
  id: string
  title: string
  global_filters?: FilterDef[]
  widgets: WidgetSpec[]
}

export type DashboardSpec = {
  version: string
  name: string
  grid: { columns: number; rowHeight: number }
  pages: DashboardPage[]
}

export type FiltersPayload = {
  global_filters: FilterDef[]
  widget_filters: Record<string, FilterDef[]>
}

export type QueryDataPayload = {
  query_id: string
  filters: Record<string, string>
  chart: string
  dimension: string
  metrics: string[]
  rows: Record<string, string | number>[]
  row_count: number
  applied_filters: Array<{ field: string; mode: string; value: string }>
  summary: Record<string, number>
  session_id: string
  audit_sql_md_path: string
  audit_sql_file_path: string
  sql_audit_report_path?: string
  sql_truncated: boolean
  missing_parameters: string[]
  generated_at: string
}

export type ImportResponse = {
  dashboard_id: string
  sql_md_path: string
  query_count: number
  widget_count: number
  imported_at: string
}

export type FilterValue = string | string[] | { from: string; to: string } | null

export type QueryReportResponse = {
  query_id: string
  session_id: string
  filters: Record<string, string>
  theme: string
  version: string
  report_root: string
  report_audit: string
  finding_count: number
  artifacts: Record<string, string>
}
