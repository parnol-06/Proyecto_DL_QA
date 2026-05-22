import { motion } from 'framer-motion'
import type { EdgeScenario } from '../../types'

interface Props { edge: EdgeScenario; index: number }

const riskColor: Record<string, string> = {
  high: '#f87171', alto: '#f87171',
  medium: '#fbbf24', medio: '#fbbf24',
  low: '#34d399', bajo: '#34d399',
}

export function EdgeCard({ edge, index }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: .25, delay: index * .04 }}
      className="rounded-lg p-3"
      style={{ background: '#0f0f18', border: '1px solid rgba(255,255,255,.07)' }}
    >
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <span className="text-xs font-mono font-medium text-qa-text">{edge.scenario}</span>
        <span className="text-[10px] font-mono text-qa-muted flex-shrink-0">{edge.id}</span>
      </div>
      {edge.description && (
        <p className="text-[11px] font-mono text-qa-muted2 mb-2">{edge.description}</p>
      )}
      {edge.risk_level && (
        <div className="flex items-center gap-1.5">
          <span className="section-label mb-0">Risk:</span>
          <span
            className="text-[10px] font-mono font-semibold uppercase px-1.5 py-0.5 rounded-sm"
            style={{
              color: riskColor[edge.risk_level] || '#8e8ea8',
              background: (riskColor[edge.risk_level] || '#8e8ea8') + '18',
              border: `1px solid ${riskColor[edge.risk_level] || '#8e8ea8'}30`,
            }}
          >
            {edge.risk_level}
          </span>
        </div>
      )}
    </motion.div>
  )
}
