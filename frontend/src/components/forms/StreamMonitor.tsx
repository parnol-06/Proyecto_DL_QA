import { useEffect, useRef } from 'react'
import { useStore } from '../../store/useStore'
import { useShallow } from 'zustand/react/shallow'

const AGENT_KEYS = ['gen', 'rev', 'opt'] as const
const AGENT_NAMES = { gen: 'Generator', rev: 'Reviewer', opt: 'Optimizer' }

const LOG_COLORS: Record<string, string> = {
  info: '#8e8ea8', done: '#34d399', case: '#7c6dfa',
  pass: '#34d399', fail: '#f87171', mod: '#fbbf24',
  warn: '#fbbf24', error: '#f87171',
}

const AGENT_STATE_COLORS: Record<string, string> = {
  idle: '#64647a', running: '#7c6dfa', done: '#34d399', error: '#f87171',
}

export function StreamMonitor() {
  const { streamMonitor, generatorElapsed } = useStore(useShallow(s => ({
    streamMonitor: s.streamMonitor,
    generatorElapsed: s.generatorElapsed,
  })))
  const logRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [streamMonitor.log.length])

  if (!streamMonitor.visible) return null

  return (
    <div className="mb-3 rounded-lg overflow-hidden panel-fade"
         style={{ background: '#0f0f18', border: '1px solid rgba(255,255,255,.07)' }}>
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b"
           style={{ borderColor: 'rgba(255,255,255,.05)', background: '#151520' }}>
        <div className="flex items-center gap-3">
          {AGENT_KEYS.map(key => (
            <div key={key} className="flex items-center gap-1">
              <div className="w-1.5 h-1.5 rounded-full transition-colors"
                   style={{
                     background: AGENT_STATE_COLORS[streamMonitor.agents[key]] || '#64647a',
                     animation: streamMonitor.agents[key] === 'running' ? 'livePulse 1.2s ease-in-out infinite' : 'none',
                   }} />
              <span className="text-[10px] font-mono"
                    style={{ color: streamMonitor.agents[key] === 'running' ? '#c4b5fd' : '#64647a' }}>
                {AGENT_NAMES[key]}
              </span>
            </div>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono text-qa-muted truncate max-w-[120px]">{streamMonitor.current}</span>
          <span className="text-[10px] font-mono text-qa-accent">{generatorElapsed}s</span>
        </div>
      </div>

      {/* Log */}
      <div ref={logRef} className="h-28 overflow-y-auto px-2 py-1.5 space-y-0.5">
        {streamMonitor.log.slice(-12).map((e, i) => (
          <div key={i} className="flex items-start gap-1.5 text-[10px] font-mono leading-relaxed">
            <span className="text-qa-muted flex-shrink-0">{e.time}</span>
            <span className="flex-shrink-0" style={{ color: AGENT_STATE_COLORS[e.agent === 'Generator' ? 'running' : 'idle'] || '#64647a' }}>
              {e.agent}
            </span>
            <span style={{ color: LOG_COLORS[e.type] || '#8e8ea8' }}>{e.text}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
