import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import * as echarts from 'echarts'
import { Sql2BiApi } from './api'
import type {
  DashboardSpec,
  FilterDef,
  FilterValue,
  FiltersPayload,
  QueryDataPayload,
  ThemeSpec,
  UiSpec,
  WidgetSpec
} from './types'

const DEFAULT_BACKEND_URL = 'http://127.0.0.1:18000'
const DEFAULT_SQL_MD_PATH = '/abs/path/sql.md'
const UI_OVERRIDES_KEY = 'sql2bi_ui_overrides_v1'
const LAYOUT_MODE_KEY = 'sql2bi_layout_mode_v1'
const ECHARTS_THEME_NAME = 'sql2bi_dynamic_theme_v1'

const HEX_COLOR_RE = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/

type UiPreset = 'dashboard' | 'sunset' | 'mint' | 'graphite' | 'midnight'
type LayoutMode = 'classic' | 'focus'

type UiOverrides = {
  preset: UiPreset
  theme: Partial<ThemeSpec>
  chart_palette: string[]
  shadow_level: number | null
}

type ThemePresetDef = {
  label: string
  ui: UiSpec
}

type ResolvedTheme = {
  name: string
  font_family: string
  app_bg: string
  canvas_bg: string
  panel_bg: string
  line_soft: string
  line_strong: string
  text_main: string
  text_sub: string
  text_mute: string
  brand: string
  brand_weak: string
  radius_sm: number
  radius_md: number
  card_shadow: string
}

type WidgetVisual = {
  palette: string[]
  textMain: string
  textSub: string
  textMute: string
  brand: string
  lineSoft: string
  lineStrong: string
}

type WidgetCardProps = {
  widget: WidgetSpec
  payload?: QueryDataPayload
  active: boolean
  themeName: string
  visual: WidgetVisual
  onClick: () => void
  onCrossFilter: (value: string) => void
}

const DEFAULT_THEME: ResolvedTheme = {
  name: 'studio_default',
  font_family: '"Source Sans 3", "Noto Sans SC", sans-serif',
  app_bg: '#f5f7fb',
  canvas_bg: '#eef2ff',
  panel_bg: '#ffffff',
  line_soft: '#dce4f3',
  line_strong: '#c7d4ec',
  text_main: '#0f172a',
  text_sub: '#334155',
  text_mute: '#64748b',
  brand: '#0ea5e9',
  brand_weak: '#e0f2fe',
  radius_sm: 8,
  radius_md: 14,
  card_shadow: '0 10px 28px rgba(15, 23, 42, 0.08)'
}

const DEFAULT_CHART_PALETTE = ['#0ea5e9', '#f59e0b', '#14b8a6', '#f43f5e', '#8b5cf6']

const THEME_PRESETS: Record<Exclude<UiPreset, 'dashboard'>, ThemePresetDef> = {
  sunset: {
    label: 'Sunset Glow',
    ui: {
      theme: {
        name: 'sunset_glow',
        app_bg: '#fff7ed',
        canvas_bg: '#ffedd5',
        panel_bg: '#ffffff',
        line_soft: '#fed7aa',
        line_strong: '#fdba74',
        text_main: '#7c2d12',
        text_sub: '#9a3412',
        text_mute: '#b45309',
        brand: '#f97316',
        brand_weak: '#ffedd5',
        radius_sm: 10,
        radius_md: 16,
        card_shadow: '0 12px 28px rgba(154, 52, 18, 0.16)'
      },
      chart_palette: ['#f97316', '#fb7185', '#f59e0b', '#2dd4bf', '#a855f7']
    }
  },
  mint: {
    label: 'Mint Pulse',
    ui: {
      theme: {
        name: 'mint_pulse',
        app_bg: '#f0fdfa',
        canvas_bg: '#d1fae5',
        panel_bg: '#ffffff',
        line_soft: '#a7f3d0',
        line_strong: '#6ee7b7',
        text_main: '#064e3b',
        text_sub: '#065f46',
        text_mute: '#047857',
        brand: '#10b981',
        brand_weak: '#d1fae5',
        radius_sm: 9,
        radius_md: 15,
        card_shadow: '0 10px 24px rgba(4, 120, 87, 0.14)'
      },
      chart_palette: ['#10b981', '#0ea5e9', '#f59e0b', '#ef4444', '#6366f1']
    }
  },
  graphite: {
    label: 'Graphite Lab',
    ui: {
      theme: {
        name: 'graphite_lab',
        app_bg: '#f8fafc',
        canvas_bg: '#e2e8f0',
        panel_bg: '#ffffff',
        line_soft: '#cbd5e1',
        line_strong: '#94a3b8',
        text_main: '#111827',
        text_sub: '#1f2937',
        text_mute: '#475569',
        brand: '#2563eb',
        brand_weak: '#dbeafe',
        radius_sm: 7,
        radius_md: 12,
        card_shadow: '0 10px 24px rgba(15, 23, 42, 0.14)'
      },
      chart_palette: ['#2563eb', '#0891b2', '#f59e0b', '#db2777', '#16a34a']
    }
  },
  midnight: {
    label: 'Midnight Ops',
    ui: {
      theme: {
        name: 'midnight_ops',
        app_bg: '#0b1220',
        canvas_bg: '#111827',
        panel_bg: '#172033',
        line_soft: '#25324a',
        line_strong: '#334766',
        text_main: '#e5edf8',
        text_sub: '#b5c5df',
        text_mute: '#8aa0c0',
        brand: '#22d3ee',
        brand_weak: '#0c4a6e',
        radius_sm: 8,
        radius_md: 14,
        card_shadow: '0 14px 28px rgba(2, 6, 23, 0.42)'
      },
      chart_palette: ['#22d3ee', '#a78bfa', '#f59e0b', '#34d399', '#fb7185']
    }
  }
}

const DEFAULT_UI_OVERRIDES: UiOverrides = {
  preset: 'dashboard',
  theme: {},
  chart_palette: [],
  shadow_level: null
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

function isUiPreset(value: string): value is UiPreset {
  return value === 'dashboard' || value === 'sunset' || value === 'mint' || value === 'graphite' || value === 'midnight'
}

function isLayoutMode(value: string): value is LayoutMode {
  return value === 'classic' || value === 'focus'
}

function normalizeHexColor(value: string | undefined, fallback: string): string {
  if (!value) return fallback
  const text = value.trim()
  if (!HEX_COLOR_RE.test(text)) return fallback
  if (text.length === 4) {
    const r = text[1]
    const g = text[2]
    const b = text[3]
    return `#${r}${r}${g}${g}${b}${b}`.toLowerCase()
  }
  return text.toLowerCase()
}

function hexToRgb(hex: string): { r: number; g: number; b: number } | null {
  const normalized = normalizeHexColor(hex, '')
  if (!normalized) return null
  const m = /^#([0-9a-f]{6})$/i.exec(normalized)
  if (!m) return null
  const num = Number.parseInt(m[1], 16)
  return {
    r: (num >> 16) & 255,
    g: (num >> 8) & 255,
    b: num & 255
  }
}

function withAlpha(hex: string, alpha: number, fallback: string): string {
  const rgb = hexToRgb(hex)
  if (!rgb) return fallback
  return `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${clamp(alpha, 0, 1)})`
}

function isColorDark(hex: string): boolean {
  const rgb = hexToRgb(hex)
  if (!rgb) return false
  const brightness = (rgb.r * 299 + rgb.g * 587 + rgb.b * 114) / 1000
  return brightness < 145
}

function formatKpiValue(value: number): string {
  if (!Number.isFinite(value)) return '-'
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (Math.abs(value) >= 1_000) return `${(value / 1_000).toFixed(1)}K`
  return String(Math.round(value * 100) / 100)
}

function normalizePalette(source: string[] | undefined, fallback: string[] = DEFAULT_CHART_PALETTE): string[] {
  const pool = (source || []).map((c, idx) => normalizeHexColor(c, fallback[idx % fallback.length])).slice(0, 5)
  while (pool.length < 5) {
    pool.push(fallback[pool.length % fallback.length])
  }
  return pool
}

function mergeTheme(...parts: Array<Partial<ThemeSpec> | undefined>): ResolvedTheme {
  const raw: Partial<ThemeSpec> = {}
  parts.forEach((part) => {
    if (!part) return
    Object.assign(raw, part)
  })

  const brand = normalizeHexColor(raw.brand, DEFAULT_THEME.brand)
  const brandWeakFallback = withAlpha(brand, 0.14, DEFAULT_THEME.brand_weak)

  return {
    name: String(raw.name || DEFAULT_THEME.name),
    font_family: String(raw.font_family || DEFAULT_THEME.font_family),
    app_bg: normalizeHexColor(raw.app_bg, DEFAULT_THEME.app_bg),
    canvas_bg: normalizeHexColor(raw.canvas_bg, DEFAULT_THEME.canvas_bg),
    panel_bg: normalizeHexColor(raw.panel_bg, DEFAULT_THEME.panel_bg),
    line_soft: normalizeHexColor(raw.line_soft, DEFAULT_THEME.line_soft),
    line_strong: normalizeHexColor(raw.line_strong, DEFAULT_THEME.line_strong),
    text_main: normalizeHexColor(raw.text_main, DEFAULT_THEME.text_main),
    text_sub: normalizeHexColor(raw.text_sub, DEFAULT_THEME.text_sub),
    text_mute: normalizeHexColor(raw.text_mute, DEFAULT_THEME.text_mute),
    brand,
    brand_weak: normalizeHexColor(raw.brand_weak, brandWeakFallback),
    radius_sm: clamp(Number(raw.radius_sm ?? DEFAULT_THEME.radius_sm), 4, 24),
    radius_md: clamp(Number(raw.radius_md ?? DEFAULT_THEME.radius_md), 8, 28),
    card_shadow: String(raw.card_shadow || DEFAULT_THEME.card_shadow)
  }
}

function buildCardShadow(level: number): string {
  if (level <= 0) return 'none'
  const y = Math.max(2, Math.round(level * 0.45))
  const blur = Math.max(8, Math.round(level * 2.6))
  const alpha = Math.min(0.22, 0.04 + level * 0.007)
  return `0 ${y}px ${blur}px rgba(15, 23, 42, ${alpha.toFixed(3)})`
}

function loadUiOverrides(): UiOverrides {
  try {
    const raw = localStorage.getItem(UI_OVERRIDES_KEY)
    if (!raw) return DEFAULT_UI_OVERRIDES

    const parsed = JSON.parse(raw) as Partial<UiOverrides>
    const preset = typeof parsed.preset === 'string' && isUiPreset(parsed.preset) ? parsed.preset : 'dashboard'
    const theme = parsed.theme && typeof parsed.theme === 'object' ? parsed.theme : {}
    const palette = Array.isArray(parsed.chart_palette) ? parsed.chart_palette.filter((v): v is string => typeof v === 'string') : []
    const shadowLevel =
      typeof parsed.shadow_level === 'number' && Number.isFinite(parsed.shadow_level)
        ? clamp(Math.round(parsed.shadow_level), 0, 24)
        : null

    return {
      preset,
      theme,
      chart_palette: palette,
      shadow_level: shadowLevel
    }
  } catch {
    return DEFAULT_UI_OVERRIDES
  }
}

function loadLayoutMode(): LayoutMode {
  const raw = localStorage.getItem(LAYOUT_MODE_KEY)
  return raw && isLayoutMode(raw) ? raw : 'classic'
}

function buildEchartsTheme(theme: ResolvedTheme, palette: string[]): Record<string, unknown> {
  return {
    color: palette,
    backgroundColor: 'transparent',
    textStyle: {
      color: theme.text_sub,
      fontFamily: theme.font_family
    },
    legend: {
      textStyle: {
        color: theme.text_sub
      }
    },
    categoryAxis: {
      axisLine: {
        lineStyle: {
          color: theme.line_strong
        }
      },
      axisLabel: {
        color: theme.text_sub
      },
      splitLine: {
        lineStyle: {
          color: theme.line_soft
        }
      }
    },
    valueAxis: {
      axisLine: {
        lineStyle: {
          color: theme.line_strong
        }
      },
      axisLabel: {
        color: theme.text_sub
      },
      splitLine: {
        lineStyle: {
          color: theme.line_soft
        }
      }
    },
    line: {
      lineStyle: { width: 2.2 },
      symbol: 'circle',
      symbolSize: 6
    },
    bar: {
      itemStyle: {
        borderRadius: [6, 6, 0, 0]
      }
    }
  }
}

function optionForPayload(payload: QueryDataPayload, visual: WidgetVisual): echarts.EChartsOption | null {
  const chartType = (payload.chart || 'table').toLowerCase()
  const rows = payload.rows || []
  const dim = payload.dimension
  const metricA = payload.metrics[0]
  const metricB = payload.metrics[1]

  const x = rows.map((r) => String(r[dim]))
  const y1 = rows.map((r) => Number(r[metricA] || 0))
  const y2 = rows.map((r) => Number(r[metricB] || 0))

  const axis = {
    axisLabel: { color: visual.textSub },
    axisLine: { lineStyle: { color: visual.lineStrong } }
  }

  if (chartType === 'line') {
    return {
      color: visual.palette,
      tooltip: {
        trigger: 'axis'
      },
      grid: { left: 36, right: 12, top: 18, bottom: 24 },
      xAxis: { type: 'category', data: x, ...axis },
      yAxis: { type: 'value', ...axis, splitLine: { lineStyle: { color: visual.lineSoft } } },
      series: [{ type: 'line', smooth: true, data: y1 }]
    }
  }

  if (chartType === 'bar') {
    return {
      color: visual.palette,
      tooltip: { trigger: 'axis' },
      grid: { left: 36, right: 12, top: 18, bottom: 24 },
      xAxis: { type: 'category', data: x, axisLabel: { rotate: 25, color: visual.textSub }, axisLine: axis.axisLine },
      yAxis: { type: 'value', ...axis, splitLine: { lineStyle: { color: visual.lineSoft } } },
      series: [{ type: 'bar', data: y1 }]
    }
  }

  if (chartType === 'grouped_bar') {
    return {
      color: visual.palette,
      tooltip: { trigger: 'axis' },
      legend: { top: 0, textStyle: { color: visual.textSub } },
      grid: { left: 36, right: 12, top: 24, bottom: 24 },
      xAxis: { type: 'category', data: x, axisLabel: { rotate: 20, color: visual.textSub }, axisLine: axis.axisLine },
      yAxis: { type: 'value', ...axis, splitLine: { lineStyle: { color: visual.lineSoft } } },
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
      series: [{ type: 'bar', data: [total], barWidth: 80, itemStyle: { color: visual.brand } }],
      graphic: [
        {
          type: 'text',
          left: 'center',
          top: '44%',
          style: { text: String(total), font: '700 24px "JetBrains Mono"', fill: visual.textMain }
        },
        {
          type: 'text',
          left: 'center',
          top: '63%',
          style: { text: metricA, font: '12px "Source Sans 3"', fill: visual.textMute }
        }
      ]
    }
  }

  return null
}

function WidgetCard({ widget, payload, active, themeName, visual, onClick, onCrossFilter }: WidgetCardProps) {
  const chartRef = useRef<HTMLDivElement | null>(null)
  const echartsRef = useRef<echarts.ECharts | null>(null)
  const chartThemeNameRef = useRef<string>('')

  useEffect(() => {
    const chartType = (widget.chart || 'table').toLowerCase()
    if (chartType === 'table') {
      if (echartsRef.current) {
        echartsRef.current.dispose()
        echartsRef.current = null
      }
      return
    }

    const node = chartRef.current
    if (!node || !payload) return

    if (!echartsRef.current || chartThemeNameRef.current !== themeName) {
      if (echartsRef.current) {
        echartsRef.current.dispose()
      }
      echartsRef.current = echarts.init(node, themeName)
      chartThemeNameRef.current = themeName
      echartsRef.current.on('click', (params) => {
        const name = params?.name
        if (name !== null && name !== undefined) {
          onCrossFilter(String(name))
        }
      })
    }

    const option = optionForPayload(payload, visual)
    if (option) {
      echartsRef.current.setOption(option, true)
      echartsRef.current.resize()
    }

    const onResize = () => {
      echartsRef.current?.resize()
    }
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
    }
  }, [widget.chart, payload, themeName, visual, onCrossFilter])

  useEffect(() => {
    return () => {
      if (echartsRef.current) {
        echartsRef.current.dispose()
        echartsRef.current = null
      }
    }
  }, [])

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
  const [uiOverrides, setUiOverrides] = useState<UiOverrides>(() => loadUiOverrides())
  const [layoutMode, setLayoutMode] = useState<LayoutMode>(() => loadLayoutMode())

  const api = useMemo(() => new Sql2BiApi(backendUrl), [backendUrl])

  const currentPage = dashboard?.pages?.[0]
  const widgets = currentPage?.widgets || []
  const dashboardUi = dashboard?.ui
  const selectedWidget = widgets.find((w) => w.query_id === selectedQueryId) || null
  const worksheetFilters = selectedQueryId ? (filtersPayload.widget_filters[selectedQueryId] || []) : []

  const presetUi = useMemo(() => {
    if (uiOverrides.preset === 'dashboard') return undefined
    return THEME_PRESETS[uiOverrides.preset].ui
  }, [uiOverrides.preset])

  const baseTheme = useMemo(() => {
    if (uiOverrides.preset === 'dashboard') {
      return mergeTheme(DEFAULT_THEME, dashboardUi?.theme)
    }
    return mergeTheme(DEFAULT_THEME, presetUi?.theme)
  }, [dashboardUi?.theme, presetUi?.theme, uiOverrides.preset])

  const activeTheme = useMemo(() => {
    const merged = mergeTheme(baseTheme, uiOverrides.theme)
    if (uiOverrides.shadow_level !== null) {
      return {
        ...merged,
        card_shadow: buildCardShadow(uiOverrides.shadow_level)
      }
    }
    return merged
  }, [baseTheme, uiOverrides.shadow_level, uiOverrides.theme])

  const basePalette = useMemo(() => {
    if (uiOverrides.preset === 'dashboard') {
      return normalizePalette(dashboardUi?.chart_palette, DEFAULT_CHART_PALETTE)
    }
    return normalizePalette(presetUi?.chart_palette, DEFAULT_CHART_PALETTE)
  }, [dashboardUi?.chart_palette, presetUi?.chart_palette, uiOverrides.preset])

  const activePalette = useMemo(
    () => normalizePalette(uiOverrides.chart_palette.length ? uiOverrides.chart_palette : basePalette, basePalette),
    [basePalette, uiOverrides.chart_palette]
  )

  const themePreviewPalette = useMemo(() => normalizePalette(activePalette, DEFAULT_CHART_PALETTE), [activePalette])

  const echartsTheme = useMemo(() => buildEchartsTheme(activeTheme, activePalette), [activeTheme, activePalette])

  const widgetVisual = useMemo<WidgetVisual>(
    () => ({
      palette: activePalette,
      textMain: activeTheme.text_main,
      textSub: activeTheme.text_sub,
      textMute: activeTheme.text_mute,
      brand: activeTheme.brand,
      lineSoft: activeTheme.line_soft,
      lineStrong: activeTheme.line_strong
    }),
    [activePalette, activeTheme]
  )

  const darkTheme = useMemo(() => isColorDark(activeTheme.app_bg), [activeTheme.app_bg])

  const kpiCards = useMemo(() => {
    return widgets
      .map((widget) => {
        const payload = widgetData[widget.query_id]
        if (!payload) return null
        const metricName = payload.metrics?.[0]
        if (!metricName) return null
        const rawValue = Number(payload.summary?.[metricName] ?? 0)
        return {
          queryId: widget.query_id,
          label: widget.title || widget.query_id,
          metricName,
          value: rawValue,
          text: formatKpiValue(rawValue)
        }
      })
      .filter((item): item is { queryId: string; label: string; metricName: string; value: number; text: string } => Boolean(item))
      .sort((a, b) => b.value - a.value)
      .slice(0, 6)
  }, [widgetData, widgets])

  const visibleWidgets = useMemo(() => {
    if (layoutMode !== 'focus') return widgets
    if (!selectedQueryId) return widgets
    return widgets.filter((w) => w.query_id === selectedQueryId)
  }, [layoutMode, selectedQueryId, widgets])

  useEffect(() => {
    localStorage.setItem(UI_OVERRIDES_KEY, JSON.stringify(uiOverrides))
  }, [uiOverrides])

  useEffect(() => {
    localStorage.setItem(LAYOUT_MODE_KEY, layoutMode)
  }, [layoutMode])

  useEffect(() => {
    const root = document.documentElement
    root.style.setProperty('--bg-app', activeTheme.app_bg)
    root.style.setProperty('--bg-canvas', activeTheme.canvas_bg)
    root.style.setProperty('--bg-panel', activeTheme.panel_bg)
    root.style.setProperty('--line-soft', activeTheme.line_soft)
    root.style.setProperty('--line-strong', activeTheme.line_strong)
    root.style.setProperty('--text-main', activeTheme.text_main)
    root.style.setProperty('--text-sub', activeTheme.text_sub)
    root.style.setProperty('--text-mute', activeTheme.text_mute)
    root.style.setProperty('--brand', activeTheme.brand)
    root.style.setProperty('--brand-weak', activeTheme.brand_weak)
    root.style.setProperty('--radius-sm', `${activeTheme.radius_sm}px`)
    root.style.setProperty('--radius-md', `${activeTheme.radius_md}px`)
    root.style.setProperty('--card-shadow', activeTheme.card_shadow)
    root.style.setProperty('--font-family-main', activeTheme.font_family)
    root.style.setProperty('--brand-ring', withAlpha(activeTheme.brand, 0.2, 'rgba(14, 165, 233, 0.2)'))
    root.style.setProperty('--brand-glow', withAlpha(activeTheme.brand, 0.12, 'rgba(14, 165, 233, 0.12)'))
  }, [activeTheme])

  useEffect(() => {
    echarts.registerTheme(ECHARTS_THEME_NAME, echartsTheme)
  }, [echartsTheme])

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
          const merged: Record<string, string> = {}

          Object.entries(globalFilterValues).forEach(([field, value]) => {
            const serialized = serializeFilterValue(value)
            if (serialized) merged[field] = serialized
          })

          const local = worksheetFilterValues[w.query_id] || {}
          Object.entries(local).forEach(([field, value]) => {
            const serialized = serializeFilterValue(value)
            if (serialized) merged[field] = serialized
          })

          const payload = await api.queryData(w.query_id, merged)
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
  }, [api, currentPage, globalFilterValues, worksheetFilterValues])

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

  const updateThemePatch = useCallback((patch: Partial<ThemeSpec>) => {
    setUiOverrides((prev) => ({
      ...prev,
      theme: {
        ...prev.theme,
        ...patch
      }
    }))
  }, [])

  const onPresetChange = useCallback((nextPresetText: string) => {
    const preset: UiPreset = isUiPreset(nextPresetText) ? nextPresetText : 'dashboard'
    const presetPalette = preset === 'dashboard' ? [] : normalizePalette(THEME_PRESETS[preset].ui.chart_palette)
    setUiOverrides({
      preset,
      theme: {},
      chart_palette: presetPalette,
      shadow_level: null
    })
  }, [])

  const onPaletteChange = useCallback((index: number, color: string) => {
    const normalized = normalizeHexColor(color, DEFAULT_CHART_PALETTE[index % DEFAULT_CHART_PALETTE.length])
    setUiOverrides((prev) => {
      const nextPalette = normalizePalette(prev.chart_palette.length ? prev.chart_palette : activePalette)
      nextPalette[index] = normalized
      return {
        ...prev,
        chart_palette: nextPalette
      }
    })
  }, [activePalette])

  const resetLocalTheme = useCallback(() => {
    setUiOverrides(DEFAULT_UI_OVERRIDES)
    localStorage.removeItem(UI_OVERRIDES_KEY)
  }, [])

  return (
    <div className={`app-root ${darkTheme ? 'theme-dark' : ''} layout-${layoutMode}`}>
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
            <select value={layoutMode} onChange={(e) => setLayoutMode(isLayoutMode(e.target.value) ? e.target.value : 'classic')}>
              <option value="classic">Layout: Classic</option>
              <option value="focus">Layout: Focus</option>
            </select>
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
              {widgets.length} widgets · mode: {layoutMode}
              {loading ? ' | loading...' : ''}
              {error ? ` | error: ${error}` : ''}
            </div>
          </div>

          {kpiCards.length > 0 ? (
            <section className="kpi-strip">
              {kpiCards.map((item) => (
                <button
                  key={`kpi-${item.queryId}`}
                  className={`kpi-card ${selectedQueryId === item.queryId ? 'active' : ''}`}
                  onClick={() => {
                    setSelectedQueryId(item.queryId)
                    setLayoutMode('focus')
                  }}
                >
                  <span className="kpi-label">{item.label}</span>
                  <span className="kpi-value">{item.text}</span>
                  <span className="kpi-metric">{item.metricName}</span>
                </button>
              ))}
            </section>
          ) : null}

          <section className={`grid-canvas ${layoutMode === 'focus' ? 'focus-mode' : ''}`}>
            {visibleWidgets.map((w) => (
              <WidgetCard
                key={w.id}
                widget={w}
                payload={widgetData[w.query_id]}
                active={selectedQueryId === w.query_id}
                themeName={ECHARTS_THEME_NAME}
                visual={widgetVisual}
                onClick={() => setSelectedQueryId(w.query_id)}
                onCrossFilter={(value) => {
                  const target = (filtersPayload.global_filters || [])[0]
                  if (!target) return
                  setGlobalFilterValues((prev) => ({ ...prev, [target.field]: value }))
                }}
              />
            ))}
          </section>
        </main>

        <aside className="right-pane">
          <div className="theme-studio">
            <div className="pane-title">Theme Studio</div>

            <div className="theme-field">
              <label>Preset</label>
              <select value={uiOverrides.preset} onChange={(e) => onPresetChange(e.target.value)}>
                <option value="dashboard">Use Dashboard Theme</option>
                <option value="sunset">{THEME_PRESETS.sunset.label}</option>
                <option value="mint">{THEME_PRESETS.mint.label}</option>
                <option value="graphite">{THEME_PRESETS.graphite.label}</option>
                <option value="midnight">{THEME_PRESETS.midnight.label}</option>
              </select>
            </div>

            <div className="theme-row">
              <div className="theme-field">
                <label>Brand</label>
                <input
                  type="color"
                  value={normalizeHexColor(activeTheme.brand, DEFAULT_THEME.brand)}
                  onChange={(e) => updateThemePatch({ brand: e.target.value, brand_weak: undefined })}
                />
              </div>
              <div className="theme-field">
                <label>Text</label>
                <input
                  type="color"
                  value={normalizeHexColor(activeTheme.text_main, DEFAULT_THEME.text_main)}
                  onChange={(e) => updateThemePatch({ text_main: e.target.value })}
                />
              </div>
            </div>

            <div className="theme-row">
              <div className="theme-field">
                <label>App Bg</label>
                <input
                  type="color"
                  value={normalizeHexColor(activeTheme.app_bg, DEFAULT_THEME.app_bg)}
                  onChange={(e) => updateThemePatch({ app_bg: e.target.value })}
                />
              </div>
              <div className="theme-field">
                <label>Panel Bg</label>
                <input
                  type="color"
                  value={normalizeHexColor(activeTheme.panel_bg, DEFAULT_THEME.panel_bg)}
                  onChange={(e) => updateThemePatch({ panel_bg: e.target.value })}
                />
              </div>
            </div>

            <div className="theme-slider">
              <label>Roundness ({Math.round(activeTheme.radius_md)}px)</label>
              <input
                type="range"
                min={8}
                max={24}
                value={Math.round(activeTheme.radius_md)}
                onChange={(e) => {
                  const radiusMd = clamp(Number(e.target.value), 8, 24)
                  updateThemePatch({
                    radius_md: radiusMd,
                    radius_sm: Math.max(4, radiusMd - 6)
                  })
                }}
              />
            </div>

            <div className="theme-slider">
              <label>Shadow ({uiOverrides.shadow_level ?? 10})</label>
              <input
                type="range"
                min={0}
                max={24}
                value={uiOverrides.shadow_level ?? 10}
                onChange={(e) => {
                  const value = clamp(Number(e.target.value), 0, 24)
                  setUiOverrides((prev) => ({ ...prev, shadow_level: value }))
                }}
              />
            </div>

            <div className="theme-field">
              <label>Chart Palette</label>
              <div className="palette-strip">
                {themePreviewPalette.map((color, idx) => (
                  <div className="palette-item" key={`palette-${idx}`}>
                    <span>{idx + 1}</span>
                    <input
                      type="color"
                      value={normalizeHexColor(color, DEFAULT_CHART_PALETTE[idx])}
                      onChange={(e) => onPaletteChange(idx, e.target.value)}
                    />
                  </div>
                ))}
              </div>
            </div>

            <div className="theme-actions">
              <button onClick={resetLocalTheme}>Reset Local Theme</button>
              <button
                onClick={() => setUiOverrides((prev) => ({ ...prev, chart_palette: [] }))}
              >
                Reset Palette
              </button>
            </div>
          </div>

          <div className="pane-title">Worksheet Filters</div>
          {selectedWidget ? (
            <>
              <div className="worksheet-title">{selectedWidget.title || selectedWidget.query_id}</div>
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
