/**
 * API client composable — talks to the vargen FastAPI backend.
 */
export function useApi() {
  const config = useRuntimeConfig()
  const base = config.public.apiBase

  async function fetchJson(path: string, options?: RequestInit) {
    const res = await fetch(`${base}${path}`, {
      headers: { 'Content-Type': 'application/json', ...options?.headers },
      ...options,
    })
    if (!res.ok) {
      const text = await res.text()
      throw new Error(`API ${res.status}: ${text}`)
    }
    return res.json()
  }

  // Pipelines
  const listPipelines = () => fetchJson('/api/pipelines')
  const getPipeline = (id: string) => fetchJson(`/api/pipelines/${id}`)
  const savePipeline = (id: string, yaml: string) =>
    fetchJson(`/api/pipelines/${id}`, { method: 'PUT', body: JSON.stringify({ yaml }) })
  const deletePipeline = (id: string) =>
    fetchJson(`/api/pipelines/${id}`, { method: 'DELETE' })

  // Models
  const getModelStatus = () => fetchJson('/api/models/status')
  const checkModels = (yaml: string) =>
    fetchJson('/api/models/check', { method: 'POST', body: JSON.stringify({ yaml }) })

  // Outputs
  const listOutputs = (limit = 50) => fetchJson(`/api/outputs?limit=${limit}`)
  const outputUrl = (filename: string) => `${base}/api/outputs/${filename}`

  // Upload
  async function uploadImage(file: File): Promise<{ filename: string; url: string }> {
    const form = new FormData()
    form.append('file', file)
    const res = await fetch(`${base}/api/upload`, { method: 'POST', body: form })
    if (!res.ok) throw new Error(`Upload failed: ${res.status}`)
    return res.json()
  }

  // Run via REST
  async function runPipeline(pipelineId: string, imageFilename?: string, overrides?: Record<string, any>) {
    return fetchJson('/api/run', {
      method: 'POST',
      body: JSON.stringify({
        pipeline_id: pipelineId,
        image_filename: imageFilename,
        overrides,
      }),
    })
  }

  // Run via WebSocket (live progress)
  function runPipelineWs(
    pipelineId: string,
    imageFilename?: string,
    overrides?: Record<string, any>,
    callbacks?: {
      onStepStart?: (data: any) => void
      onStepDone?: (data: any) => void
      onBatchProgress?: (data: any) => void
      onComplete?: () => void
      onError?: (msg: string) => void
    },
  ) {
    const wsBase = base.replace('http', 'ws')
    const ws = new WebSocket(`${wsBase}/api/ws/run`)

    ws.onopen = () => {
      ws.send(JSON.stringify({
        pipeline_id: pipelineId,
        image_filename: imageFilename,
        overrides,
      }))
    }

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      switch (data.event) {
        case 'step_start':
          callbacks?.onStepStart?.(data)
          break
        case 'step_done':
          callbacks?.onStepDone?.(data)
          break
        case 'batch_progress':
          callbacks?.onBatchProgress?.(data)
          break
        case 'complete':
          callbacks?.onComplete?.()
          ws.close()
          break
        case 'error':
          callbacks?.onError?.(data.message)
          ws.close()
          break
      }
    }

    ws.onerror = () => callbacks?.onError?.('WebSocket connection failed')
    return ws
  }

  // Step types
  const listStepTypes = () => fetchJson('/api/step-types')

  return {
    base,
    listPipelines,
    getPipeline,
    savePipeline,
    deletePipeline,
    getModelStatus,
    checkModels,
    listOutputs,
    outputUrl,
    uploadImage,
    runPipeline,
    runPipelineWs,
    listStepTypes,
  }
}
