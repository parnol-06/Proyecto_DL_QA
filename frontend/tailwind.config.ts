import type { Config } from 'tailwindcss'
import qaPreset from './tailwind-preset.js'

export default {
  presets: [qaPreset],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        'qa-bg':     '#09090e',
        'qa-s1':     '#0f0f18',
        'qa-s2':     '#151520',
        'qa-s3':     '#1c1c2a',
        'qa-s4':     '#242435',
        'qa-accent':  '#5B8DEF',
        'qa-accent2': '#60A5FA',
        'qa-accent3': 'rgba(91,141,239,0.7)',
        'qa-green':   '#34d399',
        'qa-red':     '#f87171',
        'qa-amber':   '#fbbf24',
        'qa-cyan':    '#22d3ee',
        'qa-pink':    '#e879a0',
        'qa-text':    '#eaeaf4',
        'qa-muted':   '#64647a',
        'qa-muted2':  '#8e8ea8',
        'qa-muted3':  '#aeaec8',
      },
      fontFamily: {
        head: ['Syne', 'sans-serif'],
      },
      borderRadius: {
        xs:      '5px',
        sm:      '7px',
        DEFAULT: '11px',
        lg:      '14px',
        xl:      '18px',
      },
      boxShadow: {
        'glow-accent': '0 0 20px rgba(124,109,250,.18)',
        'glow-green':  '0 0 12px rgba(52,211,153,.22)',
        'glow-red':    '0 0 12px rgba(248,113,113,.22)',
        'elevation':   '0 4px 24px rgba(0,0,0,.35)',
        'kpi':         '0 6px 24px rgba(0,0,0,.3)',
      },
      backgroundImage: {
        'grad-accent': 'linear-gradient(135deg, #7c6dfa 0%, #5b4fe6 100%)',
        'grad-eval':   'linear-gradient(135deg, #6c5ef5 0%, #9b7ef8 100%)',
        'grad-glass':  'linear-gradient(145deg, rgba(255,255,255,.055) 0%, rgba(255,255,255,.01) 100%)',
      },
      animation: {
        'pulse-slow': 'livePulse 2s ease-in-out infinite',
        'shimmer':    'shimmer 1.6s ease-in-out infinite',
        'spin-fast':  'spin .7s linear infinite',
      },
    },
  },
  plugins: [],
} satisfies Config
