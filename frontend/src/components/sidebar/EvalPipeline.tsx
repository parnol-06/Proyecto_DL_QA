import { useStore } from '../../store/useStore'
import { useShallow } from 'zustand/react/shallow'
import { fmtTime } from '../../lib/utils'
import type { MetricResult } from '../../types'

const EVAL_STEPS = [
  { key: 'coverage',              name: 'Test Coverage',          color: '#34d399', threshold: 0.60 },
  { key: 'relevancy',             name: 'Test Relevancy',         color: '#22d3ee', threshold: 0.70 },
  { key: 'consistency',           name: 'Test Consistency',       color: '#5B8DEF', threshold: 0.65 },
  { key: 'specificity',           name: 'Step Specificity',       color: '#fbbf24', threshold: 0.60 },
  { key: 'nonfunctional_balance', name: 'Non-Functional Balance', color: '#e879a0', threshold: 0.55 },
]

interface StepNodeProps {
  step: typeof EVAL_STEPS[0]
  result?: MetricResult
  isActive: boolean
  isLast: boolean
}

function StepNode({ step, result, isActive, isLast }: StepNodeProps) {
  const st = result ? (result.passed ? 'pass' : 'warn') : isActive ? 'running' : 'idle'
  const pct = result ? Math.round(result.score * 100) : 0
  const thrPct = Math.round(step.threshold * 100)

  const dotSymbol = { idle: '', running: '·', pass: '✓', warn: '!' }[st]
  const dotColor = { idle: 'rgba(100,100,122,.35)', running: '#5B8DEF', pass: '#34d399', warn: '#fbbf24' }[st]
  const badgeColor = { idle: '#64647a', running: '#5B8DEF', pass: '#34d399', warn: '#fbbf24' }[st]
  const badgeLabel = { idle: 'PENDING', running: 'EVALUATING', pass: `PASS · ${result?.score.toFixed(2)}`, warn: `WARN · ${result?.score.toFixed(2)}` }[st]

  return (
    <>
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-bold flex-shrink-0"
               style={{
                 background: dotColor + '20',
                 border: `1px solid ${dotColor}`,
                 color: dotColor,
                 animation: st === 'running' ? 'livePulse 1.5s ease-in-out infinite' : 'none',
               }}>
            {dotSymbol}
          </div>
          <span className="text-[11px] font-mono flex-1" style={{ color: st === 'idle' ? '#64647a' : 'var(--brand)' }}>{step.name}</span>
          {result && (
            <span className="text-[9px] font-mono text-qa-muted">{result.elapsed_ms}ms</span>
          )}
          <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded-sm"
                style={{ color: badgeColor, background: badgeColor + '18', border: `1px solid ${badgeColor}30` }}>
            {badgeLabel}
          </span>
        </div>
        <div className="flex items-center gap-1.5 pl-6">
          <div className="relative flex-1 h-1.5 rounded-full" style={{ background: 'rgba(255,255,255,.07)' }}>
            <div className="h-full rounded-full transition-all duration-700"
                 style={{ width: `${pct}%`, background: step.color }} />
            <div className="absolute top-0 bottom-0 w-px"
                 style={{ left: `${thrPct}%`, background: 'rgba(255,255,255,.35)' }} />
          </div>
          <span className="text-[10px] font-mono w-6 text-right"
                style={{ color: result ? step.color : '#64647a' }}>
            {result ? pct + '%' : '—'}
          </span>
        </div>
        {result?.reason && result.reason !== 'N/A' && !result.reason.startsWith('Error:') && (
          <p className="pl-6 text-[10px] font-mono text-qa-muted leading-relaxed">
            {result.reason.slice(0, 120)}{result.reason.length > 120 ? '…' : ''}
          </p>
        )}
      </div>
      {!isLast && (
        <div className="w-px h-2.5 ml-2" style={{ background: 'rgba(100,100,122,.2)' }} />
      )}
    </>
  )
}

export function EvalPipeline() {
  const { evalPipelineState, evalMetrics, evalTimerElapsed } = useStore(useShallow(s => ({
    evalPipelineState: s.evalPipelineState,
    evalMetrics: s.evalMetrics,
    evalTimerElapsed: s.evalTimerElapsed,
  })))

  if (evalPipelineState === 'done') return null

  const doneCount = Object.keys(evalMetrics).length
  const total = EVAL_STEPS.length

  return (
    <div className="rounded-lg p-3 mb-3" style={{ background: '#0f0f18', border: '1px solid rgba(255,255,255,.07)' }}>
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] text-qa-accent">◈</span>
          <span className="text-[11px] font-mono font-semibold text-qa-muted2">Pipeline DeepEval</span>
          <span className="text-[9px] font-mono text-qa-muted">5 metrics · Local Ollama</span>
        </div>
        {evalPipelineState === 'running' && (
          <span className="text-[10px] font-mono text-qa-accent">{fmtTime(evalTimerElapsed)}</span>
        )}
      </div>

      {evalPipelineState === 'idle' && (
        <p className="text-[10px] font-mono text-qa-muted mb-2">
          Press <strong className="text-qa-accent">Evaluate with DeepEval</strong> to analyse the quality of the generated cases.
        </p>
      )}
      {evalPipelineState === 'running' && (
        <p className="text-[10px] font-mono text-qa-muted mb-2">
          Evaluating… <strong className="text-qa-accent">{doneCount} of {total}</strong> metrics completed
        </p>
      )}

      {/* Steps */}
      <div className="flex flex-col">
        {EVAL_STEPS.map((step, i) => (
          <StepNode
            key={step.key}
            step={step}
            result={evalMetrics[step.key]}
            isActive={evalPipelineState === 'running' && i === doneCount}
            isLast={i === EVAL_STEPS.length - 1}
          />
        ))}
      </div>
    </div>
  )
}
