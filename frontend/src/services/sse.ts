export type SSEMessage = Record<string, unknown>

export async function* readSSE(response: Response): AsyncGenerator<SSEMessage> {
  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try { yield JSON.parse(line.slice(6)) } catch { /* skip invalid JSON */ }
      }
    }
  } finally {
    reader.releaseLock()
  }
}
