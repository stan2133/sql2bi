import type { ThemeSpec, UiSpec } from '../types'

const HEX_COLOR_RE = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/

export type UiPreset = 'dashboard' | 'sunset' | 'mint' | 'graphite' | 'midnight'
export type LayoutMode = 'classic' | 'focus'

export type UiOverrides = {
  preset: UiPreset
  theme: Partial<ThemeSpec>
  chart_palette: string[]
  shadow_level: number | null
}

type ThemePresetDef = {
  label: string
  ui: UiSpec
}

export type ResolvedTheme = {
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

export const DEFAULT_THEME: ResolvedTheme = {
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

export const DEFAULT_CHART_PALETTE = ['#0ea5e9', '#f59e0b', '#14b8a6', '#f43f5e', '#8b5cf6']

export const THEME_PRESETS: Record<Exclude<UiPreset, 'dashboard'>, ThemePresetDef> = {
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

export const DEFAULT_UI_OVERRIDES: UiOverrides = {
  preset: 'dashboard',
  theme: {},
  chart_palette: [],
  shadow_level: null
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

export function isUiPreset(value: string): value is UiPreset {
  return value === 'dashboard' || value === 'sunset' || value === 'mint' || value === 'graphite' || value === 'midnight'
}

export function isLayoutMode(value: string): value is LayoutMode {
  return value === 'classic' || value === 'focus'
}

export function normalizeHexColor(value: string | undefined, fallback: string): string {
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

export function withAlpha(hex: string, alpha: number, fallback: string): string {
  const rgb = hexToRgb(hex)
  if (!rgb) return fallback
  return `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${clamp(alpha, 0, 1)})`
}

export function isColorDark(hex: string): boolean {
  const rgb = hexToRgb(hex)
  if (!rgb) return false
  const brightness = (rgb.r * 299 + rgb.g * 587 + rgb.b * 114) / 1000
  return brightness < 145
}

export function formatKpiValue(value: number): string {
  if (!Number.isFinite(value)) return '-'
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (Math.abs(value) >= 1_000) return `${(value / 1_000).toFixed(1)}K`
  return String(Math.round(value * 100) / 100)
}

export function normalizePalette(source: string[] | undefined, fallback: string[] = DEFAULT_CHART_PALETTE): string[] {
  const pool = (source || []).map((c, idx) => normalizeHexColor(c, fallback[idx % fallback.length])).slice(0, 5)
  while (pool.length < 5) {
    pool.push(fallback[pool.length % fallback.length])
  }
  return pool
}

export function mergeTheme(...parts: Array<Partial<ThemeSpec> | undefined>): ResolvedTheme {
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

export function buildCardShadow(level: number): string {
  if (level <= 0) return 'none'
  const y = Math.max(2, Math.round(level * 0.45))
  const blur = Math.max(8, Math.round(level * 2.6))
  const alpha = Math.min(0.22, 0.04 + level * 0.007)
  return `0 ${y}px ${blur}px rgba(15, 23, 42, ${alpha.toFixed(3)})`
}
