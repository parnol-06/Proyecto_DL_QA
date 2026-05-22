import { useStore } from '../../store/useStore'
import { fmtTime } from '../../lib/utils'

const STEPS = [
  { id: 'input',    label: 'Input' },
  { id: 'generate', label: 'Generating' },
  { id: 'evaluate', label: 'Evaluating' },
  { id: 'export',   label: 'Export' },
] as const

export function WorkflowBar() {
  const { workflowStep, generatorElapsed, evalTimerElapsed, streaming } = useStore(s => ({
    workflowStep: s.workflowStep,
    generatorElapsed: s.generatorElapsed,
    evalTimerElapsed: s.evalTimerElapsed,
    streaming: s.streaming,
  }))

  const activeIdx = STEPS.findIndex(s => s.id === workflowStep)

  return (
    <div className="flex items-center gap-0 px-4 py-2.5 border-b shrink-0"
         style={{ borderColor: 'rgba(255,255,255,.05)', background: '#0f0f18' }}>
      {STEPS.map((step, i) => {
        const state = i < activeIdx ? 'done' : i === activeIdx ? 'active' : 'idle'
        const isTimer = (step.id === 'generate' && streaming && generatorElapsed > 0)
                     || (step.id === 'evaluate' && evalTimerElapsed > 0 && workflowStep === 'evaluate')

        return (
          <div key={step.id} className="flex items-center">
            <div className="flex items-center gap-1.5">
              <div
                className="w-2 h-2 rounded-full transition-all duration-300"
                style={{
                  background: state === 'done' ? '#34d399'
                            : state === 'active' ? '#7c6dfa'
                            : 'rgba(100,100,122,.35)',
                  boxShadow: state === 'active' ? '0 0 6px rgba(124,109,250,.5)' : 'none',
                }}
              />
              <span className="text-[10px] font-mono transition-colors"
                    style={{ color: state === 'active' ? '#c4b5fd' : state === 'done' ? '#34d399' : '#64647a' }}>
                {step.label}
              </span>
              {isTimer && (
                <span className="text-[9px] font-mono" style={{ color: '#7c6dfa' }}>
                  {fmtTime(step.id === 'generate' ? generatorElapsed : evalTimerElapsed)}
                </span>
              )}
            </div>
            {i < STEPS.length - 1 && (
              <div className="w-6 h-px mx-2 transition-all duration-500"
                   style={{ background: i < activeIdx ? 'rgba(52,211,153,.4)' : 'rgba(100,100,122,.2)' }} />
            )}
          </div>
        )
      })}
    </div>
  )
}
