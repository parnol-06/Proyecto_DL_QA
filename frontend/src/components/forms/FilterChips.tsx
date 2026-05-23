import { useStore } from '../../store/useStore'
import { useShallow } from 'zustand/react/shallow'

const CATEGORIES = [
  { value: 'happy_path',    label: 'Happy Path',    color: '#34d399', bg: 'rgba(52,211,153,.16)',  border: 'rgba(52,211,153,.4)',  glow: 'rgba(52,211,153,.12)'  },
  { value: 'edge_case',     label: 'Edge Case',     color: '#fbbf24', bg: 'rgba(251,191,36,.16)',  border: 'rgba(251,191,36,.4)',  glow: 'rgba(251,191,36,.12)'  },
  { value: 'negative',      label: 'Negative',      color: '#f87171', bg: 'rgba(248,113,113,.16)', border: 'rgba(248,113,113,.4)', glow: 'rgba(248,113,113,.12)' },
  { value: 'security',      label: 'Security',      color: '#fb923c', bg: 'rgba(251,146,60,.16)',  border: 'rgba(251,146,60,.4)',  glow: 'rgba(251,146,60,.12)'  },
  { value: 'performance',   label: 'Performance',   color: '#60a5fa', bg: 'rgba(96,165,250,.16)',  border: 'rgba(96,165,250,.4)',  glow: 'rgba(96,165,250,.12)'  },
  { value: 'usability',     label: 'Usability',     color: '#22d3ee', bg: 'rgba(34,211,238,.16)',  border: 'rgba(34,211,238,.4)',  glow: 'rgba(34,211,238,.12)'  },
  { value: 'compatibility', label: 'Compatibility', color: '#60a5fa', bg: 'rgba(96,165,250,.16)',  border: 'rgba(96,165,250,.4)',  glow: 'rgba(96,165,250,.12)'  },
]

const PRIORITIES = [
  { value: 'high',   label: 'High',   color: '#f87171', bg: 'rgba(248,113,113,.16)', border: 'rgba(248,113,113,.4)', glow: 'rgba(248,113,113,.12)' },
  { value: 'medium', label: 'Medium', color: '#fbbf24', bg: 'rgba(251,191,36,.16)',  border: 'rgba(251,191,36,.4)',  glow: 'rgba(251,191,36,.12)'  },
  { value: 'low',    label: 'Low',    color: '#34d399', bg: 'rgba(52,211,153,.16)',  border: 'rgba(52,211,153,.4)',  glow: 'rgba(52,211,153,.12)'  },
]

interface Props {
  onCategoryChange?: (cat: string) => void
  onPriorityChange?: (prio: string) => void
}

export function FilterChips({ onCategoryChange, onPriorityChange }: Props) {
  const { filters, setFilters } = useStore(useShallow(s => ({
    filters: s.filters,
    setFilters: s.setFilters,
  })))

  function toggleCat(val: string) {
    const next = filters.category === val ? '' : val
    setFilters({ category: next })
    onCategoryChange?.(next)
  }

  function togglePrio(val: string) {
    const next = filters.priority === val ? '' : val
    setFilters({ priority: next })
    onPriorityChange?.(next)
  }

  return (
    <div className="space-y-1.5">
      {/* Category chips — pill-shaped, single row, scrollable */}
      <div role="group" aria-label="Filter by category"
           className="flex gap-1.5 overflow-x-auto pb-0.5 scrollbar-hide">
        {CATEGORIES.map(c => {
          const active = filters.category === c.value
          return (
            <button
              key={c.value}
              onClick={() => toggleCat(c.value)}
              aria-pressed={active}
              className="text-[10px] font-mono px-2.5 py-0.5 rounded-full transition-all duration-150 font-semibold whitespace-nowrap"
              style={
                active
                  ? {
                      background: c.bg,
                      color: c.color,
                      border: `1px solid ${c.border}`,
                      boxShadow: `0 0 10px ${c.glow}`,
                    }
                  : {
                      background: 'rgba(255,255,255,.04)',
                      color: '#5a5a74',
                      border: '1px solid rgba(255,255,255,.07)',
                    }
              }
            >
              {c.label}
            </button>
          )
        })}
      </div>

      {/* Priority chips — pill-shaped */}
      <div role="group" aria-label="Filter by priority"
           className="flex gap-1.5">
        {PRIORITIES.map(p => {
          const active = filters.priority === p.value
          return (
            <button
              key={p.value}
              onClick={() => togglePrio(p.value)}
              aria-pressed={active}
              className="text-[10px] font-mono px-2.5 py-0.5 rounded-full transition-all duration-150 font-semibold"
              style={
                active
                  ? {
                      background: p.bg,
                      color: p.color,
                      border: `1px solid ${p.border}`,
                      boxShadow: `0 0 10px ${p.glow}`,
                    }
                  : {
                      background: 'rgba(255,255,255,.04)',
                      color: '#5a5a74',
                      border: '1px solid rgba(255,255,255,.07)',
                    }
              }
            >
              {p.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}
