import type { ResolvedTheme } from './themeUtils'

export function buildEchartsTheme(theme: ResolvedTheme, palette: string[]): Record<string, unknown> {
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
