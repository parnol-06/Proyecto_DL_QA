import type { ReactNode } from 'react'
import { useStore } from '../../store/useStore'
import { useShallow } from 'zustand/react/shallow'

// ── Sparklines (pre-built path data) ─────────────────────────────────────────
const SPARKS = {
  tc:  'M0,18 L11,14 L22,17 L33,10 L44,13 L55,7 L66,10',
  bug: 'M0,12 L11,17 L22,10 L33,15 L44,11 L55,17 L66,12',
  cov: 'M0,16 L11,12 L22,14 L33,7  L44,10 L55,5  L66,7',
  scr: 'M0,18 L11,15 L22,18 L33,12 L44,16 L55,10 L66,13',
}

function Spark({ d, color }: { d: string; color: string }) {
  return (
    <svg viewBox="0 0 66 22" className="w-16 h-5 flex-shrink-0" fill="none">
      <path d={d} stroke={color} strokeWidth="1.8" fill="none"
            strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

// ── KPI icon SVGs ─────────────────────────────────────────────────────────────
const KpiIcon = {
  tc: (
    <svg width="11" height="11" viewBox="0 0 12 12" fill="none">
      <rect x="1.5" y="1.5" width="9" height="9" rx="2"
            stroke="currentColor" strokeWidth="1.1" fill="none"/>
      <path d="M3.5 6 L5.2 7.8 L8.5 4.2"
            stroke="currentColor" strokeWidth="1.3"
            strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  bug: (
    <svg width="11" height="11" viewBox="0 0 12 12" fill="none">
      <ellipse cx="6" cy="7.5" rx="2.5" ry="3"
               stroke="currentColor" strokeWidth="1" fill="none"/>
      <circle cx="6" cy="3.2" r="1.4"
              stroke="currentColor" strokeWidth="1" fill="none"/>
      <path d="M4.5 2.2 L3 1 M7.5 2.2 L9 1"
            stroke="currentColor" strokeWidth=".9" strokeLinecap="round"/>
      <path d="M3.5 6.5 L1.5 6 M3.5 8.5 L1.5 9
               M8.5 6.5 L10.5 6 M8.5 8.5 L10.5 9"
            stroke="currentColor" strokeWidth=".9" strokeLinecap="round"/>
    </svg>
  ),
  cov: (
    <svg width="11" height="11" viewBox="0 0 12 12" fill="none">
      <path d="M6 1 L11 3.5 L11 7 C11 9.5 8.5 11 6 11 C3.5 11 1 9.5 1 7 L1 3.5 Z"
            stroke="currentColor" strokeWidth="1" fill="none" strokeLinejoin="round"/>
      <path d="M4 6.5 L5.4 8 L8.2 5"
            stroke="currentColor" strokeWidth="1.2"
            strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  scr: (
    <svg width="11" height="11" viewBox="0 0 12 12" fill="none">
      <path d="M6 1 L7 4.5 L11 6 L7 7.5 L6 11 L5 7.5 L1 6 L5 4.5 Z"
            stroke="currentColor" strokeWidth="1" fill="none" strokeLinejoin="round"/>
    </svg>
  ),
}

// ── KPI Card ──────────────────────────────────────────────────────────────────
function KpiCard({ label, icon, value, spark, color, tintRgb }: {
  label: string
  icon: ReactNode
  value: string | number
  spark: string
  color: string
  tintRgb: string
}) {
  return (
    <div
      aria-label={`${label}: ${value}`}
      className="flex-1 flex flex-col justify-between px-4 py-3.5 rounded-xl min-w-0 kpi-card"
      style={{
        background: `linear-gradient(145deg, rgba(${tintRgb},.04) 0%, rgba(255,255,255,.01) 85%)`,
        border: '1px solid rgba(255,255,255,.07)',
      }}
    >
      <div className="flex items-center justify-between mb-1">
        <span className="text-[9px] font-mono uppercase tracking-[.13em] text-qa-muted">{label}</span>
        <div style={{ color: '#64647a', opacity: .7 }} aria-hidden="true">{icon}</div>
      </div>
      <div className="flex items-end justify-between gap-2">
        <span className="text-2xl font-head font-bold leading-none text-qa-text tabular-nums">{value}</span>
        <Spark d={spark} color={color} />
      </div>
    </div>
  )
}

// ── KPI Bar (top of main content) ────────────────────────────────────────────
export function Header() {
  const { result, overallScore } = useStore(useShallow(s => ({
    result: s.result,
    overallScore: s.overallScore,
  })))

  const tcCount  = result?.test_cases?.length ?? '—'
  const bugCount = result?.potential_bugs?.length ?? '—'
  const covPct   = result?.coverage_summary?.estimated_coverage_percent != null
                   ? result.coverage_summary.estimated_coverage_percent + '%' : '—'
  const scoreVal = overallScore != null ? overallScore.toFixed(2) : '—'

  return (
    <div className="flex items-center gap-2 px-4 py-3 border-b shrink-0"
         style={{ background: '#09090e', borderColor: 'rgba(255,255,255,.05)' }}>
      <div className="flex gap-2 min-w-0 w-full">
        <KpiCard label="Test Cases" icon={KpiIcon.tc}  value={tcCount}  spark={SPARKS.tc}  color="#5B8DEF" tintRgb="91,141,239" />
        <KpiCard label="Bugs"       icon={KpiIcon.bug} value={bugCount} spark={SPARKS.bug} color="#f87171" tintRgb="248,113,113" />
        <KpiCard label="Coverage"   icon={KpiIcon.cov} value={covPct}   spark={SPARKS.cov} color="#34d399" tintRgb="52,211,153"  />
        <KpiCard label="Score"      icon={KpiIcon.scr} value={scoreVal} spark={SPARKS.scr} color="#fbbf24" tintRgb="251,191,36"  />
      </div>
    </div>
  )
}
