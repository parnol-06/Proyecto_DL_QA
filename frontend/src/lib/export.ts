import type { GenerateResult } from '../types'

function download(content: string | Uint8Array<ArrayBuffer>, filename: string, type: string) {
  const blob = new Blob([content as BlobPart], { type })
  const url = URL.createObjectURL(blob)
  const a = Object.assign(document.createElement('a'), { href: url, download: filename })
  a.click()
  URL.revokeObjectURL(url)
}

export async function copyJSON(data: GenerateResult): Promise<void> {
  await navigator.clipboard.writeText(JSON.stringify(data, null, 2))
}

export function downloadJSON(data: GenerateResult): void {
  download(JSON.stringify(data, null, 2), 'test-cases.json', 'application/json')
}

export function downloadCSV(data: GenerateResult): void {
  const header = ['ID', 'Categoría', 'Título', 'Pasos', 'Resultado esperado', 'Prioridad']
  const rows = (data.test_cases || []).map(tc =>
    [tc.id || '', tc.category || '', tc.title || '',
     (tc.steps || []).join(' | '), tc.expected_result || '', tc.priority || '']
      .map(v => `"${String(v).replace(/"/g, '""')}"`)
  )
  const csv = [header, ...rows].map(r => r.join(',')).join('\r\n')
  download('﻿' + csv, 'test-cases.csv', 'text/csv;charset=utf-8')
}

export function downloadMarkdown(data: GenerateResult): void {
  const lines: string[] = ['# Test Cases', '']
  const byCategory: Record<string, typeof data.test_cases> = {}
  ;(data.test_cases || []).forEach(tc => {
    const cat = tc.category || 'general'
    if (!byCategory[cat]) byCategory[cat] = []
    byCategory[cat]!.push(tc)
  })
  for (const [cat, tcs] of Object.entries(byCategory)) {
    lines.push('## ' + cat.replace(/_/g, ' ').toUpperCase(), '')
    tcs!.forEach(tc => {
      lines.push('### ' + (tc.id || '') + ' · ' + tc.title, '')
      lines.push('**Prioridad:** ' + (tc.priority || ''), '')
      if (tc.preconditions?.length) {
        lines.push('**Precondiciones:*', ...(tc.preconditions.map(p => '- ' + p)), '')
      }
      lines.push('**Pasos:**', ...(tc.steps || []).map((s, i) => (i + 1) + '. ' + s), '')
      lines.push('> **Resultado esperado:** ' + tc.expected_result, '')
    })
  }
  download(lines.join('\n'), 'test-cases.md', 'text/markdown;charset=utf-8')
}

export function downloadXLSX(data: GenerateResult, showToast: (m: string, c?: string) => void): void {
  // @ts-ignore — xlsx loaded via npm
  const XLSX = (window as Record<string, unknown>).XLSX ?? (globalThis as Record<string, unknown>).XLSX
  import('xlsx').then(mod => {
    const X = mod.default ?? mod
    const wb = X.utils.book_new()

    const tcRows = (data.test_cases || []).map(tc => ({
      ID: tc.id || '', Título: tc.title || '', Categoría: tc.category || '',
      Prioridad: tc.priority || '', Tipo: tc.test_type || '',
      Precondiciones: (tc.preconditions || []).join(' | '),
      Pasos: (tc.steps || []).join(' | '), 'Resultado esperado': tc.expected_result || '',
    }))
    X.utils.book_append_sheet(wb, X.utils.json_to_sheet(tcRows.length ? tcRows : [{}]), 'Test Cases')

    const edgeRows = (data.edge_scenarios || []).map(e => ({
      ID: e.id || '', Escenario: e.scenario || '',
      'Nivel de riesgo': e.risk_level || '', Descripción: e.description || '',
    }))
    X.utils.book_append_sheet(wb, X.utils.json_to_sheet(edgeRows.length ? edgeRows : [{}]), 'Edge Scenarios')

    const bugRows = (data.potential_bugs || []).map(b => ({
      ID: b.id || '', Título: b.title || '', Área: b.area || '',
      Probabilidad: b.likelihood || '', Descripción: b.description || '',
      'Test sugerido': b.suggested_test || '',
    }))
    X.utils.book_append_sheet(wb, X.utils.json_to_sheet(bugRows.length ? bugRows : [{}]), 'Potential Bugs')

    const cov = data.coverage_summary || {}
    const covRows = [
      { Métrica: 'Total casos',            Valor: cov.total_test_cases ?? '' },
      { Métrica: 'Categorías cubiertas',   Valor: (cov.categories_covered || []).join(', ') },
      { Métrica: 'Cobertura estimada (%)', Valor: cov.estimated_coverage_percent ?? '' },
      { Métrica: 'Áreas faltantes',        Valor: (cov.missing_areas || []).join(', ') },
    ]
    X.utils.book_append_sheet(wb, X.utils.json_to_sheet(covRows), 'Coverage')
    X.writeFile(wb, 'test-cases.xlsx')
    showToast('XLSX exportado correctamente')
  }).catch(() => showToast('XLSX no disponible', '#f87171'))
}
