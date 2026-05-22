import { useStore } from '../../store/useStore'
import type { MetricResult } from '../../types'

const METRIC_META = {
  coverage:              { label: 'Test Coverage',          threshold: 0.70, color: '#34d399' },
  relevancy:             { label: 'Relevancy',              threshold: 0.70, color: '#22d3ee' },
  consistency:           { label: 'Consistency',            threshold: 0.65, color: '#a78bfa' },
  specificity:           { label: 'Step Specificity',       threshold: 0.65, color: '#fbbf24' },
  nonfunctional_balance: { label: 'Non-Functional Balance', threshold: 0.60, color: '#e879a0' },
}

const METRIC_ACTIONS: Record<string, { fail?: string; warn?: string }> = {
  coverage:              { fail: 'Agrega casos para las funciones no cubiertas. Considera escenarios negativos y de borde.', warn: 'Faltan 1–2 escenarios para alcanzar el umbral. Revisa escenarios negativos.' },
  relevancy:             { fail: 'Algunos casos no están alineados al requerimiento. Usa "Regenerar" en los casos de categorías secundarias.', warn: 'Revisa casos de usabilidad/compatibilidad para asegurar que se relacionen con la historia.' },
  consistency:           { fail: 'Pasos y resultados esperados incoherentes. Usa ⟳ en los casos con menor coherencia.', warn: 'Revisa precondiciones duplicadas o resultados esperados genéricos.' },
  specificity:           { fail: 'Pasos demasiado genéricos. Sube la temperatura del modelo para obtener más detalle.', warn: 'Algunos pasos pueden especificar datos de prueba concretos.' },
  nonfunctional_balance: { fail: 'Activa las categorías Seguridad, Rendimiento y Usabilidad.', warn: 'Agrega contexto técnico en el campo "Contexto adicional".' },
}

interface MetricCardProps { metricKey: string; result?: MetricResult }

function MetricCard({ metricKey, result }: MetricCardProps) {
  const meta = METRIC_META[metricKey as keyof typeof METRIC_META]
  if (!meta) return null

  if (!result) {
    return (
      <div className="rounded-lg p-3" style={{ background: '#151520', border: '1px solid rgba(255,255,255,.06)' }}>
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-mono font-semibold text-qa-muted2">{meta.label}</span>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-sm" style={{ background: 'rgba(100,100,122,.2)', color: '#64647a' }}>PENDIENTE</span>
        </div>
        <div className="h-1.5 rounded-full" style={{ background: 'rgba(255,255,255,.06)' }} />
      </div>
    )
  }

  const pct = Math.round(result.score * 100)
  const passed = result.score >= meta.threshold
  const near = !passed && result.score >= meta.threshold - 0.10
  const status = passed ? 'pass' : near ? 'warn' : 'fail'
  const thresholdPct = Math.round(meta.threshold * 100)
  const action = !passed ? METRIC_ACTIONS[metricKey]?.[status as 'fail' | 'warn'] : null
  const showReason = result.reason && result.reason !== 'N/A' && !result.reason.startsWith('Error:') && result.reason.length > 5

  const statusColors = {
    pass: { bg: 'rgba(52,211,153,.12)', border: 'rgba(52,211,153,.25)', text: '#34d399', badge: '#34d399' },
    warn: { bg: 'rgba(251,191,36,.08)', border: 'rgba(251,191,36,.2)',  text: '#fbbf24', badge: '#fbbf24' },
    fail: { bg: 'rgba(248,113,113,.08)', border: 'rgba(248,113,113,.2)', text: '#f87171', badge: '#f87171' },
  }[status]

  return (
    <div className="rounded-lg p-3" style={{ background: statusColors.bg, border: `1px solid ${statusColors.border}` }}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-mono font-semibold" style={{ color: statusColors.text }}>{meta.label}</span>
        <div className="flex items-center gap-1.5">
          <span className="text-sm font-mono font-bold" style={{ color: statusColors.text }}>{result.score.toFixed(2)}</span>
          <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded-sm uppercase"
                style={{ background: statusColors.badge + '22', color: statusColors.badge, border: `1px solid ${statusColors.badge}40` }}>
            {status.toUpperCase()}
          </span>
        </div>
      </div>

      {/* Bar with threshold marker */}
      <div className="relative h-2 rounded-full mb-1.5" style={{ background: 'rgba(255,255,255,.08)' }}>
        <div className="h-full rounded-full transition-all duration-700"
             style={{ width: `${pct}%`, background: meta.color }} />
        <div className="absolute top-0 bottom-0 w-px"
             style={{ left: `${thresholdPct}%`, background: 'rgba(255,255,255,.4)' }}
             title={`Umbral: ${meta.threshold}`} />
      </div>
      <div className="flex justify-between items-center">
        <span className="text-[10px] font-mono text-qa-muted">{pct}%</span>
        <span className="text-[10px] font-mono text-qa-muted">umbral {thresholdPct}%</span>
      </div>

      {action && (
        <div className="mt-2 px-2 py-1.5 rounded text-[10px] font-mono"
             style={{ background: 'rgba(255,255,255,.04)', border: '1px solid rgba(255,255,255,.08)', color: '#8e8ea8' }}>
          💡 {action}
        </div>
      )}

      {showReason && (
        <details className="mt-2">
          <summary className="text-[10px] font-mono text-qa-muted cursor-pointer hover:text-qa-muted2">Ver razón del evaluador</summary>
          <p className="text-[10px] font-mono text-qa-muted2 mt-1">{result.reason.slice(0, 400)}</p>
        </details>
      )}
    </div>
  )
}

export function MetricsDashboard() {
  const evalMetrics = useStore(s => s.evalMetrics)
  const keys = Object.keys(METRIC_META) as (keyof typeof METRIC_META)[]

  return (
    <div className="space-y-2 panel-fade">
      {keys.map(k => <MetricCard key={k} metricKey={k} result={evalMetrics[k]} />)}
    </div>
  )
}

// Radar chart for the right panel
export function MetricsRadar() {
  const evalMetrics = useStore(s => s.evalMetrics)

  const KEYS: (keyof typeof METRIC_META)[] = [
    'coverage', 'relevancy', 'consistency', 'specificity', 'nonfunctional_balance',
  ]
  const scores = KEYS.map(k => evalMetrics[k]?.score ?? 0)
  const cx = 70, cy = 70, r = 50
  const n = KEYS.length
  const angles = KEYS.map((_, i) => (i * 2 * Math.PI) / n - Math.PI / 2)

  function pt(score: number, i: number) {
    const radius = score * r
    return [cx + radius * Math.cos(angles[i]), cy + radius * Math.sin(angles[i])] as [number, number]
  }

  const gridLevels = [0.25, 0.5, 0.75, 1]
  const polygonPoints = scores.map((s, i) => pt(s, i))
  const polyStr = polygonPoints.map(([x, y]) => `${x},${y}`).join(' ')

  return (
    <svg width="140" height="140" viewBox="0 0 140 140">
      {/* Grid */}
      {gridLevels.map(lvl => {
        const pts = angles.map(a => `${cx + lvl * r * Math.cos(a)},${cy + lvl * r * Math.sin(a)}`).join(' ')
        return <polygon key={lvl} points={pts} fill="none" stroke="rgba(255,255,255,.07)" strokeWidth="0.5" />
      })}
      {/* Axes */}
      {angles.map((a, i) => (
        <line key={i} x1={cx} y1={cy}
              x2={cx + r * Math.cos(a)} y2={cy + r * Math.sin(a)}
              stroke="rgba(255,255,255,.06)" strokeWidth="0.5" />
      ))}
      {/* Data polygon */}
      {scores.some(s => s > 0) && (
        <polygon points={polyStr} fill="rgba(124,109,250,.18)" stroke="#7c6dfa" strokeWidth="1.2" />
      )}
      {/* Score dots */}
      {polygonPoints.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r="2.5" fill={scores[i] > 0 ? '#7c6dfa' : 'rgba(100,100,122,.3)'} />
      ))}
      {/* Score labels */}
      {scores.map((s, i) => {
        const [x, y] = pt(1.18, i)
        return <text key={i} x={x} y={y} textAnchor="middle" dominantBaseline="middle"
                     fontSize="8" fill={s > 0 ? '#a78bfa' : '#64647a'}>{s > 0 ? s.toFixed(2) : '0.00'}</text>
      })}
    </svg>
  )
}
