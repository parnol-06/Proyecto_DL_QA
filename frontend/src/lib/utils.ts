export function cn(...classes: (string | false | undefined | null)[]): string {
  return classes.filter(Boolean).join(' ')
}

export function catBadgeClass(cat?: string): string {
  const map: Record<string, string> = {
    happy_path:     'badge-happy',
    edge_case:      'badge-edge',
    negative:       'badge-negative',
    security:       'badge-security',
    performance:    'badge-performance',
    usability:      'badge-usability',
    compatibility:  'badge-compatibility',
    // Backward-compat: legacy Spanish values from stored data
    caso_limite:    'badge-edge',
    negativo:       'badge-negative',
    seguridad:      'badge-security',
    rendimiento:    'badge-performance',
    usabilidad:     'badge-usability',
    compatibilidad: 'badge-compatibility',
  }
  return map[cat || ''] ?? 'badge-low'
}

export function catLabel(cat?: string): string {
  const labels: Record<string, string> = {
    happy_path:     'Happy Path',
    edge_case:      'Edge Case',
    negative:       'Negative',
    security:       'Security',
    performance:    'Performance',
    usability:      'Usability',
    compatibility:  'Compatibility',
    // Backward-compat: legacy Spanish values
    caso_limite:    'Edge Case',
    negativo:       'Negative',
    seguridad:      'Security',
    rendimiento:    'Performance',
    usabilidad:     'Usability',
    compatibilidad: 'Compatibility',
  }
  return labels[cat || ''] ?? (cat || '').replace(/_/g, ' ')
}

export function fmtTime(secs: number): string {
  if (secs < 60) return `${secs}s`
  return `${Math.floor(secs / 60)}m ${secs % 60}s`
}

export function scoreColor(score: number): string {
  if (score >= 0.7) return '#34d399'
  if (score >= 0.5) return '#fbbf24'
  return '#f87171'
}

export function clampPct(val: number): number {
  return Math.max(0, Math.min(100, Math.round(val * 100)))
}

export function nowTime(): string {
  return new Date().toLocaleTimeString('en', { hour12: false })
}
