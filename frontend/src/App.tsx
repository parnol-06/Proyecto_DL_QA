import { useState } from 'react'
import { useStore } from './store/useStore'
import { useShallow } from 'zustand/react/shallow'
import { Header } from './components/layout/Header'
import { Sidebar } from './components/layout/Sidebar'
import { RightPanel } from './components/layout/RightPanel'
import { Toast } from './components/ui/Toast'
import { TCCard } from './components/dashboard/TCCard'
import { EdgeCard } from './components/dashboard/EdgeCard'
import { BugCard } from './components/dashboard/BugCard'
import { CoveragePanel } from './components/dashboard/CoveragePanel'
import { MetricsDashboard } from './components/dashboard/MetricsDashboard'
import { EvalPipeline } from './components/sidebar/EvalPipeline'
import { StreamMonitor } from './components/forms/StreamMonitor'
import { FilterChips } from './components/forms/FilterChips'
import { fmtTime } from './lib/utils'
import type { TestCase, ActiveTab } from './types'

// ── Panel: Test Cases ────────────────────────────────────────────────────────
function PanelTC() {
  const {
    result, liveTCs, streaming, agentMode, streamPreviewText,
    filters, setActiveTab,
  } = useStore(useShallow(s => ({
    result: s.result,
    liveTCs: s.liveTCs,
    streaming: s.streaming,
    agentMode: s.agentMode,
    streamPreviewText: s.streamPreviewText,
    filters: s.filters,
    setActiveTab: s.setActiveTab,
  })))

  const [search, setSearch] = useState('')
  const [openCards, setOpenCards] = useState<Set<number>>(new Set())

  const rawTCs: TestCase[] = streaming ? liveTCs : (result?.test_cases || [])

  const displayTCs = rawTCs.filter(tc => {
    const matchCat  = !filters.category || tc.category === filters.category
    const matchPrio = !filters.priority  || tc.priority  === filters.priority
    const q = search.toLowerCase().trim()
    const matchSearch = !q || [tc.title, tc.category, tc.expected_result, ...(tc.steps || [])]
      .some(v => (v || '').toLowerCase().includes(q))
    return matchCat && matchPrio && matchSearch
  })

  function toggleCard(i: number) {
    setOpenCards(prev => {
      const next = new Set(prev)
      next.has(i) ? next.delete(i) : next.add(i)
      return next
    })
  }

  function handleReplace(index: number, tc: TestCase) {
    const s = useStore.getState()
    if (s.result?.test_cases) {
      const tcs = [...s.result.test_cases]
      tcs[index] = tc
      s.setResult({ ...s.result, test_cases: tcs })
    }
  }

  const hasTC = rawTCs.length > 0 || streaming

  return (
    <div className="p-3 flex flex-col gap-2.5 panel-fade">
      <StreamMonitor />

      {/* Stream preview (standard mode) */}
      {streaming && !agentMode && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg"
             style={{ background: 'rgba(124,109,250,.08)', border: '1px solid rgba(124,109,250,.2)' }}>
          <div className="w-1.5 h-1.5 rounded-full flex-shrink-0 live-pulse" style={{ background: '#7c6dfa' }} />
          <span className="text-[11px] font-mono" style={{ color: '#c4b5fd' }}>
            {streamPreviewText || 'Streaming in real time...'}
          </span>
        </div>
      )}

      {/* Search bar with icon */}
      {hasTC && (
        <div className="relative">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
               width="12" height="12" viewBox="0 0 16 16" fill="none">
            <circle cx="6.5" cy="6.5" r="5" stroke="#5a5a74" strokeWidth="1.5"/>
            <path d="M10.5 10.5L14 14" stroke="#5a5a74" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          <input
            type="search"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search test cases..."
            className="field-input text-[11px] py-2 pl-8"
            style={{ borderRadius: '10px' }}
          />
        </div>
      )}

      {/* Filter chips */}
      {hasTC && <FilterChips />}

      {/* Expand / collapse all */}
      {rawTCs.length > 1 && (
        <div className="flex gap-1.5">
          {[
            { label: '▾ Expand all',   fn: () => setOpenCards(new Set(rawTCs.map((_, i) => i))) },
            { label: '▸ Collapse all', fn: () => setOpenCards(new Set()) },
          ].map(({ label, fn }) => (
            <button key={label} onClick={fn}
                    className="text-[10px] font-mono px-2 py-0.5 rounded transition-colors"
                    style={{ background: 'rgba(255,255,255,.04)', color: '#8e8ea8', border: '1px solid rgba(255,255,255,.07)' }}>
              {label}
            </button>
          ))}
        </div>
      )}

      {/* Empty state */}
      {!hasTC && (
        <div className="flex flex-col items-center justify-center py-16 gap-3">
          <div className="w-12 h-12 rounded-xl flex items-center justify-center"
               style={{ background: 'rgba(124,109,250,.08)', border: '1px solid rgba(124,109,250,.12)' }}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
              <rect x="4" y="3" width="16" height="18" rx="3"
                    stroke="#7c6dfa" strokeWidth="1.4" fill="none" opacity=".6"/>
              <path d="M8 8 L16 8 M8 12 L16 12 M8 16 L12 16"
                    stroke="#7c6dfa" strokeWidth="1.4" strokeLinecap="round" opacity=".5"/>
              <path d="M14 15 L15.5 16.5 L18 14"
                    stroke="#34d399" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <p className="text-[12px] font-mono font-semibold" style={{ color: '#8e8ea8' }}>
            No test cases
          </p>
          <p className="text-[11px] font-mono text-center leading-relaxed" style={{ color: '#5a5a74' }}>
            Enter a user story<br/>and press <span style={{ color: '#a78bfa' }}>Generate</span>
          </p>
        </div>
      )}

      {/* TC Cards */}
      <div className="space-y-2">
        {displayTCs.map((tc, i) => {
          const realIdx = rawTCs.indexOf(tc)
          const idx = realIdx >= 0 ? realIdx : i
          return (
            <TCCard
              key={tc.id || idx}
              tc={tc}
              index={idx}
              onReplace={handleReplace}
              defaultOpen={openCards.has(idx)}
            />
          )
        })}
      </div>
    </div>
  )
}

// ── Panel: Edge Scenarios ────────────────────────────────────────────────────
function PanelEdge() {
  const edges = useStore(s => s.result?.edge_scenarios || [])
  if (!edges.length) return (
    <div className="flex flex-col items-center justify-center py-16 gap-3 panel-fade">
      <div className="w-12 h-12 rounded-xl flex items-center justify-center"
           style={{ background: 'rgba(34,211,238,.07)', border: '1px solid rgba(34,211,238,.15)' }}>
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
          <path d="M13 2 L4 14 L11 14 L11 22 L20 10 L13 10 Z"
                stroke="#22d3ee" strokeWidth="1.4" fill="none" strokeLinecap="round" strokeLinejoin="round" opacity=".8"/>
          <circle cx="4.5" cy="5.5" r=".9" fill="#22d3ee" opacity=".5"/>
          <circle cx="20" cy="18" r=".9" fill="#22d3ee" opacity=".5"/>
          <circle cx="19.5" cy="4.5" r=".65" fill="#22d3ee" opacity=".35"/>
        </svg>
      </div>
      <p className="text-[12px] font-mono font-semibold" style={{ color: '#8e8ea8' }}>
        No edge scenarios
      </p>
      <p className="text-[11px] font-mono text-center leading-relaxed" style={{ color: '#5a5a74' }}>
        Edge cases and scenarios<br/>will appear here after <span style={{ color: '#22d3ee' }}>Generate</span>
      </p>
    </div>
  )
  return (
    <div className="p-3 space-y-2 panel-fade">
      {edges.map((e, i) => <EdgeCard key={e.id || i} edge={e} index={i} />)}
    </div>
  )
}

// ── Panel: Potential Bugs ────────────────────────────────────────────────────
function PanelBugs() {
  const bugs = useStore(s => s.result?.potential_bugs || [])
  if (!bugs.length) return (
    <div className="flex flex-col items-center justify-center py-16 gap-3 panel-fade">
      <div className="w-12 h-12 rounded-xl flex items-center justify-center"
           style={{ background: 'rgba(248,113,113,.07)', border: '1px solid rgba(248,113,113,.15)' }}>
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
          <ellipse cx="12" cy="15" rx="5" ry="6" stroke="#f87171" strokeWidth="1.4" fill="none" opacity=".8"/>
          <circle cx="12" cy="6.5" r="2.8" stroke="#f87171" strokeWidth="1.4" fill="none" opacity=".8"/>
          <path d="M9 5 L6.5 3 M15 5 L17.5 3" stroke="#f87171" strokeWidth="1.2" strokeLinecap="round" opacity=".6"/>
          <path d="M7 12.5 L3.5 11.5 M7 16 L3.5 17
                   M17 12.5 L20.5 11.5 M17 16 L20.5 17"
                stroke="#f87171" strokeWidth="1.2" strokeLinecap="round" opacity=".5"/>
        </svg>
      </div>
      <p className="text-[12px] font-mono font-semibold" style={{ color: '#8e8ea8' }}>
        No potential bugs
      </p>
      <p className="text-[11px] font-mono text-center leading-relaxed" style={{ color: '#5a5a74' }}>
        Detected bug risks<br/>will appear here after <span style={{ color: '#f87171' }}>Generate</span>
      </p>
    </div>
  )
  return (
    <div className="p-3 space-y-2 panel-fade">
      {bugs.map((b, i) => <BugCard key={b.id || i} bug={b} index={i} />)}
    </div>
  )
}

// ── Panel: Agents trace ──────────────────────────────────────────────────────
function PanelAgents() {
  const result = useStore(s => s.result)
  const traces = result?.agent_trace || []
  const optimizer = result?.optimizer_output

  if (!traces.length) return (
    <div className="flex flex-col items-center justify-center py-16 gap-3 panel-fade">
      <div className="w-12 h-12 rounded-xl flex items-center justify-center"
           style={{ background: 'rgba(167,139,250,.07)', border: '1px solid rgba(167,139,250,.15)' }}>
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="5" r="2.5" stroke="#a78bfa" strokeWidth="1.3" fill="none" opacity=".9"/>
          <circle cx="5" cy="18" r="2.5" stroke="#a78bfa" strokeWidth="1.3" fill="none" opacity=".75"/>
          <circle cx="19" cy="18" r="2.5" stroke="#a78bfa" strokeWidth="1.3" fill="none" opacity=".75"/>
          <line x1="12" y1="7.5" x2="6.5" y2="15.5" stroke="#a78bfa" strokeWidth="1" opacity=".4" strokeLinecap="round"/>
          <line x1="12" y1="7.5" x2="17.5" y2="15.5" stroke="#a78bfa" strokeWidth="1" opacity=".4" strokeLinecap="round"/>
          <line x1="7.5" y1="18" x2="16.5" y2="18" stroke="#a78bfa" strokeWidth="1" opacity=".3" strokeLinecap="round"/>
          <circle cx="12" cy="12.5" r="1.2" fill="#a78bfa" opacity=".45"/>
        </svg>
      </div>
      <p className="text-[12px] font-mono font-semibold" style={{ color: '#8e8ea8' }}>
        Pipeline inactive
      </p>
      <p className="text-[11px] font-mono text-center leading-relaxed" style={{ color: '#5a5a74' }}>
        Enable <span style={{ color: '#a78bfa' }}>⚙ Agents</span> mode and generate<br/>to view the pipeline trace
      </p>
    </div>
  )

  return (
    <div className="p-3 space-y-2 panel-fade">
      {result?.used_fallback && (
        <div className="px-3 py-2 rounded-lg text-[11px] font-mono"
             style={{ background: 'rgba(251,191,36,.08)', border: '1px solid rgba(251,191,36,.2)', color: '#fbbf24' }}>
          ⚠ Fallback Mode — CrewAI unavailable, direct generation was used
        </div>
      )}
      {traces.map((t, i) => (
        <div key={i} className="rounded-lg p-3" style={{ background: '#0f0f18', border: '1px solid rgba(255,255,255,.07)' }}>
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs font-mono font-semibold text-qa-accent2">{t.agent}</span>
            <span className="text-[10px] font-mono text-qa-muted">{t.elapsed_s}s</span>
          </div>
          <p className="text-[11px] font-mono text-qa-muted2 leading-relaxed">{t.summary}</p>
        </div>
      ))}
      {optimizer?.priority_gaps?.length ? (
        <div className="rounded-lg p-3" style={{ background: '#0f0f18', border: '1px solid rgba(255,255,255,.07)' }}>
          <p className="section-label mb-2">Critical Gaps Identified</p>
          {optimizer.priority_gaps.map((g, i) => (
            <div key={i} className="flex items-start gap-2 mb-1.5">
              <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded-sm flex-shrink-0"
                    style={{ background: g.impact === 'alto' ? 'rgba(248,113,113,.15)' : 'rgba(251,191,36,.15)', color: g.impact === 'alto' ? '#f87171' : '#fbbf24' }}>
                {g.rank}
              </span>
              <div>
                <p className="text-[11px] font-mono text-qa-muted2">{g.reason}</p>
                <p className="text-[10px] font-mono text-qa-muted">Category: {g.category} · Impact: {g.impact}</p>
              </div>
            </div>
          ))}
        </div>
      ) : null}
      {optimizer?.optimization_summary && (
        <div className="px-3 py-2 rounded-lg text-[11px] font-mono text-qa-muted2"
             style={{ background: 'rgba(255,255,255,.03)', border: '1px solid rgba(255,255,255,.06)' }}>
          {optimizer.optimization_summary}
        </div>
      )}
    </div>
  )
}

// ── Panel: Metrics ───────────────────────────────────────────────────────────
function PanelMetrics() {
  const { result, evalPipelineState } = useStore(useShallow(s => ({
    result: s.result,
    evalPipelineState: s.evalPipelineState,
  })))

  return (
    <div className="p-3 space-y-2 panel-fade">
      {evalPipelineState !== 'done' && <EvalPipeline />}

      {evalPipelineState === 'idle' && !result && (
        <div className="flex flex-col items-center justify-center py-12 gap-3">
          <div className="w-12 h-12 rounded-xl flex items-center justify-center"
               style={{ background: 'rgba(52,211,153,.07)', border: '1px solid rgba(52,211,153,.15)' }}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="8" stroke="#34d399" strokeWidth="1.3" fill="none" opacity=".45"/>
              <circle cx="12" cy="12" r="4.5" stroke="#34d399" strokeWidth="1.2" fill="none" opacity=".7"/>
              <circle cx="12" cy="12" r="2" fill="#34d399" opacity=".9"/>
              <line x1="12" y1="3.8" x2="12" y2="7.3" stroke="#34d399" strokeWidth="1" strokeLinecap="round" opacity=".45"/>
              <line x1="12" y1="16.7" x2="12" y2="20.2" stroke="#34d399" strokeWidth="1" strokeLinecap="round" opacity=".45"/>
              <line x1="3.8" y1="12" x2="7.3" y2="12" stroke="#34d399" strokeWidth="1" strokeLinecap="round" opacity=".45"/>
              <line x1="16.7" y1="12" x2="20.2" y2="12" stroke="#34d399" strokeWidth="1" strokeLinecap="round" opacity=".45"/>
            </svg>
          </div>
          <p className="text-[12px] font-mono font-semibold" style={{ color: '#8e8ea8' }}>
            No metrics yet
          </p>
          <p className="text-[11px] font-mono text-center leading-relaxed" style={{ color: '#5a5a74' }}>
            Generate cases and press<br/><span style={{ color: '#34d399' }}>+ Evaluate with DeepEval</span>
          </p>
        </div>
      )}

      {evalPipelineState === 'done' && <MetricsDashboard />}

      {result?.coverage_summary && (
        <CoveragePanel cov={result.coverage_summary} />
      )}
    </div>
  )
}

// ── Tab configuration ────────────────────────────────────────────────────────
const TABS: Array<{ id: ActiveTab; label: string; hasCount?: boolean }> = [
  { id: 'tc',      label: 'Test Cases', hasCount: true },
  { id: 'edge',    label: 'Edge',       hasCount: true },
  { id: 'bugs',    label: 'Bugs',       hasCount: true },
  { id: 'agents',  label: '⚙ Agents' },
  { id: 'metrics', label: '◈ Metrics' },
]

// ── App ──────────────────────────────────────────────────────────────────────
export default function App() {
  const {
    activeTab, setActiveTab, result, liveTCs, streaming,
    workflowStep, generatorElapsed, evalTimerElapsed,
  } = useStore(useShallow(s => ({
    activeTab: s.activeTab,
    setActiveTab: s.setActiveTab,
    result: s.result,
    liveTCs: s.liveTCs,
    streaming: s.streaming,
    workflowStep: s.workflowStep,
    generatorElapsed: s.generatorElapsed,
    evalTimerElapsed: s.evalTimerElapsed,
  })))

  const tcCount   = streaming ? liveTCs.length : (result?.test_cases?.length ?? 0)
  const edgeCount = result?.edge_scenarios?.length ?? 0
  const bugCount  = result?.potential_bugs?.length ?? 0

  function getCount(id: ActiveTab): number | null {
    if (id === 'tc')   return tcCount
    if (id === 'edge') return edgeCount
    if (id === 'bugs') return bugCount
    return null
  }

  // Compact workflow step indicator for the tab bar
  const STEP_LABELS: Record<string, string> = {
    input: 'Input', generate: 'Generating', evaluate: 'Evaluating', export: 'Export',
  }
  const stepTimer = workflowStep === 'generate' && streaming && generatorElapsed > 0
    ? ` · ${fmtTime(generatorElapsed)}`
    : workflowStep === 'evaluate' && evalTimerElapsed > 0
    ? ` · ${fmtTime(evalTimerElapsed)}`
    : ''

  return (
    <div className="flex flex-col h-full bg-qa-bg text-qa-text overflow-hidden">

      {/* Three-column row: sidebar | main | right-panel */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        <Sidebar />

        {/* Center column: KPI bar at top, tabs + panels below */}
        <main className="flex-1 flex flex-col min-w-0 overflow-hidden"
              style={{ background: '#0a0a14' }}>

          {/* KPI bar — directly inside main, matches mockup layout */}
          <Header />

          {/* Tab bar + inline workflow step */}
          <div role="tablist" aria-label="Generator sections"
               className="flex items-center border-b shrink-0"
               style={{ borderColor: 'rgba(255,255,255,.06)', background: '#0d0d16' }}>
            {TABS.map(tab => {
              const count = tab.hasCount ? getCount(tab.id) : null
              const active = activeTab === tab.id
              return (
                <button
                  key={tab.id}
                  role="tab"
                  aria-selected={active}
                  aria-controls={`panel-${tab.id}`}
                  onClick={() => setActiveTab(tab.id)}
                  className="flex items-center gap-1.5 px-4 py-3 text-[11px] font-mono border-b-2 transition-all duration-150 shrink-0"
                  style={{
                    borderBottomColor: active ? '#7c6dfa' : 'transparent',
                    color: active ? '#c4b5fd' : '#5a5a74',
                    background: active ? 'rgba(124,109,250,.05)' : 'transparent',
                  }}
                >
                  {tab.label}
                  {count !== null && (
                    <span className="text-[9px] px-1.5 py-0.5 rounded-sm font-mono leading-none"
                          style={{
                            background: count > 0 ? 'rgba(124,109,250,.18)' : 'rgba(255,255,255,.04)',
                            color: count > 0 ? '#a78bfa' : '#4a4a5e',
                          }}>
                      {count}
                    </span>
                  )}
                </button>
              )
            })}

            {/* Workflow step indicator — right-aligned */}
            <div className="ml-auto flex items-center gap-1.5 px-4 shrink-0">
              <div className="w-1.5 h-1.5 rounded-full transition-all duration-300"
                   style={{
                     background: workflowStep === 'input'    ? 'rgba(100,100,122,.35)'
                               : workflowStep === 'generate' ? '#7c6dfa'
                               : workflowStep === 'evaluate' ? '#22d3ee'
                               : '#34d399',
                     boxShadow: workflowStep === 'generate' ? '0 0 6px rgba(124,109,250,.7)'
                               : workflowStep === 'evaluate' ? '0 0 6px rgba(34,211,238,.7)'
                               : 'none',
                     animation: (workflowStep === 'generate' || workflowStep === 'evaluate')
                               ? 'livePulse 1.5s ease-in-out infinite' : 'none',
                   }} />
              <span className="text-[10px] font-mono"
                    style={{ color: workflowStep === 'input' ? '#4a4a5e' : workflowStep === 'export' ? '#34d399' : '#a78bfa' }}>
                {STEP_LABELS[workflowStep] || workflowStep}{stepTimer}
              </span>
            </div>
          </div>

          {/* Panel content */}
          <div id={`panel-${activeTab}`} role="tabpanel"
               aria-label={TABS.find(t => t.id === activeTab)?.label}
               className="flex-1 overflow-y-auto">
            {activeTab === 'tc'      && <PanelTC />}
            {activeTab === 'edge'    && <PanelEdge />}
            {activeTab === 'bugs'    && <PanelBugs />}
            {activeTab === 'agents'  && <PanelAgents />}
            {activeTab === 'metrics' && <PanelMetrics />}
          </div>
        </main>

        <RightPanel />
      </div>

      {/* Footer */}
      <footer className="shrink-0 flex items-center justify-end px-4 py-1.5 border-t"
              style={{ background: '#09090e', borderColor: 'rgba(255,255,255,.04)' }}>
        <span className="text-[10px] font-mono text-qa-muted">© 2026 Arnol Ferney Pérez &amp; Jesus Andres Cabezas</span>
      </footer>

      <Toast />
    </div>
  )
}
