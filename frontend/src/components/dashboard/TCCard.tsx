import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { RotateCw } from 'lucide-react'
import { catBadgeClass, catLabel } from '../../lib/utils'
import { postRegenerateTC } from '../../services/api'
import { useStore } from '../../store/useStore'
import { useShallow } from 'zustand/react/shallow'
import type { TestCase } from '../../types'

interface Props {
  tc: TestCase
  index: number
  onReplace: (index: number, tc: TestCase) => void
  defaultOpen?: boolean
}

export function TCCard({ tc, index, onReplace, defaultOpen = false }: Props) {
  const [open, setOpen] = useState(defaultOpen)
  const [regen, setRegen] = useState(false)

  const id = tc.id || `TC-${String(index + 1).padStart(3, '0')}`
  const { model, temperature, context, userStory, showToast } = useStore(useShallow(s => ({
    model: s.model, temperature: s.temperature, context: s.context,
    userStory: s.userStory, showToast: s.showToast,
  })))

  async function handleRegen(e: React.MouseEvent) {
    e.stopPropagation()
    if (!userStory.trim()) { showToast('A user story is required', '#fbbf24'); return }
    setRegen(true)
    try {
      const { test_case } = await postRegenerateTC({
        tc_id: tc.id || id, user_story: userStory,
        model, temperature, category: tc.category || '', context,
      })
      onReplace(index, test_case)
      showToast(`${id} regenerado`)
    } catch (e: unknown) {
      showToast('Regeneration error: ' + (e instanceof Error ? e.message : ''), '#f87171')
    } finally {
      setRegen(false)
    }
  }

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: .25 }}
      className="rounded-xl overflow-hidden tc-card"
      style={{ background: '#0f0f18', border: '1px solid rgba(255,255,255,.07)' }}
    >
      {/* Header row — collapse / expand toggle */}
      <div
        role="button"
        tabIndex={0}
        aria-expanded={open}
        aria-controls={`tc-body-${index}`}
        onClick={() => setOpen(o => !o)}
        onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && setOpen(o => !o)}
        className="flex items-center gap-2 px-3 py-2.5 cursor-pointer select-none transition-colors"
        style={{ background: open ? 'rgba(91,141,239,.04)' : 'transparent' }}
      >
        {/* ID chip */}
        <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded flex-shrink-0"
              style={{ background: 'rgba(91,141,239,.15)', color: 'var(--brand)', border: '1px solid rgba(91,141,239,.25)' }}>
          {id}
        </span>

        {/* Title */}
        <span className="text-xs font-mono font-semibold text-qa-text truncate flex-1">{tc.title}</span>

        {/* Badges + actions */}
        <div className="flex items-center gap-1 flex-shrink-0">
          {tc.priority && (
            <span className={`badge badge-${tc.priority}`}>{tc.priority.toUpperCase()}</span>
          )}
          {tc.category && (
            <span className={`badge ${catBadgeClass(tc.category)}`}>{catLabel(tc.category)}</span>
          )}
          <button
            onClick={handleRegen}
            disabled={regen}
            title="Regenerar este caso"
            aria-label={`Regenerar ${id}`}
            className="ml-1 w-5 h-5 flex items-center justify-center rounded text-qa-muted hover:text-qa-accent hover:bg-qa-accent/10 transition-colors"
          >
            <RotateCw size={10} className={regen ? 'animate-spin' : ''} />
          </button>
          <span className="text-[11px] transition-transform duration-200 select-none"
                style={{ color: '#5a5a74', display: 'inline-block', transform: open ? 'rotate(180deg)' : 'rotate(0deg)' }}>
            ▾
          </span>
        </div>
      </div>

      {/* Expandable body */}
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            id={`tc-body-${index}`}
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: .22 }}
            style={{ overflow: 'hidden' }}
          >
            <div className="px-3 pb-3 pt-2.5 space-y-2.5 border-t"
                 style={{ borderColor: 'rgba(255,255,255,.05)', background: '#0d0d17' }}>

              {/* Preconditions */}
              {tc.preconditions && tc.preconditions.length > 0 && (
                <section>
                  <p className="section-label">Preconditions</p>
                  <ul className="space-y-0.5">
                    {tc.preconditions.map((p, i) => (
                      <li key={i} className="text-[11px] font-mono text-qa-muted2 flex gap-1.5">
                        <span className="text-qa-muted flex-shrink-0">{i + 1}.</span>{p}
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {/* Steps */}
              <section>
                <p className="section-label">Steps</p>
                <ol className="space-y-0.5">
                  {(tc.steps || []).map((s, i) => (
                    <li key={i} className="text-[11px] font-mono text-qa-muted2 flex gap-1.5">
                      <span className="text-qa-muted flex-shrink-0">{i + 1}.</span>{s}
                    </li>
                  ))}
                </ol>
              </section>

              {/* Expected result */}
              <section>
                <p className="section-label">Expected Result</p>
                <p className="text-[11px] font-mono text-qa-muted2 leading-relaxed">{tc.expected_result}</p>
              </section>

              {/* Type */}
              {tc.test_type && (
                <section>
                  <p className="section-label">Type</p>
                  <p className="text-[11px] font-mono text-qa-muted">{tc.test_type}</p>
                </section>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
