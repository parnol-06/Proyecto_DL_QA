import type { TestCase } from '../types'

export async function fetchModels(): Promise<{ models: string[]; ollama_available: boolean }> {
  const r = await fetch('/models')
  if (!r.ok) throw new Error('Failed to fetch models')
  return r.json()
}

export async function fetchHealth(): Promise<{ ollama: boolean }> {
  const r = await fetch('/health')
  return r.json()
}

export async function fetchModelStatus(model: string): Promise<{ loaded: boolean }> {
  const r = await fetch(`/model-status?model=${encodeURIComponent(model)}`)
  return r.json()
}

export async function postPullModel(model: string): Promise<void> {
  const r = await fetch('/pull-model', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model }),
  })
  if (!r.ok) throw new Error((await r.json()).detail || 'Error al descargar')
}

export async function checkRagStatus(): Promise<{ built: boolean; chunk_count: number }> {
  const r = await fetch('/rag/status')
  return r.json()
}

export async function postRegenerateTC(params: {
  tc_id: string
  user_story: string
  model: string
  temperature: number
  category: string
  context: string
}): Promise<{ test_case: TestCase }> {
  const r = await fetch('/regenerate-tc', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  if (!r.ok) throw new Error((await r.json()).detail || 'Error al regenerar')
  return r.json()
}
