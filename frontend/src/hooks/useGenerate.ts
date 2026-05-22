import { useRef, useState } from 'react'
import { useStore } from '../store/useStore'
import { readSSE } from '../services/sse'
import type { GenerateResult, TestCase } from '../types'
import { nowTime } from '../lib/utils'

type AgentKey = 'generator' | 'reviewer' | 'optimizer'

const AGENT_KEYS: Record<string, AgentKey> = {
  'Generator': 'generator', 'Reviewer': 'reviewer', 'Optimizer': 'optimizer',
}
const AGENT_MSGS: Record<string, string> = {
  'Generator': 'Generating test cases from the user story...',
  'Reviewer':  'Analysing quality and consistency of the cases...',
  'Optimizer': 'Optimising coverage and identifying critical gaps...',
}

export function useGenerate() {
  const [loading, setLoading] = useState(false)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  function clearTimer() {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null }
  }

  function getParams(story: string) {
    const s = useStore.getState()
    return {
      user_story: story,
      model: s.model,
      context: s.context,
      temperature: s.temperature,
      use_rag: s.useRag,
      categories: s.categories,
      tc_count: s.tcCount,
      edge_count: s.edgeCount,
      bug_count: s.bugCount,
    }
  }

  async function generate() {
    const s = useStore.getState()
    const story = s.userStory.trim()
    if (!story) { s.showToast('Enter a user story first', '#fbbf24'); return }
    if (s.agentMode) return generateAgents()

    const t0 = Date.now()
    setLoading(true)
    s.setStreaming(true)
    s.clearLiveTCs()
    s.resetStreamCaseCount()
    s.setStreamPreviewText('Starting generation...')
    s.setWorkflowStep('generate')
    s.setActiveTab('tc')
    timerRef.current = setInterval(() =>
      useStore.getState().setGeneratorElapsed(Math.round((Date.now() - t0) / 1000)), 1000)

    try {
      const res = await fetch('/generate/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(getParams(story)),
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Server error')

      let localCount = 0
      for await (const msg of readSSE(res)) {
        if (msg.token !== undefined) {
          const st = useStore.getState()
          st.setStreamPreviewText(
            localCount > 0
              ? `Generating... ${localCount} case${localCount > 1 ? 's' : ''} detected`
              : 'Processing...'
          )
        } else if (msg.case) {
          const tc = msg.case as TestCase
          useStore.getState().appendLiveTC(tc)
          useStore.getState().incStreamCaseCount()
          useStore.getState().setActiveTab('tc')
          localCount++
        } else if (msg.result) {
          const data = msg.result as GenerateResult
          clearTimer()
          const elapsed = Math.round((Date.now() - t0) / 1000)
          useStore.getState().setResult(data)
          useStore.getState().clearLiveTCs()
          useStore.getState().setStreaming(false)
          useStore.getState().setWorkflowStep('evaluate')
          useStore.getState().setEvalPipelineState('idle')
          const tcCount = (data.test_cases || []).length
          useStore.getState().showToast(
            `${tcCount} cases generated in ${elapsed}s${useStore.getState().useRag ? ' · RAG' : ''}`
          )
        } else if (msg.error) {
          throw new Error(msg.error as string)
        }
      }
    } catch (e: unknown) {
      useStore.getState().setStreaming(false)
      useStore.getState().showToast('Error: ' + (e instanceof Error ? e.message : String(e)), '#f87171')
      useStore.getState().setWorkflowStep('input')
    } finally {
      clearTimer()
      setLoading(false)
    }
  }

  async function generateAgents() {
    const s = useStore.getState()
    const story = s.userStory.trim()
    const t0 = Date.now()

    setLoading(true)
    s.setStreaming(true)
    s.clearLiveTCs()
    s.resetStreamCaseCount()
    s.setWorkflowStep('generate')
    s.setActiveTab('tc')
    s.setAgentPipelineVisible(true)
    s.resetAgentNodes()
    s.setConnectors([false, false])
    s.setStreamMonitor({
      visible: true, log: [],
      agents: { gen: 'idle', rev: 'idle', opt: 'idle' },
      current: 'Iniciando pipeline...',
    })

    timerRef.current = setInterval(() =>
      useStore.getState().setGeneratorElapsed(Math.round((Date.now() - t0) / 1000)), 1000)

    let localCount = 0

    try {
      const res = await fetch('/generate/agents/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(getParams(story)),
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Agent pipeline error')

      for await (const msg of readSSE(res)) {
        const st = useStore.getState()

        if (msg.event === 'agent_start') {
          const agent = msg.agent as string
          const step = msg.step as number
          const nodeKey = AGENT_KEYS[agent]
          if (nodeKey) {
            st.updateAgentNode(nodeKey, { state: 'running', message: AGENT_MSGS[agent] || 'Procesando...', progress: 3 })
          }
          if (step > 1) st.setConnectors([true, step > 2])
          st.setStreamMonitor({ current: `${agent} · step ${step}/${msg.total}` })
          st.addSmLog({ time: nowTime(), agent, text: AGENT_MSGS[agent] || 'Processing...', type: 'info' })

        } else if (msg.event === 'token') {
          const agentName = (msg.agent as string) || 'Generator'
          const nodeKey = AGENT_KEYS[agentName]
          if (nodeKey) {
            const elapsed = Math.round((Date.now() - t0) / 1000)
            const pct = localCount > 0 ? Math.min(88, 10 + localCount * 6) : Math.min(55, elapsed * 1.8)
            st.updateAgentNode(nodeKey, {
              progress: pct,
              stats: localCount > 0 ? `${localCount} cases · ${elapsed}s` : `${elapsed}s`,
            })
          }

        } else if (msg.event === 'case') {
          const tc = msg.case as TestCase
          st.appendLiveTC(tc)
          st.incStreamCaseCount()
          localCount++
          st.addSmLog({ time: nowTime(), agent: 'Generator', text: `${tc.id || `TC-${localCount}`} generated (${tc.category || 'general'})`, type: 'case' })
          st.updateAgentNode('generator', {
            progress: Math.min(88, 10 + localCount * 6),
            stats: `${localCount} cases · ${Math.round((Date.now()-t0)/1000)}s`,
          })

        } else if (msg.event === 'agent_done') {
          const agent = msg.agent as string
          const step = msg.step as number
          const nodeKey = AGENT_KEYS[agent]
          if (nodeKey) {
            st.updateAgentNode(nodeKey, {
              state: 'done',
              message: (msg.summary as string) || 'Completed',
              elapsed: `${msg.elapsed_s}s`,
              progress: 100,
              decisions: (msg.decisions as typeof st.agentNodes.reviewer.decisions) || [],
            })
          }
          st.setConnectors([step >= 1, step >= 2] as [boolean, boolean])
          st.addSmLog({ time: nowTime(), agent, text: `completed in ${msg.elapsed_s}s — ${((msg.summary as string)||'').slice(0,90)}`, type: 'done' })

          if (agent === 'Reviewer') {
            const decisions = (msg.decisions as Array<{tc_id?:string;id?:string;verdict:string;reason?:string}>) || []
            decisions.forEach(d => {
              const type = d.verdict === 'APPROVED' ? 'pass' : d.verdict === 'REJECTED' ? 'fail' : 'mod'
              st.addSmLog({ time: nowTime(), agent: 'Reviewer', text: `${d.tc_id||d.id} ${d.verdict}${d.reason ? ' — '+d.reason.slice(0,55) : ''}`, type })
            })
          }
          if (agent === 'Generator' && msg.data) {
            st.setResult({ ...(msg.data as GenerateResult), raw_story: story })
          }

        } else if (msg.event === 'done') {
          const data = msg.data as GenerateResult
          clearTimer()
          const elapsed = Math.round((Date.now() - t0) / 1000)
          useStore.getState().setResult(data)
          useStore.getState().clearLiveTCs()
          useStore.getState().setStreaming(false)
          useStore.getState().setStreamMonitor({ visible: false })
          useStore.getState().setWorkflowStep('evaluate')
          useStore.getState().setEvalPipelineState('idle')
          const tcCount = (data.test_cases || []).length
          const tag = data.used_fallback ? ' (fallback)' : ''
          useStore.getState().showToast(`${tcCount} casos · ${elapsed}s${tag}`)

        } else if (msg.event === 'error') {
          throw new Error((msg.message as string) || 'Agent pipeline error')
        }
      }
    } catch (e: unknown) {
      useStore.getState().setStreaming(false)
      useStore.getState().setStreamMonitor({ visible: false })
      useStore.getState().updateAgentNode('generator', { state: 'error', message: e instanceof Error ? e.message : 'Error' })
      useStore.getState().showToast('Error: ' + (e instanceof Error ? e.message : String(e)), '#f87171')
      useStore.getState().setWorkflowStep('input')
    } finally {
      clearTimer()
      setLoading(false)
    }
  }

  async function generateBatch() {
    const s = useStore.getState()
    const stories = s.userStory.trim().split(/\n---+\n/).map(x => x.trim()).filter(x => x.length >= 20)
    if (stories.length < 2) { s.showToast('Separate stories with "---" on its own line', '#fbbf24'); return }

    setLoading(true)
    s.showToast(`Processing ${stories.length} stories in batch...`, '#22d3ee')

    const merged: GenerateResult = { test_cases: [], edge_scenarios: [], potential_bugs: [], coverage_summary: {} }
    for (let i = 0; i < stories.length; i++) {
      useStore.getState().setStreamPreviewText(`Story ${i + 1}/${stories.length}...`)
      try {
        const res = await fetch('/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(getParams(stories[i])),
        })
        if (!res.ok) continue
        const r = await res.json() as GenerateResult
        ;(r.test_cases || []).forEach((tc, j) => { tc.id = `B${i+1}-TC-${String(j+1).padStart(3,'0')}`; merged.test_cases!.push(tc) })
        ;(r.edge_scenarios || []).forEach((e, j) => { e.id = `B${i+1}-ES-${String(j+1).padStart(3,'0')}`; merged.edge_scenarios!.push(e) })
        ;(r.potential_bugs || []).forEach((b, j) => { b.id = `B${i+1}-BUG-${String(j+1).padStart(3,'0')}`; merged.potential_bugs!.push(b) })
      } catch { /* continue */ }
    }
    const cats = [...new Set(merged.test_cases!.map(tc => tc.category).filter(Boolean))] as string[]
    merged.coverage_summary = {
      total_test_cases: merged.test_cases!.length,
      categories_covered: cats,
      estimated_coverage_percent: Math.min(95, 50 + merged.test_cases!.length * 2),
      missing_areas: [],
    }
    useStore.getState().setResult(merged)
    useStore.getState().setWorkflowStep('evaluate')
    useStore.getState().setEvalPipelineState('idle')
    setLoading(false)
    useStore.getState().showToast(`Batch: ${merged.test_cases!.length} TCs from ${stories.length} stories`)
  }

  return { generate, generateAgents, generateBatch, loading }
}
