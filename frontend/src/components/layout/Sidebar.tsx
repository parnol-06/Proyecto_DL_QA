import { useMemo } from 'react'
import { Settings2 } from 'lucide-react'
import { useStore } from '../../store/useStore'
import { useShallow } from 'zustand/react/shallow'
import { TEMPLATES } from '../../lib/templates'
import { useGenerate } from '../../hooks/useGenerate'

const ALL_CATS = [
  { value: 'happy_path',    label: 'Happy Path'    },
  { value: 'edge_case',     label: 'Edge Case'     },
  { value: 'negative',      label: 'Negative'      },
  { value: 'security',      label: 'Security'      },
  { value: 'performance',   label: 'Performance'   },
  { value: 'usability',     label: 'Usability'     },
  { value: 'compatibility', label: 'Compatibility' },
]

const SEP = { borderTop: '1px solid rgba(255,255,255,.05)', paddingTop: '10px' }

export function Sidebar() {
  const s = useStore(useShallow(st => ({
    userStory:       st.userStory,
    context:         st.context,
    categories:      st.categories,
    tcCount:         st.tcCount,
    edgeCount:       st.edgeCount,
    bugCount:        st.bugCount,
    agentMode:       st.agentMode,
    useRag:          st.useRag,
    ragAvailable:    st.ragAvailable,
    setForm:         st.setForm,
    resetGeneration: st.resetGeneration,
    showToast:       st.showToast,
  })))
  const { generate, generateBatch, loading } = useGenerate()

  function loadTemplate(key: string) {
    const t = TEMPLATES[key]
    if (!t) return
    s.setForm({ userStory: t.story, context: t.context })
  }

  function toggleCategory(val: string) {
    const cats = s.categories.includes(val)
      ? s.categories.filter(c => c !== val)
      : [...s.categories, val]
    s.setForm({ categories: cats })
  }

  const distHint = useMemo(() => {
    if (!s.categories.length) return ''
    const count = Math.max(1, s.tcCount)
    const base  = Math.floor(count / s.categories.length)
    const rem   = count % s.categories.length
    return 'Dist: ' + s.categories.map((c, i) =>
      `${c.replace(/_/g, ' ')}: ${base + (i < rem ? 1 : 0)}`
    ).join(' · ')
  }, [s.categories, s.tcCount])

  function handleClear() {
    s.resetGeneration()
    s.showToast('Results cleared', '#8e8ea8')
  }

  return (
    <aside aria-label="Configuration panel"
           className="w-52 flex-shrink-0 flex flex-col overflow-hidden border-r"
           style={{ background: '#0f0f18', borderColor: 'rgba(255,255,255,.05)' }}>

      {/* Brand / logo ─ top of sidebar, mirrors the mockup */}
      <div className="flex items-center gap-2 px-3 py-2.5 border-b shrink-0"
           style={{ borderColor: 'rgba(255,255,255,.05)', background: '#121218' }}>
        <div className="w-7 h-7 rounded-xl flex items-center justify-center flex-shrink-0"
             style={{ background: 'linear-gradient(135deg, #1e3a8a, #2563eb)', boxShadow: '0 3px 14px rgba(37,99,235,.4)' }}>
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <polygon points="8,1.5 12.5,4.5 12.5,11.5 8,14.5 3.5,11.5 3.5,4.5"
                     stroke="rgba(255,255,255,.45)" strokeWidth=".9" fill="none"/>
            <polygon points="8,3.8 11.8,8 8,12.2 4.2,8"
                     stroke="rgba(255,255,255,.72)" strokeWidth=".9" fill="none"/>
            <line x1="8"    y1="1.5"  x2="8"    y2="3.8"  stroke="rgba(255,255,255,.30)" strokeWidth=".7"/>
            <line x1="12.5" y1="4.5"  x2="11.8" y2="8"    stroke="rgba(255,255,255,.22)" strokeWidth=".7"/>
            <line x1="12.5" y1="11.5" x2="11.8" y2="8"    stroke="rgba(255,255,255,.18)" strokeWidth=".7"/>
            <line x1="8"    y1="14.5" x2="8"    y2="12.2" stroke="rgba(255,255,255,.22)" strokeWidth=".7"/>
            <line x1="3.5"  y1="11.5" x2="4.2"  y2="8"   stroke="rgba(255,255,255,.18)" strokeWidth=".7"/>
            <line x1="3.5"  y1="4.5"  x2="4.2"  y2="8"   stroke="rgba(255,255,255,.22)" strokeWidth=".7"/>
            <circle cx="8" cy="8" r="1.5" fill="white" opacity=".95"/>
          </svg>
        </div>
        <span className="text-sm font-head font-bold text-qa-text leading-none tracking-tight">QA Generator</span>
      </div>

      <div className="flex flex-col gap-0 p-3 flex-1 overflow-y-auto min-h-0">

        {/* Additional Context */}
        <div className="pb-3">
          <p className="section-label">Additional Context</p>
          <textarea
            value={s.context}
            onChange={e => s.setForm({ context: e.target.value })}
            rows={3}
            placeholder="The email must be unique. The account locks after 3 failed attempts..."
            className="field-input resize-none text-[11px] leading-relaxed"
          />
        </div>

        {/* Generation Mode */}
        <div style={SEP} className="pb-3">
          <p className="section-label">Generation Mode</p>
          <div className="flex gap-1.5">
            {[
              { id: false, label: 'Standard', icon: null },
              { id: true,  label: 'Agents',   icon: <Settings2 size={10} /> },
            ].map(({ id, label, icon }) => (
              <button
                key={String(id)}
                onClick={() => s.setForm({ agentMode: id })}
                aria-pressed={s.agentMode === id}
                className="flex-1 py-1.5 rounded-full text-[11px] font-mono font-medium transition-all duration-150 flex items-center justify-center gap-1"
                style={
                  s.agentMode === id
                    ? { background: 'rgba(124,109,250,.2)', color: '#c4b5fd', border: '1px solid rgba(124,109,250,.35)' }
                    : { background: 'rgba(255,255,255,.04)', color: '#64647a', border: '1px solid rgba(255,255,255,.07)' }
                }
              >
                {icon && <span aria-hidden="true">{icon}</span>}
                {label}
              </button>
            ))}
          </div>
          {s.agentMode && (
            <p className="text-[9px] font-mono text-qa-muted mt-1.5 leading-relaxed">
              CrewAI pipeline · Generator → Reviewer → Optimizer (~2–4 min) with quality analysis.
            </p>
          )}
        </div>

        {/* Knowledge Base (RAG) */}
        <div style={SEP} className="pb-3">
          <p className="section-label">Knowledge Base</p>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={s.useRag && s.ragAvailable}
              onChange={e => s.setForm({ useRag: e.target.checked })}
              disabled={!s.ragAvailable}
              className="accent-qa-accent w-3.5 h-3.5"
            />
            <span className="text-[11px] font-mono leading-relaxed"
                  style={{ color: s.ragAvailable ? '#34d399' : '#4a4a5e' }}>
              {s.ragAvailable ? 'QA base available' : 'Index not built'}
            </span>
          </label>
          {s.useRag && s.ragAvailable && (
            <p className="text-[9px] font-mono text-qa-muted mt-1 leading-relaxed">
              CrewAI pipeline · Generator (1–2 min with quality analysis).
            </p>
          )}
        </div>

        {/* Generation Categories */}
        <div style={SEP} className="pb-3">
          <p className="section-label">Generation Categories</p>
          <div className="grid grid-cols-2 gap-0.5">
            {ALL_CATS.map(c => (
              <label key={c.value} className="flex items-center gap-1.5 cursor-pointer py-0.5">
                <input
                  type="checkbox"
                  checked={s.categories.includes(c.value)}
                  onChange={() => toggleCategory(c.value)}
                  className="accent-qa-accent w-3 h-3"
                />
                <span className="text-[10px] font-mono text-qa-muted2">{c.label}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Quantity */}
        <div style={SEP} className="pb-3">
          <p className="section-label">Quantity</p>
          <div className="flex gap-2">
            {[
              { key: 'tcCount',   label: 'TC',   val: s.tcCount,   min: 1, max: 50 },
              { key: 'edgeCount', label: 'Edge', val: s.edgeCount, min: 0, max: 20 },
              { key: 'bugCount',  label: 'Bugs', val: s.bugCount,  min: 0, max: 20 },
            ].map(({ key, label, val, min, max }) => (
              <label key={key} className="flex-1 flex flex-col gap-0.5">
                <span className="text-[9px] font-mono text-qa-muted">{label}</span>
                <input
                  type="number"
                  value={val}
                  min={min}
                  max={max}
                  onChange={e => s.setForm({ [key]: Math.max(min, parseInt(e.target.value) || min) } as never)}
                  className="field-input text-center text-xs py-1 px-1"
                />
              </label>
            ))}
          </div>
          {distHint && (
            <p className="text-[9px] font-mono text-qa-muted mt-1 leading-relaxed">{distHint}</p>
          )}
        </div>

        {/* User story */}
        <div style={SEP} className="pb-2">
          <div className="flex items-center justify-between mb-1">
            <p className="section-label mb-0">User Story</p>
            <select
              onChange={e => { loadTemplate(e.target.value); e.target.value = '' }}
              defaultValue=""
              className="text-[9px] font-mono rounded-full px-1.5 py-0.5 transition-colors"
              style={{
                background: 'rgba(255,255,255,.04)',
                color: '#64647a',
                border: '1px solid rgba(255,255,255,.07)',
                appearance: 'none',
                cursor: 'pointer',
              }}
            >
              <option value="">+ Template</option>
              {Object.entries(TEMPLATES).map(([k, t]) => (
                <option key={k} value={k}>{t.label}</option>
              ))}
            </select>
          </div>
          <textarea
            value={s.userStory}
            onChange={e => s.setForm({ userStory: e.target.value })}
            rows={4}
            placeholder="As a registered user I want to log in with my email and password to access my personal dashboard."
            className="field-input resize-none text-[11px] leading-relaxed"
          />
        </div>

      </div>

      {/* CTA buttons — sticky bottom */}
      <div className="p-3 border-t space-y-1.5 flex-shrink-0"
           style={{ borderColor: 'rgba(255,255,255,.05)', background: '#0f0f18' }}>
        <button
          onClick={generate}
          disabled={loading}
          aria-label={loading ? 'Generating test cases…' : 'Generate test cases'}
          className="btn-generate"
        >
          {loading ? (
            <>
              <span className="spinner active" />
              <span>Generating...</span>
            </>
          ) : (
            <>
              <svg width="13" height="13" viewBox="0 0 14 14" fill="none" aria-hidden="true">
                <path d="M9.5 1.5 L5.5 7 L8.5 7 L4.5 12.5"
                      stroke="currentColor" strokeWidth="1.6"
                      strokeLinecap="round" strokeLinejoin="round"/>
                <circle cx="12.5" cy="3.5" r=".9" fill="currentColor" opacity=".65"/>
                <circle cx="13" cy="7.5" r=".65" fill="currentColor" opacity=".4"/>
                <circle cx="1.5" cy="5" r=".65" fill="currentColor" opacity=".4"/>
                <circle cx="1" cy="9.5" r=".9" fill="currentColor" opacity=".55"/>
              </svg>
              <span>Generate test cases</span>
            </>
          )}
        </button>

        <button
          onClick={generateBatch}
          disabled={loading}
          title="Paste multiple stories separated with ---"
          className="w-full py-1.5 rounded-full text-[10px] font-mono transition-all"
          style={{ background: 'rgba(255,255,255,.03)', color: '#5a5a74', border: '1px solid rgba(255,255,255,.06)' }}
        >
          ⊞ Batch mode
        </button>

        <button
          onClick={handleClear}
          aria-label="Clear all results"
          className="w-full py-1 rounded text-[10px] font-mono transition-all flex items-center justify-center gap-1.5"
          style={{ background: 'transparent', color: '#4a4a5e', border: 'none' }}
        >
          <span>×</span>
          <span>Clear results</span>
        </button>
      </div>
    </aside>
  )
}
