import { useRef, useState } from 'react'
import { useStore } from '../store/useStore'
import { readSSE } from '../services/sse'
import { fmtTime } from '../lib/utils'
import type { MetricResult } from '../types'

const KEY_MAP: Record<string, string> = {
  coverage: 'cov', relevancy: 'rel', consistency: 'con',
  specificity: 'spe', nonfunctional_balance: 'nfb',
}
const RP_KEYS = ['cov', 'rel', 'con', 'spe', 'nfb']

export function useEvaluate() {
  const [loading, setLoading] = useState(false)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  function clearTimer() {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null }
  }

  async function evaluate() {
    const s = useStore.getState()
    if (!s.result) { s.showToast('Generate test cases first', '#fbbf24'); return }
    const story = s.userStory.trim()
    if (!story) { s.showToast('A user story is required to evaluate', '#fbbf24'); return }

    setLoading(true)
    s.resetEvalMetrics()
    RP_KEYS.forEach(k => s.setMetricBarState(k, 'idle'))
    s.setMetricBarState('cov', 'running')
    s.setEvalPipelineState('running')
    s.setActiveTab('metrics')
    s.setEvalTimerElapsed(0)

    const t0 = Date.now()
    timerRef.current = setInterval(() => {
      s.setEvalTimerElapsed(Math.round((Date.now() - t0) / 1000))
    }, 1000)

    s.showToast('Evaluating with DeepEval... (may take several minutes)', '#22d3ee')

    try {
      const evalModel = s.evalModel || s.model
      const res = await fetch('/evaluate/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          requirement: story,
          generated_output: s.result,
          model: s.model,
          eval_model: evalModel,
        }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Evaluation error')

      for await (const msg of readSSE(res)) {
        if (msg.error) throw new Error(msg.error as string)

        if (msg.metric) {
          const shortKey = KEY_MAP[msg.metric as string]
          const result: MetricResult = {
            score: msg.score as number,
            passed: msg.passed as boolean,
            elapsed_ms: (msg.elapsed_ms as number) || 0,
            reason: (msg.reason as string) || '',
          }
          if (shortKey) {
            useStore.getState().setEvalMetric(msg.metric as string, result)
            useStore.getState().setMetricBarState(shortKey, result.passed ? 'pass' : 'warn')
            const nextKey = RP_KEYS[msg.step as number]
            if (nextKey) useStore.getState().setMetricBarState(nextKey, 'running')
          }

          const icon = result.passed ? '✓' : '✗'
          const color = result.passed ? '#34d399' : '#fbbf24'
          useStore.getState().showToast(
            `${msg.name} ${icon} ${result.score.toFixed(2)} (${msg.step}/${msg.total})`,
            color
          )
        }

        if (msg.done) {
          const totalElapsed = Math.round((Date.now() - t0) / 1000)
          clearTimer()
          useStore.getState().setEvalTimerElapsed(totalElapsed)
          useStore.getState().setEvalPipelineState('done')
          useStore.getState().setOverallScore(msg.overall as number)
          useStore.getState().setWorkflowStep('export')
          useStore.getState().showToast(
            `Evaluation complete in ${fmtTime(totalElapsed)} · overall ${(msg.overall as number).toFixed(2)}`
          )
        }
      }
    } catch (e: unknown) {
      clearTimer()
      useStore.getState().setEvalPipelineState('idle')
      useStore.getState().showToast('Error: ' + (e instanceof Error ? e.message : String(e)), '#f87171')
    } finally {
      clearTimer()
      setLoading(false)
    }
  }

  return { evaluate, loading }
}
