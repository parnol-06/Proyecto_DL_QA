import { useEffect, useRef, useState } from 'react'
import { useStore } from '../store/useStore'
import { useShallow } from 'zustand/react/shallow'
import { fetchModels, fetchHealth, fetchModelStatus, checkRagStatus } from '../services/api'

export function useModels() {
  const { model, setForm, setOllamaOk, setModelLoaded } = useStore(useShallow(s => ({
    model: s.model,
    setForm: s.setForm,
    setOllamaOk: s.setOllamaOk,
    setModelLoaded: s.setModelLoaded,
  })))
  const [models, setModels] = useState<string[]>([])
  const prevModel = useRef(model)

  async function loadModels() {
    try {
      const data = await fetchModels()
      const list = data.models || []
      setModels(list)

      if (!data.ollama_available || list.length === 0) {
        setOllamaOk(false)
        return
      }
      if (!list.includes(useStore.getState().model)) {
        setForm({ model: list[0] })
      }
      try {
        const h = await fetchHealth()
        setOllamaOk(h.ollama)
      } catch { setOllamaOk(true) }

      loadModelStatus(useStore.getState().model)
    } catch {
      setOllamaOk(false)
    }
  }

  async function loadModelStatus(m: string) {
    try {
      const s = await fetchModelStatus(m)
      setModelLoaded(s.loaded)
    } catch {
      setModelLoaded(false)
    }
  }

  async function loadRagStatus() {
    try {
      const { built } = await checkRagStatus()
      useStore.getState().setForm({ ragAvailable: built })
    } catch {}
  }

  useEffect(() => {
    loadModels()
    loadRagStatus()
    const id1 = setInterval(loadModels, 300_000)
    const id2 = setInterval(loadRagStatus, 300_000)
    return () => { clearInterval(id1); clearInterval(id2) }
  }, [])

  useEffect(() => {
    if (model !== prevModel.current) {
      prevModel.current = model
      loadModelStatus(model)
    }
  }, [model])

  return { models, loadModels, loadModelStatus }
}
