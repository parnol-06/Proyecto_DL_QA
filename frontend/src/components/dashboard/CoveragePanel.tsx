import { catBadgeClass, catLabel } from '../../lib/utils'
import type { CoverageSummary } from '../../types'

interface Props { cov: CoverageSummary }

export function CoveragePanel({ cov }: Props) {
  const pct     = Math.round(cov.estimated_coverage_percent || 0)
  const r       = 52
  const circ    = 2 * Math.PI * r
  const dash    = Math.max(0, Math.min(circ, (pct / 100) * circ))
  const gap     = circ - dash
  const ringColor = pct >= 80 ? '#34d399' : pct >= 60 ? '#7c6dfa' : '#fbbf24'
  const covered   = cov.categories_covered || []
  const missing   = cov.missing_areas || []
  const total     = cov.total_test_cases || 0

  return (
    <div className="rounded-lg p-4 mt-3" style={{ background: '#0f0f18', border: '1px solid rgba(255,255,255,.07)' }}>
      <div className="flex items-start gap-6 mb-4">
        {/* Donut */}
        <div className="flex-shrink-0">
          <svg width="130" height="130" viewBox="0 0 140 140" role="img" aria-label={`Estimated coverage: ${pct}%`}>
            <circle cx="70" cy="70" r={r} fill="none" stroke="rgba(255,255,255,.06)" strokeWidth="10" />
            <circle
              cx="70" cy="70" r={r} fill="none" stroke={ringColor} strokeWidth="10"
              strokeDasharray={`${dash.toFixed(2)} ${gap.toFixed(2)}`}
              strokeLinecap="round"
              transform="rotate(-90 70 70)"
              style={{ transition: 'stroke-dasharray .9s ease' }}
            />
            <text x="70" y="66" textAnchor="middle" fontSize="22" fontWeight="800" fill={ringColor}>{pct}%</text>
            <text x="70" y="80" textAnchor="middle" fontSize="10" fill="#64647a">coverage</text>
          </svg>
        </div>

        {/* Stats column */}
        <div className="flex flex-col gap-3 pt-2">
          {[
            { n: total,           lbl: 'Test Cases' },
            { n: covered.length,  lbl: 'Categories' },
            { n: missing.length,  lbl: 'Uncovered', warn: missing.length > 0 },
          ].map(({ n, lbl, warn }) => (
            <div key={lbl} className="flex flex-col">
              <span className="text-2xl font-head font-bold leading-none" style={{ color: warn ? '#fbbf24' : '#eaeaf4' }}>{n}</span>
              <span className="text-[10px] font-mono text-qa-muted mt-0.5">{lbl}</span>
            </div>
          ))}
        </div>
      </div>

      {covered.length > 0 && (
        <>
          <p className="section-label mb-2">Covered categories</p>
          <div className="flex flex-wrap gap-1 mb-3">
            {covered.map(c => (
              <span key={c} className={`badge ${catBadgeClass(c)}`}>{catLabel(c)}</span>
            ))}
          </div>
        </>
      )}

      {missing.length > 0 ? (
        <>
          <p className="section-label mb-1.5">Uncovered areas</p>
          <div className="flex flex-col gap-1">
            {missing.map(a => (
              <div key={a} className="text-[11px] font-mono text-qa-amber px-2 py-1 rounded"
                   style={{ background: 'rgba(251,191,36,.06)', border: '1px solid rgba(251,191,36,.15)' }}>
                {a}
              </div>
            ))}
          </div>
        </>
      ) : (
        <p className="text-[11px] font-mono" style={{ color: '#34d399' }}>✓ All areas covered</p>
      )}
    </div>
  )
}
