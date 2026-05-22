import { motion } from 'framer-motion'
import type { PotentialBug } from '../../types'

interface Props { bug: PotentialBug; index: number }

const likeColor: Record<string, string> = {
  high: '#f87171', alto: '#f87171',
  medium: '#fbbf24', medio: '#fbbf24',
  low: '#34d399', bajo: '#34d399',
}

export function BugCard({ bug, index }: Props) {
  const lc = likeColor[bug.likelihood || ''] || '#8e8ea8'
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: .25, delay: index * .04 }}
      className="rounded-lg p-3"
      style={{ background: '#0f0f18', border: '1px solid rgba(255,255,255,.07)' }}
    >
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <span className="text-xs font-mono font-medium text-qa-text">{bug.title}</span>
        <span className="text-[10px] font-mono text-qa-muted flex-shrink-0">{bug.id}</span>
      </div>
      {bug.description && (
        <p className="text-[11px] font-mono text-qa-muted2 mb-2">{bug.description}</p>
      )}
      <div className="flex items-center gap-3 flex-wrap">
        {bug.area && (
          <span className="text-[10px] font-mono text-qa-muted">
            Área: <span className="text-qa-muted2">{bug.area}</span>
          </span>
        )}
        {bug.likelihood && (
          <span
            className="text-[10px] font-mono font-semibold uppercase px-1.5 py-0.5 rounded-sm"
            style={{ color: lc, background: lc + '18', border: `1px solid ${lc}30` }}
          >
            {bug.likelihood}
          </span>
        )}
      </div>
      {bug.suggested_test && (
        <div className="mt-2 px-2 py-1.5 rounded"
             style={{ background: 'rgba(251,191,36,.06)', border: '1px solid rgba(251,191,36,.15)' }}>
          <span className="text-[11px] font-mono text-qa-amber">💡 {bug.suggested_test}</span>
        </div>
      )}
    </motion.div>
  )
}
