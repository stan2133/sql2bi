import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import * as echarts from 'echarts'
import { Sql2BiApi } from './api'
import type {
  DashboardSpec,
  FilterDef,
  FilterValue,
  FiltersPayload,
  QueryReportResponse,
  QueryDataPayload,
  WidgetSpec
} from './types'

const DEFAULT_BACKEND_URL = 'http://127.0.0.1:18000'
const DEFAULT_SQL_MD_PATH = '/Users/lyg/software/sql2bi/sample.sql.md'
const SESSION_STORAGE_KEY = 'sql2bi_session_id'

function getOrCreateSessionId(): string {
  const existing = localStorage.getItem(SESSION_STORAGE_KEY)
  if (existing) return existing

  const generated = `ui_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`
  localStorage.setItem(SESSION_STORAGE_KEY, generated)
  return generated
}

function slugifyTheme(value: string): string {
  const slug = value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/-{2,}/g, '-').replace(/^-|-$/g, '')
  return slug || 'adhoc-analysis'
}

function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

type WidgetCardProps = {
  widget: WidgetSpec
  payload?: QueryDataPayload
  active: boolean
  onClick: () => void
  onCrossFilter: (value: string) => void
  onRegisterPngExporter: (exporter: (() => string | null) | null) => void
}

function optionForPayload(payload: QueryDataPayload): echarts.EChartsOption | null {
  const chartType = (payload.chart || 'table').toLowerCase()
  const rows = payload.rows || []
  const dim = payload.dimension
  const metricA = payload.metrics[0]
  const metricB = payload.metrics[1]

  const x = rows.map((r) => String(r[dim]))
  const y1 = rows.map((r) => Number(r[metricA] || 0))
  const y2 = rows.map((r) => Number(r[metricB] || 0))

  if (chartType === 'line') {
    return {
      color: ['#2f6fed'],
      tooltip: { trigger: 'axis' },
      grid: { left: 36, right: 12, top: 18, bottom: 24 },
      xAxis: { type: 'category', data: x },
      yAxis: { type: 'value' },
      series: [{ type: 'line', smooth: true, data: y1 }]
    }
  }

  if (chartType === 'bar') {
    return {
      color: ['#2f6fed'],
      tooltip: { trigger: 'axis' },
      grid: { left: 36, right: 12, top: 18, bottom: 24 },
      xAxis: { type: 'category', data: x, axisLabel: { rotate: 25 } },
      yAxis: { type: 'value' },
      series: [{ type: 'bar', data: y1 }]
    }
  }

  if (chartType === 'grouped_bar') {
    return {
      color: ['#2f6fed', '#f59e0b'],
      tooltip: { trigger: 'axis' },
      legend: { top: 0 },
      grid: { left: 36, right: 12, top: 24, bottom: 24 },
      xAxis: { type: 'category', data: x, axisLabel: { rotate: 20 } },
      yAxis: { type: 'value' },
      series: [
        { name: metricA, type: 'bar', data: y1 },
        { name: metricB, type: 'bar', data: y2 }
      ]
    }
  }

  if (chartType === 'kpi') {
    const total = y1.reduce((a, b) => a + b, 0)
    return {
      xAxis: { show: false, type: 'value' },
      yAxis: { show: false, type: 'value' },
      series: [{ type: 'bar', data: [total], barWidth: 80, itemStyle: { color: '#2f6fed' } }],
      graphic: [
        {
          type: 'text',
          left: 'center',
          top: '44%',
          style: { text: String(total), font: '700 24px "JetBrains Mono"', fill: '#101828' }
        },
        {
          type: 'text',
          left: 'center',
          top: '63%',
          style: { text: metricA, font: '12px "Source Sans 3"', fill: '#667085' }
        }
      ]
    }
  }

  return null
}

function WidgetCard({ widget, payload, active, onClick, onCrossFilter, onRegisterPngExporter }: WidgetCardProps) {
  const chartRef = useRef<HTMLDivElement | null>(null)
  const echartsRef = useRef<echarts.ECharts | null>(null)

  useEffect(() => {
    const chartType = (widget.chart || 'table').toLowerCase()
    if (chartType === 'table') {
      if (echartsRef.current) {
        echartsRef.current.dispose()
        echartsRef.current = null
      }
      onRegisterPngExporter(null)
      return
    }

    const node = chartRef.current
    if (!node || !payload) {
      onRegisterPngExporter(null)
      return
    }

    if (!echartsRef.current) {
      echartsRef.current = echarts.init(node)
      echartsRef.current.on('click', (params) => {
        const name = params?.name
        if (name !== null && name !== undefined) {
          onCrossFilter(String(name))
        }
      })
    }

    const option = optionForPayload(payload)
    if (option) {
      echartsRef.current.setOption(option, true)
      echartsRef.current.resize()
      onRegisterPngExporter(() => echartsRef.current?.getDataURL({
        type: 'png',
        pixelRatio: 2,
        backgroundColor: '#ffffff'
      }) || null)
    }

    const onResize = () => {
      echartsRef.current?.resize()
    }
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
    }
  }, [widget.chart, payload, onCrossFilter, onRegisterPngExporter])

  useEffect(() => {
    return () => {
      onRegisterPngExporter(null)
      if (echartsRef.current) {
        echartsRef.current.dispose()
        echartsRef.current = null
      }
    }
  }, [onRegisterPngExporter])

  const rows = payload?.rows || []
  const chartType = (widget.chart || 'table').toLowerCase()

  return (
    <article
      className={`widget ${active ? 'active' : ''}`}
      style={{
        gridColumn: `${(widget.position?.x || 0) + 1} / span ${widget.position?.w || 6}`,
        gridRow: `${(widget.position?.y || 0) + 1} / span ${widget.position?.h || 4}`
      }}
      onClick={onClick}
    >
      <div className="widget-head">
        <div className="widget-title">{widget.title || widget.query_id}</div>
        <div className="widget-type">{widget.chart || 'table'}</div>
      </div>
      <div className="widget-body">
        {chartType === 'table' ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  {rows[0]
                    ? Object.keys(rows[0]).map((k) => <th key={k}>{k}</th>)
                    : <th>No Data</th>}
                </tr>
              </thead>
              <tbody>
                {rows.slice(0, 8).map((row, idx) => (
                  <tr key={idx}>
                    {Object.values(row).map((v, i) => <td key={i}>{String(v)}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="chart-canvas" ref={chartRef} />
        )}
      </div>
      <div className="widget-foot">
        <span>rows: {payload?.row_count ?? 0}</span>
        <span>{widget.query_id}</span>
      </div>
    </article>
  )
}

function serializeFilterValue(value: FilterValue): string {
  if (value === null) return ''
  if (Array.isArray(value)) return value.join(',')
  if (typeof value === 'object') return `${value.from || ''}..${value.to || ''}`
  return value.trim()
}

function normalizeFilter(def: FilterDef, raw: string): FilterValue {
  const mode = (def.suggested_widget || 'select').toLowerCase()
  const text = raw.trim()
  if (!text) return null

  if (mode === 'multi_select') {
    return text.split(',').map((v) => v.trim()).filter(Boolean)
  }

  return text
}

function App() {
  const [sessionId] = useState<string>(() => getOrCreateSessionId())
  const [backendUrl, setBackendUrl] = useState<string>(
    localStorage.getItem('sql2bi_backend') || DEFAULT_BACKEND_URL
  )
  const [sqlPath, setSqlPath] = useState<string>(DEFAULT_SQL_MD_PATH)
  const [dashboard, setDashboard] = useState<DashboardSpec | null>(null)
  const [filtersPayload, setFiltersPayload] = useState<FiltersPayload>({ global_filters: [], widget_filters: {} })
  const [globalFilterValues, setGlobalFilterValues] = useState<Record<string, FilterValue>>({})
  const [worksheetFilterValues, setWorksheetFilterValues] = useState<Record<string, Record<string, FilterValue>>>({})
  const [widgetData, setWidgetData] = useState<Record<string, QueryDataPayload>>({})
  const [selectedQueryId, setSelectedQueryId] = useState<string | null>(null)
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string>('')
  const [reportTheme, setReportTheme] = useState<string>('adhoc-analysis')
  const [actionMessage, setActionMessage] = useState<string>('')
  const [reportResult, setReportResult] = useState<QueryReportResponse | null>(null)
  const [exporting, setExporting] = useState<boolean>(false)
  const pngExportersRef = useRef<Record<string, () => string | null>>({})

  const api = useMemo(() => new Sql2BiApi(backendUrl, sessionId), [backendUrl, sessionId])

  const currentPage = dashboard?.pages?.[0]
  const widgets = currentPage?.widgets || []
  const buildMergedFilters = useCallback((queryId: string): Record<string, string> => {
    const merged: Record<string, string> = {}

    Object.entries(globalFilterValues).forEach(([field, value]) => {
      const serialized = serializeFilterValue(value)
      if (serialized) merged[field] = serialized
    })

    const local = worksheetFilterValues[queryId] || {}
    Object.entries(local).forEach(([field, value]) => {
      const serialized = serializeFilterValue(value)
      if (serialized) merged[field] = serialized
    })

    return merged
  }, [globalFilterValues, worksheetFilterValues])

  const loadDashboard = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [db, filters] = await Promise.all([api.currentDashboard(), api.filters()])
      setDashboard(db)
      setFiltersPayload(filters)
      if (!selectedQueryId && db.pages?.[0]?.widgets?.[0]?.query_id) {
        setSelectedQueryId(db.pages[0].widgets[0].query_id)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [api, selectedQueryId])

  const refreshWidgetData = useCallback(async () => {
    if (!currentPage) return

    try {
      const entries = await Promise.all(
        currentPage.widgets.map(async (w) => {
          const payload = await api.queryData(w.query_id, buildMergedFilters(w.query_id))
          return [w.query_id, payload] as const
        })
      )

      const map: Record<string, QueryDataPayload> = {}
      entries.forEach(([queryId, payload]) => {
        map[queryId] = payload
      })
      setWidgetData(map)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [api, buildMergedFilters, currentPage])

  useEffect(() => {
    loadDashboard().catch(() => {
      // handled in state
    })
  }, [loadDashboard])

  useEffect(() => {
    if (!currentPage) return
    refreshWidgetData().catch(() => {
      // handled in state
    })
  }, [currentPage, refreshWidgetData])

  const importSqlMd = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      await api.importSqlMd(sqlPath)
      await loadDashboard()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [api, loadDashboard, sqlPath])

  const selectedWidget = widgets.find((w) => w.query_id === selectedQueryId) || null
  const worksheetFilters = selectedQueryId ? (filtersPayload.widget_filters[selectedQueryId] || []) : []

  useEffect(() => {
    const nextTheme = slugifyTheme(selectedWidget?.title || dashboard?.name || 'adhoc-analysis')
    setReportTheme(nextTheme)
  }, [dashboard?.name, selectedWidget?.title, selectedWidget?.query_id])

  const downloadSelectedCsv = useCallback(async () => {
    if (!selectedWidget) return

    setExporting(true)
    setActionMessage('')
    try {
      const filters = buildMergedFilters(selectedWidget.query_id)
      const blob = await api.exportCsv(selectedWidget.query_id, filters)
      triggerDownload(blob, `${slugifyTheme(selectedWidget.title || selectedWidget.query_id)}-${sessionId}.csv`)
      setActionMessage(`CSV 已下载，session=${sessionId}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setExporting(false)
    }
  }, [api, buildMergedFilters, selectedWidget, sessionId])

  const downloadSelectedPng = useCallback(() => {
    if (!selectedWidget) return
    const exporter = pngExportersRef.current[selectedWidget.query_id]
    const dataUrl = exporter?.()
    if (!dataUrl) {
      setError('当前 widget 没有可导出的图表 PNG')
      return
    }

    fetch(dataUrl)
      .then((res) => res.blob())
      .then((blob) => {
        triggerDownload(blob, `${slugifyTheme(selectedWidget.title || selectedWidget.query_id)}-${sessionId}.png`)
        setActionMessage(`PNG 已下载，session=${sessionId}`)
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : String(err))
      })
  }, [selectedWidget, sessionId])

  const generateSelectedReport = useCallback(async () => {
    if (!selectedWidget) return

    setExporting(true)
    setActionMessage('')
    setError('')
    try {
      const filters = buildMergedFilters(selectedWidget.query_id)
      const chartPngDataUrl = pngExportersRef.current[selectedWidget.query_id]?.() || undefined
      const response = await api.createQueryReport(selectedWidget.query_id, {
        theme: reportTheme,
        filters,
        include_csv: true,
        chart_png_data_url: chartPngDataUrl
      })
      setReportResult(response)
      setActionMessage(`报告已生成到 ${response.report_root}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setExporting(false)
    }
  }, [api, buildMergedFilters, reportTheme, selectedWidget])

  return (
    <div className="app-root">
      <header className="top-toolbar">
        <div className="toolbar-left">
          <div className="brand">SQL2BI Service UI</div>
          <div className="backend-row">
            <label>Backend</label>
            <input
              value={backendUrl}
              onChange={(e) => setBackendUrl(e.target.value)}
              onBlur={() => localStorage.setItem('sql2bi_backend', backendUrl)}
            />
          </div>
        </div>
        <div className="toolbar-right">
          <div className="sql-row">
            <input value={sqlPath} onChange={(e) => setSqlPath(e.target.value)} placeholder="/abs/path/sql.md" />
            <button onClick={importSqlMd} disabled={loading}>Import sql.md</button>
            <button onClick={() => loadDashboard()} disabled={loading}>Reload</button>
          </div>
        </div>
      </header>

      <div className="main-layout">
        <aside className="left-pane">
          <div className="pane-title">Global Filters</div>
          {(filtersPayload.global_filters || []).map((f) => (
            <div className="filter-card" key={`gf-${f.field}`}>
              <label>{f.field}</label>
              <input
                placeholder={f.suggested_widget || 'value'}
                value={serializeFilterValue(globalFilterValues[f.field] ?? null)}
                onChange={(e) => {
                  const val = normalizeFilter(f, e.target.value)
                  setGlobalFilterValues((prev) => ({ ...prev, [f.field]: val }))
                }}
              />
              <div className="hint">{(f.operators || []).join(', ') || 'auto'}</div>
            </div>
          ))}
        </aside>

        <main className="center-pane">
          <div className="headline">
            <h1>{dashboard?.name || 'No dashboard loaded'}</h1>
            <div className="subline">
              {widgets.length} widgets
              {loading ? ' | loading...' : ''}
              {exporting ? ' | exporting...' : ''}
              {sessionId ? ` | session: ${sessionId}` : ''}
              {error ? ` | error: ${error}` : ''}
            </div>
          </div>
          <section className="grid-canvas">
            {widgets.map((w) => (
              <WidgetCard
                key={w.id}
                widget={w}
                payload={widgetData[w.query_id]}
                active={selectedQueryId === w.query_id}
                onClick={() => setSelectedQueryId(w.query_id)}
                onCrossFilter={(value) => {
                  const target = (filtersPayload.global_filters || [])[0]
                  if (!target) return
                  setGlobalFilterValues((prev) => ({ ...prev, [target.field]: value }))
                }}
                onRegisterPngExporter={(exporter) => {
                  if (exporter) {
                    pngExportersRef.current[w.query_id] = exporter
                  } else {
                    delete pngExportersRef.current[w.query_id]
                  }
                }}
              />
            ))}
          </section>
        </main>

        <aside className="right-pane">
          <div className="pane-title">Worksheet Filters</div>
          {selectedWidget ? (
            <>
              <div className="worksheet-title">{selectedWidget.title || selectedWidget.query_id}</div>
              <div className="session-chip">session: {sessionId}</div>
              <div className="export-card">
                <label>Report Theme</label>
                <input value={reportTheme} onChange={(e) => setReportTheme(slugifyTheme(e.target.value))} />
                <div className="export-actions">
                  <button onClick={downloadSelectedCsv} disabled={exporting}>Download CSV</button>
                  <button
                    onClick={downloadSelectedPng}
                    disabled={exporting || (selectedWidget.chart || 'table').toLowerCase() === 'table'}
                  >
                    Download PNG
                  </button>
                  <button onClick={generateSelectedReport} disabled={exporting}>Generate Report</button>
                </div>
                {actionMessage ? <div className="hint">{actionMessage}</div> : null}
                {reportResult && reportResult.query_id === selectedWidget.query_id ? (
                  <div className="report-meta">
                    <div><strong>theme</strong>: {reportResult.theme}</div>
                    <div><strong>version</strong>: {reportResult.version}</div>
                    <div><strong>root</strong>: {reportResult.report_root}</div>
                  </div>
                ) : null}
              </div>
              {worksheetFilters.length === 0 ? <div className="hint">No worksheet filters</div> : null}
              {worksheetFilters.map((f) => {
                const current = worksheetFilterValues[selectedWidget.query_id]?.[f.field] ?? null
                return (
                  <div className="filter-card" key={`wf-${selectedWidget.query_id}-${f.field}`}>
                    <label>{f.field}</label>
                    <input
                      placeholder={f.suggested_widget || 'value'}
                      value={serializeFilterValue(current)}
                      onChange={(e) => {
                        const val = normalizeFilter(f, e.target.value)
                        setWorksheetFilterValues((prev) => ({
                          ...prev,
                          [selectedWidget.query_id]: {
                            ...(prev[selectedWidget.query_id] || {}),
                            [f.field]: val
                          }
                        }))
                      }}
                    />
                    <div className="hint">{(f.operators || []).join(', ') || 'auto'}</div>
                  </div>
                )
              })}
            </>
          ) : (
            <div className="hint">No selected widget</div>
          )}
        </aside>
      </div>
    </div>
  )
}

export default App
