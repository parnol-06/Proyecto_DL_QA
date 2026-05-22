import { useStore } from '../../store/useStore'
import { useShallow } from 'zustand/react/shallow'
import { useEvaluate } from '../../hooks/useEvaluate'
import { useModels } from '../../hooks/useModels'
import { AgentPipeline } from '../sidebar/AgentPipeline'
import { MetricsRadar } from '../dashboard/MetricsDashboard'
import { postPullModel } from '../../services/api'
import { copyJSON, downloadJSON, downloadCSV, downloadMarkdown, downloadXLSX } from '../../lib/export'
import { scoreColor } from '../../lib/utils'

const METRIC_BARS = [
  { key: 'coverage',              shortKey: 'cov', name: 'Coverage',   color: '#34d399' },
  { key: 'relevancy',             shortKey: 'rel', name: 'Relevancy',  color: '#22d3ee' },
  { key: 'consistency',           shortKey: 'con', name: 'Consistency',color: '#a78bfa' },
  { key: 'specificity',           shortKey: 'spe', name: 'Specificity',color: '#fbbf24' },
  { key: 'nonfunctional_balance', shortKey: 'nfb', name: 'NFR Balance',color: '#e879a0' },
]

const SEP = { borderTop: '1px solid rgba(255,255,255,.05)', paddingTop: '12px', marginTop: '0' }

export function RightPanel() {
  const { evaluate, loading: evalLoading } = useEvaluate()
  const { models, loadModelStatus } = useModels()

  const s = useStore(useShallow(st => ({
    model:              st.model,
    evalModel:          st.evalModel,
    temperature:        st.temperature,
    ollamaOk:           st.ollamaOk,
    modelLoaded:        st.modelLoaded,
    result:             st.result,
    evalMetrics:        st.evalMetrics,
    metricBarStates:    st.metricBarStates,
    evalPipelineState:  st.evalPipelineState,
    workflowStep:       st.workflowStep,
    agentMode:          st.agentMode,
    setForm:            st.setForm,
    showToast:          st.showToast,
    setActiveTab:       st.setActiveTab,
  })))

  const hasResult = !!s.result
  const metricsHaveData = Object.keys(s.evalMetrics).length > 0

  async function handlePullModel() {
    s.showToast(`Downloading ${s.model}… (may take several minutes)`, '#22d3ee')
    try {
      await postPullModel(s.model)
      s.showToast(`${s.model} downloaded successfully`)
      loadModelStatus(s.model)
    } catch (e: unknown) {
      s.showToast('Download error: ' + (e instanceof Error ? e.message : ''), '#f87171')
    }
  }

  return (
    <aside aria-label="Ollama and evaluation panel"
           className="w-60 flex-shrink-0 flex flex-col border-l overflow-hidden"
           style={{ background: '#0f0f18', borderColor: 'rgba(255,255,255,.05)' }}>

      {/* ── Ollama header ── */}
      <div className="flex items-center justify-between px-3 py-2.5 border-b shrink-0"
           style={{ borderColor: 'rgba(255,255,255,.05)', background: '#121218' }}>
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
               style={{
                 background: 'linear-gradient(135deg, rgba(124,109,250,.25), rgba(79,63,245,.2))',
                 border: '1px solid rgba(124,109,250,.3)',
                 boxShadow: '0 2px 8px rgba(124,109,250,.2)',
               }}>
            <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
              <circle cx="8" cy="8" r="5.5" stroke="#a78bfa" strokeWidth="1"   fill="none" opacity=".55"/>
              <circle cx="8" cy="8" r="2.5" stroke="#a78bfa" strokeWidth=".9"  fill="none" opacity=".8"/>
              <circle cx="8" cy="8" r="1.1" fill="#a78bfa" opacity=".95"/>
              <line x1="8" y1="2.2" x2="8" y2="5.3" stroke="#a78bfa" strokeWidth=".8" strokeLinecap="round" opacity=".5"/>
              <line x1="8" y1="10.7" x2="8" y2="13.8" stroke="#a78bfa" strokeWidth=".8" strokeLinecap="round" opacity=".5"/>
              <line x1="2.2" y1="8" x2="5.3" y2="8" stroke="#a78bfa" strokeWidth=".8" strokeLinecap="round" opacity=".5"/>
              <line x1="10.7" y1="8" x2="13.8" y2="8" stroke="#a78bfa" strokeWidth=".8" strokeLinecap="round" opacity=".5"/>
            </svg>
          </div>
          <span className="text-xs font-mono font-semibold" style={{ color: '#c4b5fd' }}>Ollama</span>
        </div>

        <div className="flex items-center gap-1.5">
          <div className="w-1.5 h-1.5 rounded-full transition-colors flex-shrink-0"
               style={{
                 background: s.ollamaOk ? '#34d399' : '#fbbf24',
                 boxShadow: s.ollamaOk ? '0 0 6px rgba(52,211,153,.6)' : '0 0 4px rgba(251,191,36,.5)',
               }} />
          <span className="text-[9px] font-mono px-2 py-0.5 rounded-full"
                style={{
                  background: 'rgba(52,211,153,.1)',
                  color: '#34d399',
                  border: '1px solid rgba(52,211,153,.25)',
                }}>
            Local &amp; Private
          </span>
        </div>
      </div>

      {/* ── Scrollable body ── */}
      <div className="flex flex-col gap-0 p-3 flex-1 min-h-0 overflow-y-auto">

        {/* Model selector */}
        <div className="pb-3">
          <p className="section-label">Ollama</p>
          <select
            value={s.model}
            onChange={e => { s.setForm({ model: e.target.value }); loadModelStatus(e.target.value) }}
            className="field-input text-[11px] py-1.5"
            style={{ appearance: 'none' }}
          >
            {models.length > 0
              ? models.map(m => <option key={m} value={m}>{m}</option>)
              : <option value={s.model}>{s.model}</option>}
          </select>

          <div className="flex items-center gap-1.5 mt-1.5">
            <div className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                 style={{ background: s.modelLoaded ? '#34d399' : '#fbbf24' }} />
            <span className="text-[10px] font-mono text-qa-muted flex-1">
              {s.modelLoaded ? 'available' : 'not downloaded'}
            </span>
            {!s.modelLoaded && (
              <button onClick={handlePullModel}
                      className="text-[9px] font-mono px-1.5 py-0.5 rounded-full"
                      style={{ background: 'rgba(124,109,250,.15)', color: '#a78bfa', border: '1px solid rgba(124,109,250,.3)' }}>
                ⬇ Download
              </button>
            )}
          </div>

          <div className="mt-2.5">
            <div className="flex items-center justify-between mb-1">
              <span className="section-label mb-0">Temperature</span>
              <span className="text-[10px] font-mono" style={{ color: '#a78bfa' }}>{s.temperature.toFixed(2)}</span>
            </div>
            <input
              type="range" min="0" max="1" step="0.05"
              value={s.temperature}
              onChange={e => s.setForm({ temperature: parseFloat(e.target.value) })}
              className="w-full h-1.5 rounded-full appearance-none cursor-pointer"
              style={{ accentColor: '#7c6dfa' }}
            />
          </div>
        </div>

        {/* DeepEval section */}
        <div style={SEP} className="pb-3">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-1.5">
              <span className="text-[10px]" style={{ color: '#7c6dfa' }}>◈</span>
              <p className="section-label mb-0">DeepEval</p>
            </div>
            {metricsHaveData && (
              <button
                onClick={() => s.setActiveTab('metrics')}
                className="text-[9px] font-mono px-1.5 py-0.5 rounded-full transition-colors"
                style={{ background: 'rgba(124,109,250,.1)', color: '#8e8ea8', border: '1px solid rgba(124,109,250,.2)' }}
              >
                view all →
              </button>
            )}
          </div>

          {/* Radar chart */}
          <div className="flex justify-center py-1 rounded-lg"
               style={{ background: 'rgba(255,255,255,.02)', border: '1px solid rgba(255,255,255,.05)' }}>
            <MetricsRadar />
          </div>

          {/* Mini metric bars */}
          {metricsHaveData && (
            <div className="space-y-1.5 mt-2 mb-2">
              {METRIC_BARS.map(({ key, shortKey, name, color }) => {
                const result = s.evalMetrics[key]
                const state  = s.metricBarStates[shortKey]
                const pct    = result ? Math.round(result.score * 100) : 0
                const dotColors = { idle: '#64647a', running: '#7c6dfa', pass: '#34d399', warn: '#fbbf24' }
                return (
                  <div key={key} className="flex items-center gap-1.5">
                    <div className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                         style={{
                           background: dotColors[state] || '#64647a',
                           animation: state === 'running' ? 'livePulse 1.2s ease-in-out infinite' : 'none',
                         }} />
                    <span className="text-[10px] font-mono text-qa-muted w-14 flex-shrink-0">{name}</span>
                    <div className="flex-1 h-1 rounded-full" style={{ background: 'rgba(255,255,255,.07)' }}>
                      <div className="h-full rounded-full transition-all duration-700"
                           style={{ width: `${pct}%`, background: color }} />
                    </div>
                    <span className="text-[10px] font-mono w-7 text-right flex-shrink-0"
                          style={{ color: result ? scoreColor(result.score) : '#64647a' }}>
                      {result ? result.score.toFixed(2) : '—'}
                    </span>
                  </div>
                )
              })}
            </div>
          )}

          {/* Eval model */}
          <div className="mb-2">
            <p className="section-label">Evaluation model</p>
            <select
              value={s.evalModel}
              onChange={e => s.setForm({ evalModel: e.target.value })}
              className="field-input text-[11px] py-1.5"
              style={{ appearance: 'none' }}
            >
              <option value="">— same model —</option>
              {models.map(m => <option key={m} value={m}>{m}</option>)}
            </select>
            <p className="text-[9px] font-mono text-qa-muted mt-1 leading-relaxed">
              Use a different model to avoid bias.
            </p>
          </div>

          {/* Evaluate button */}
          <button
            onClick={evaluate}
            disabled={!hasResult || evalLoading || s.evalPipelineState === 'running'}
            aria-label={evalLoading || s.evalPipelineState === 'running' ? 'Evaluating with DeepEval…' : 'Evaluate with DeepEval'}
            className="btn-evaluate"
          >
            {evalLoading || s.evalPipelineState === 'running' ? (
              <>
                <span className="spinner active" style={{ display: 'block' }} />
                <span>Evaluating...</span>
              </>
            ) : (
              <>
                <svg width="13" height="13" viewBox="0 0 14 14" fill="none" aria-hidden="true">
                  <circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth=".9" fill="none" opacity=".4"/>
                  <circle cx="7" cy="7" r="3"   stroke="currentColor" strokeWidth=".9" fill="none" opacity=".65"/>
                  <circle cx="7" cy="7" r="1.5" fill="currentColor" opacity=".95"/>
                  <line x1="7" y1="1.2" x2="7" y2="3.8"   stroke="currentColor" strokeWidth=".8" strokeLinecap="round" opacity=".5"/>
                  <line x1="7" y1="10.2" x2="7" y2="12.8" stroke="currentColor" strokeWidth=".8" strokeLinecap="round" opacity=".5"/>
                  <line x1="1.2" y1="7" x2="3.8" y2="7"   stroke="currentColor" strokeWidth=".8" strokeLinecap="round" opacity=".5"/>
                  <line x1="10.2" y1="7" x2="12.8" y2="7" stroke="currentColor" strokeWidth=".8" strokeLinecap="round" opacity=".5"/>
                </svg>
                + Evaluar con DeepEval
              </>
            )}
          </button>
        </div>

        {/* Agent Pipeline */}
        <AgentPipeline />

        {/* Export section */}
        {hasResult && (
          <div style={SEP} className="pb-2">
            <p className="section-label">Export results</p>
            <div className="flex flex-col gap-1">
              <button
                onClick={() => copyJSON(s.result!).then(() => s.showToast('JSON copied')).catch(() => s.showToast('Copy failed', '#f87171'))}
                className="text-[10px] font-mono py-1.5 rounded-full transition-colors text-left px-2"
                style={{ background: 'rgba(255,255,255,.04)', color: '#8e8ea8', border: '1px solid rgba(255,255,255,.07)' }}
              >
                📋 Copiar JSON
              </button>
              <div className="grid grid-cols-2 gap-1">
                {[
                  { label: '⬇ JSON',     fn: () => downloadJSON(s.result!) },
                  { label: '⬇ CSV',      fn: () => downloadCSV(s.result!) },
                  { label: '⬇ Markdown', fn: () => downloadMarkdown(s.result!) },
                  { label: '⬇ XLSX',     fn: () => downloadXLSX(s.result!, s.showToast) },
                ].map(({ label, fn }) => (
                  <button key={label} onClick={fn}
                          className="text-[10px] font-mono py-1.5 rounded-full transition-colors"
                          style={{ background: 'rgba(255,255,255,.04)', color: '#8e8ea8', border: '1px solid rgba(255,255,255,.07)' }}>
                    {label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </aside>
  )
}
