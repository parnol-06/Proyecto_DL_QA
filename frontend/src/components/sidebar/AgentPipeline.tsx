import { useStore } from '../../store/useStore'
import { useShallow } from 'zustand/react/shallow'
import { AnimatePresence, motion } from 'framer-motion'
import { useState } from 'react'
import { Settings2, ClipboardCheck, Sparkles, type LucideIcon } from 'lucide-react'
import type { AgentKey } from '../../store/useStore'

const NODES: Array<{ key: AgentKey; name: string; desc: string }> = [
  { key: 'generator', name: 'Generator', desc: 'Generates cases from the user story' },
  { key: 'reviewer',  name: 'Reviewer',  desc: 'Analyses quality and consistency'   },
  { key: 'optimizer', name: 'Optimizer', desc: 'Optimises coverage and gaps'        },
]

const NODE_ICONS: Record<string, { bg: string; border: string; color: string; Icon: LucideIcon }> = {
  generator: { bg: 'rgba(251,146,60,.13)',  border: 'rgba(251,146,60,.28)',  color: '#fb923c', Icon: Settings2      },
  reviewer:  { bg: 'rgba(34,211,238,.10)',  border: 'rgba(34,211,238,.22)',  color: '#22d3ee', Icon: ClipboardCheck },
  optimizer: { bg: 'rgba(91,141,239,.13)',  border: 'rgba(91,141,239,.28)',  color: '#5B8DEF', Icon: Sparkles       },
}

const STATE_COLORS = {
  idle:    { dot: 'rgba(100,100,122,.4)', border: 'rgba(255,255,255,.06)', text: '#64647a'  },
  running: { dot: '#5B8DEF',              border: 'rgba(91,141,239,.35)',  text: '#5B8DEF'  },
  done:    { dot: '#34d399',              border: 'rgba(52,211,153,.25)',  text: '#34d399'  },
  error:   { dot: '#f87171',              border: 'rgba(248,113,113,.25)', text: '#f87171'  },
}

const VERDICT_COLORS: Record<string, string> = {
  APPROVED: '#34d399', REJECTED: '#f87171', MODIFIED: '#fbbf24',
}

function AgentNode({ nodeKey }: { nodeKey: AgentKey }) {
  const node = useStore(s => s.agentNodes[nodeKey])
  const [showDecisions, setShowDecisions] = useState(false)
  const cfg = NODES.find(n => n.key === nodeKey)!
  const colors = STATE_COLORS[node.state]
  const iconCfg = NODE_ICONS[nodeKey]
  const NodeIcon = iconCfg.Icon

  return (
    <div className="rounded-lg p-2.5 transition-all duration-300"
         style={{ background: '#151520', border: `1px solid ${colors.border}` }}>

      {/* Top row */}
      <div className="flex items-center gap-2 mb-1">
        <div className="w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0"
             style={{ background: iconCfg.bg, border: `1px solid ${iconCfg.border}` }}>
          <NodeIcon size={12} color={iconCfg.color} strokeWidth={1.8} />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-[11px] font-mono font-semibold" style={{ color: colors.text }}>
              {cfg.name}
            </span>
            {node.elapsed && (
              <span className="text-[10px] font-mono font-bold" style={{ color: colors.dot }}>
                {node.elapsed}
              </span>
            )}
          </div>
        </div>

        <div className="w-2 h-2 rounded-full flex-shrink-0"
             style={{
               background: colors.dot,
               boxShadow: node.state === 'running' ? `0 0 6px ${colors.dot}` : 'none',
               animation: node.state === 'running' ? 'livePulse 1.5s ease-in-out infinite' : 'none',
             }} />
      </div>

      {/* Message */}
      <p className="text-[10px] font-mono leading-relaxed mb-1"
         style={{ color: node.state === 'idle' ? '#4a4a60' : '#8e8ea8' }}>
        {node.message}
      </p>

      {/* Progress bar */}
      {(node.state === 'running' || node.state === 'done') && (
        <div className="mb-1">
          <div className="h-1 rounded-full" style={{ background: 'rgba(255,255,255,.06)' }}>
            <div className="h-full rounded-full transition-all duration-500"
                 style={{
                   width: `${node.progress}%`,
                   background: node.state === 'done' ? '#34d399' : '#5B8DEF',
                 }} />
          </div>
          {node.stats && (
            <span className="text-[9px] font-mono text-qa-muted mt-0.5 block">{node.stats}</span>
          )}
        </div>
      )}

      {/* Decisions toggle */}
      {node.decisions.length > 0 && (
        <>
          <button
            onClick={() => setShowDecisions(o => !o)}
            className="flex items-center gap-1 text-[10px] font-mono text-qa-muted hover:text-qa-muted2 transition-colors mt-1"
          >
            <span>{showDecisions ? '▴' : '▾'}</span>
            <span>{showDecisions ? 'Hide' : 'Show decisions'}</span>
          </button>
          <AnimatePresence>
            {showDecisions && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: .18 }}
                style={{ overflow: 'hidden' }}
              >
                <div className="mt-1.5 space-y-1">
                  {node.decisions.slice(0, 6).map((d, i) => (
                    <div key={i} className="flex items-start gap-1.5 text-[10px] font-mono">
                      <span className="text-qa-muted flex-shrink-0">{d.tc_id || d.id}</span>
                      <span className="font-semibold flex-shrink-0"
                            style={{ color: VERDICT_COLORS[d.verdict] || '#8e8ea8' }}>
                        {d.verdict}
                      </span>
                      {d.reason && (
                        <span className="text-qa-muted">{d.reason.slice(0, 55)}</span>
                      )}
                    </div>
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </>
      )}
    </div>
  )
}

export function AgentPipeline() {
  const { agentPipelineVisible, agentMode, connectorsActive } = useStore(useShallow(s => ({
    agentPipelineVisible: s.agentPipelineVisible,
    agentMode: s.agentMode,
    connectorsActive: s.connectorsActive,
  })))

  if (!agentPipelineVisible && !agentMode) return null

  return (
    <AnimatePresence>
      <motion.div
        key="pipeline"
        initial={{ opacity: 0, height: 0 }}
        animate={{ opacity: 1, height: 'auto' }}
        exit={{ opacity: 0, height: 0 }}
        transition={{ duration: .22 }}
      >
        <div className="border-t pt-3" style={{ borderColor: 'rgba(255,255,255,.05)' }}>
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-1.5">
              <span className="text-[10px]" style={{ color: 'var(--brand)' }}>⚙</span>
              <p className="section-label mb-0">Pipeline CrewAI</p>
            </div>
            {!agentPipelineVisible && (
              <span className="text-[9px] font-mono px-1.5 py-0.5 rounded-full"
                    style={{ background: 'rgba(91,141,239,.1)', color: 'var(--fg-3)', border: '1px solid rgba(91,141,239,.2)' }}>
                3 agents
              </span>
            )}
          </div>

          <div className="space-y-0">
            <AgentNode nodeKey="generator" />
            <div className="flex justify-center my-1">
              <div className="w-px h-3 transition-colors duration-500"
                   style={{ background: connectorsActive[0] ? 'rgba(52,211,153,.5)' : 'rgba(100,100,122,.15)' }} />
            </div>
            <AgentNode nodeKey="reviewer" />
            <div className="flex justify-center my-1">
              <div className="w-px h-3 transition-colors duration-500"
                   style={{ background: connectorsActive[1] ? 'rgba(52,211,153,.5)' : 'rgba(100,100,122,.15)' }} />
            </div>
            <AgentNode nodeKey="optimizer" />
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  )
}
