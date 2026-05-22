import { create } from 'zustand'
import type {
  GenerateResult, TestCase, MetricResult,
  WorkflowStep, ActiveTab, AgentDecision, AgentNodeState, MetricBarState,
} from '../types'

function loadResult(): GenerateResult | null {
  try {
    const s = localStorage.getItem('lastResult')
    return s ? (JSON.parse(s) as GenerateResult) : null
  } catch { return null }
}

export interface AgentNode {
  state: AgentNodeState
  message: string
  elapsed: string
  stats: string
  progress: number
  decisions: AgentDecision[]
}

const IDLE_NODE: AgentNode = {
  state: 'idle', message: 'Waiting...', elapsed: '',
  stats: '', progress: 0, decisions: [],
}

export type AgentKey = 'generator' | 'reviewer' | 'optimizer'

export interface SmLogEntry {
  time: string; agent: string; text: string; type: string
}

export interface StreamMonitorState {
  visible: boolean
  agents: { gen: string; rev: string; opt: string }
  current: string
  log: SmLogEntry[]
}

interface AppState {
  // Form
  userStory: string
  context: string
  model: string
  evalModel: string
  temperature: number
  categories: string[]
  tcCount: number
  edgeCount: number
  bugCount: number
  agentMode: boolean
  useRag: boolean
  ragAvailable: boolean

  // Generation
  result: GenerateResult | null
  overallScore: number | null
  liveTCs: TestCase[]
  streaming: boolean
  generatorElapsed: number
  streamPreviewText: string
  streamCaseCount: number

  // Agent pipeline (right panel)
  agentNodes: Record<AgentKey, AgentNode>
  connectorsActive: [boolean, boolean]
  agentPipelineVisible: boolean

  // Stream monitor (main panel TC tab)
  streamMonitor: StreamMonitorState

  // Evaluation
  evalPipelineState: 'idle' | 'running' | 'done'
  evalMetrics: Record<string, MetricResult>
  metricBarStates: Record<string, MetricBarState>
  evalTimerElapsed: number

  // UI
  workflowStep: WorkflowStep
  activeTab: ActiveTab
  filters: { category: string; priority: string }
  toast: { msg: string; color: string; id: number } | null
  ollamaOk: boolean
  modelLoaded: boolean

  // Actions
  setForm(u: Partial<Pick<AppState,
    'userStory'|'context'|'model'|'evalModel'|'temperature'|
    'categories'|'tcCount'|'edgeCount'|'bugCount'|'agentMode'|'useRag'|'ragAvailable'
  >>): void
  setResult(r: GenerateResult | null): void
  setOverallScore(s: number | null): void
  appendLiveTC(tc: TestCase): void
  clearLiveTCs(): void
  setStreaming(on: boolean): void
  setGeneratorElapsed(s: number): void
  setStreamPreviewText(t: string): void
  incStreamCaseCount(): void
  resetStreamCaseCount(): void
  updateAgentNode(key: AgentKey, u: Partial<AgentNode>): void
  resetAgentNodes(): void
  setConnectors(c: [boolean, boolean]): void
  setAgentPipelineVisible(on: boolean): void
  setStreamMonitor(u: Partial<StreamMonitorState>): void
  addSmLog(e: SmLogEntry): void
  setSmAgentState(key: 'gen' | 'rev' | 'opt', state: string): void
  setEvalPipelineState(s: 'idle' | 'running' | 'done'): void
  setEvalMetric(key: string, r: MetricResult): void
  resetEvalMetrics(): void
  setMetricBarState(key: string, s: MetricBarState): void
  setEvalTimerElapsed(s: number): void
  setWorkflowStep(s: WorkflowStep): void
  setActiveTab(t: ActiveTab): void
  setFilters(f: Partial<{ category: string; priority: string }>): void
  showToast(msg: string, color?: string): void
  clearToast(): void
  setOllamaOk(ok: boolean): void
  setModelLoaded(loaded: boolean): void
  resetGeneration(): void
}

const initialResult = loadResult()
const INITIAL_METRIC_STATES: Record<string, MetricBarState> = {
  cov: 'idle', rel: 'idle', con: 'idle', spe: 'idle', nfb: 'idle',
}

export const useStore = create<AppState>((set, get) => ({
  userStory: '',
  context: '',
  model: 'llama3.2',
  evalModel: '',
  temperature: 0.25,
  categories: ['happy_path','edge_case','negative','security','performance','usability','compatibility'],
  tcCount: 10,
  edgeCount: 4,
  bugCount: 3,
  agentMode: false,
  useRag: false,
  ragAvailable: false,

  result: initialResult,
  overallScore: null,
  liveTCs: [],
  streaming: false,
  generatorElapsed: 0,
  streamPreviewText: '',
  streamCaseCount: 0,

  agentNodes: {
    generator: { ...IDLE_NODE },
    reviewer:  { ...IDLE_NODE },
    optimizer: { ...IDLE_NODE },
  },
  connectorsActive: [false, false],
  agentPipelineVisible: false,

  streamMonitor: {
    visible: false,
    agents: { gen: 'idle', rev: 'idle', opt: 'idle' },
    current: 'Initializing pipeline...',
    log: [],
  },

  evalPipelineState: 'idle',
  evalMetrics: {},
  metricBarStates: { ...INITIAL_METRIC_STATES },
  evalTimerElapsed: 0,

  workflowStep: initialResult ? 'evaluate' : 'input',
  activeTab: 'tc',
  filters: { category: '', priority: '' },
  toast: null,
  ollamaOk: false,
  modelLoaded: false,

  setForm: (u) => set(u),

  setResult: (result) => {
    if (result) localStorage.setItem('lastResult', JSON.stringify(result))
    else localStorage.removeItem('lastResult')
    set({ result })
  },

  setOverallScore: (overallScore) => set({ overallScore }),
  appendLiveTC: (tc) => set(s => ({ liveTCs: [...s.liveTCs, tc] })),
  clearLiveTCs: () => set({ liveTCs: [] }),
  setStreaming: (streaming) => set({ streaming }),
  setGeneratorElapsed: (generatorElapsed) => set({ generatorElapsed }),
  setStreamPreviewText: (streamPreviewText) => set({ streamPreviewText }),
  incStreamCaseCount: () => set(s => ({ streamCaseCount: s.streamCaseCount + 1 })),
  resetStreamCaseCount: () => set({ streamCaseCount: 0 }),

  updateAgentNode: (key, u) =>
    set(s => ({ agentNodes: { ...s.agentNodes, [key]: { ...s.agentNodes[key], ...u } } })),

  resetAgentNodes: () =>
    set({ agentNodes: { generator: { ...IDLE_NODE }, reviewer: { ...IDLE_NODE }, optimizer: { ...IDLE_NODE } } }),

  setConnectors: (connectorsActive) => set({ connectorsActive }),
  setAgentPipelineVisible: (agentPipelineVisible) => set({ agentPipelineVisible }),

  setStreamMonitor: (u) => set(s => ({ streamMonitor: { ...s.streamMonitor, ...u } })),
  addSmLog: (e) =>
    set(s => ({ streamMonitor: { ...s.streamMonitor, log: [...s.streamMonitor.log.slice(-29), e] } })),
  setSmAgentState: (key, state) =>
    set(s => ({ streamMonitor: { ...s.streamMonitor, agents: { ...s.streamMonitor.agents, [key]: state } } })),

  setEvalPipelineState: (evalPipelineState) => set({ evalPipelineState }),
  setEvalMetric: (key, r) => set(s => ({ evalMetrics: { ...s.evalMetrics, [key]: r } })),
  resetEvalMetrics: () => set({ evalMetrics: {}, metricBarStates: { ...INITIAL_METRIC_STATES } }),
  setMetricBarState: (key, s) =>
    set(st => ({ metricBarStates: { ...st.metricBarStates, [key]: s } })),
  setEvalTimerElapsed: (evalTimerElapsed) => set({ evalTimerElapsed }),

  setWorkflowStep: (workflowStep) => set({ workflowStep }),
  setActiveTab: (activeTab) => set({ activeTab }),
  setFilters: (f) => set(s => ({ filters: { ...s.filters, ...f } })),

  showToast: (msg, color = '#34d399') => {
    const id = Date.now()
    set({ toast: { msg, color, id } })
    setTimeout(() => { if (get().toast?.id === id) set({ toast: null }) }, 3500)
  },

  clearToast: () => set({ toast: null }),

  setOllamaOk: (ollamaOk) => set({ ollamaOk }),
  setModelLoaded: (modelLoaded) => set({ modelLoaded }),

  resetGeneration: () => {
    localStorage.removeItem('lastResult')
    set({
      result: null, overallScore: null,
      liveTCs: [], streaming: false, generatorElapsed: 0,
      streamPreviewText: '', streamCaseCount: 0,
      agentNodes: { generator: { ...IDLE_NODE }, reviewer: { ...IDLE_NODE }, optimizer: { ...IDLE_NODE } },
      connectorsActive: [false, false], agentPipelineVisible: false,
      streamMonitor: { visible: false, agents: { gen: 'idle', rev: 'idle', opt: 'idle' }, current: 'Initializing pipeline...', log: [] },
      evalPipelineState: 'idle', evalMetrics: {},
      metricBarStates: { ...INITIAL_METRIC_STATES }, evalTimerElapsed: 0,
      workflowStep: 'input', filters: { category: '', priority: '' },
    })
  },
}))
