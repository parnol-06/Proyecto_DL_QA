export interface TestCase {
  id?: string
  title: string
  category?: string
  priority?: string
  test_type?: string
  preconditions?: string[]
  steps: string[]
  expected_result: string
}

export interface EdgeScenario {
  id?: string
  scenario: string
  risk_level?: string
  description?: string
}

export interface PotentialBug {
  id?: string
  title: string
  area?: string
  likelihood?: string
  description?: string
  suggested_test?: string
}

export interface CoverageSummary {
  total_test_cases?: number
  categories_covered?: string[]
  estimated_coverage_percent?: number
  missing_areas?: string[]
}

export interface AgentDecision {
  tc_id?: string
  id?: string
  verdict: string
  reason?: string
}

export interface AgentTrace {
  agent: string
  elapsed_s: number
  summary: string
  decisions?: AgentDecision[]
}

export interface OptimizerGap {
  rank: number
  reason: string
  category: string
  impact: string
}

export interface OptimizerOutput {
  priority_gaps?: OptimizerGap[]
  optimization_summary?: string
}

export interface GenerateResult {
  test_cases?: TestCase[]
  edge_scenarios?: EdgeScenario[]
  potential_bugs?: PotentialBug[]
  coverage_summary?: CoverageSummary
  agent_trace?: AgentTrace[]
  optimizer_output?: OptimizerOutput
  used_fallback?: boolean
  raw_story?: string
}

export interface MetricResult {
  score: number
  passed: boolean
  elapsed_ms: number
  reason: string
}

export type WorkflowStep = 'input' | 'generate' | 'evaluate' | 'export'
export type ActiveTab = 'tc' | 'edge' | 'bugs' | 'agents' | 'metrics'
export type MetricKey = 'coverage' | 'relevancy' | 'consistency' | 'specificity' | 'nonfunctional_balance'
export type MetricShortKey = 'cov' | 'rel' | 'con' | 'spe' | 'nfb'
export type MetricBarState = 'idle' | 'running' | 'pass' | 'warn'
export type AgentNodeState = 'idle' | 'running' | 'done' | 'error'
