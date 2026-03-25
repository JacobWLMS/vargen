import { defineStore } from 'pinia'

export interface GraphNode {
  id: string
  name: string
  type: string
  model: string
  params: Record<string, any>
  x: number
  y: number
}

export interface GraphEdge {
  id: string
  from: string
  to: string
  param: string // which param this connection feeds
}

export interface OutputImage {
  url: string
  step: string
  timestamp: number
}

export const useWorkspaceStore = defineStore('workspace', {
  state: () => ({
    // Graph
    nodes: [] as GraphNode[],
    edges: [] as GraphEdge[],
    pipelineName: 'untitled',
    pipelineDescription: '',

    // Canvas
    pan: { x: 0, y: 0 },
    zoom: 1,
    selectedNodeId: null as string | null,

    // Input
    inputImage: null as { filename: string; previewUrl: string } | null,

    // Execution
    running: false,
    stepStatuses: {} as Record<string, 'pending' | 'running' | 'done' | 'error'>,
    stepDurations: {} as Record<string, number>,

    // Outputs
    outputs: [] as OutputImage[],
    selectedOutputIndex: -1,

    // UI panels
    assetPanelOpen: true,
    propertiesPanelOpen: true,
    outputBarOpen: true,
    consoleOpen: true,

    // Panel sizes
    assetPanelWidth: 240,
    propertiesPanelWidth: 288,
    bottomPanelHeight: 200,
    bottomTab: 'output' as 'output' | 'console',

    // YAML panel
    yamlPanelOpen: false,
    yamlPanelWidth: 400,

    // Node type definitions (from API)
    nodeTypes: {} as Record<string, any>,

    // Console
    consoleLogs: [] as { time: string; level: string; message: string }[],

    // Models
    modelInventory: {} as Record<string, any[]>,

    // VRAM
    vramTotal: 0,
    vramFree: 0,
  }),

  getters: {
    selectedNode: (state) => state.nodes.find(n => n.id === state.selectedNodeId) || null,
    nodeById: (state) => (id: string) => state.nodes.find(n => n.id === id),
    edgesFrom: (state) => (id: string) => state.edges.filter(e => e.from === id),
    edgesTo: (state) => (id: string) => state.edges.filter(e => e.to === id),
    selectedOutput: (state) => state.outputs[state.selectedOutputIndex] || null,
  },

  actions: {
    // ── Nodes ────────────────────────────────

    addNode(type: string, x: number, y: number): GraphNode {
      const id = `node_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`
      const defaults: Record<string, Record<string, any>> = {
        'vision-llm': { prompt: 'Describe this image in detail', prepend: '', append: '', max_tokens: 512 },
        'txt2img': { prompt: '', negative: '', width: 1024, height: 1024, steps: 20, guidance: 3.5, seed: -1, batch_count: 1 },
        'img2img': { prompt: '', negative: '', steps: 5, denoise: 0.5, guidance: 1.0 },
        'refine': { prompt: '', steps: 5, denoise: 0.5, guidance: 1.0 },
        'pixel-upscale': { scale: 2 },
      }
      const node: GraphNode = { id, name: type.replace('-', '_'), type, model: '', params: defaults[type] || {}, x, y }
      this.nodes.push(node)
      this.selectedNodeId = id
      return node
    },

    removeNode(id: string) {
      this.nodes = this.nodes.filter(n => n.id !== id)
      this.edges = this.edges.filter(e => e.from !== id && e.to !== id)
      if (this.selectedNodeId === id) this.selectedNodeId = null
    },

    moveNode(id: string, x: number, y: number) {
      const node = this.nodes.find(n => n.id === id)
      if (node) { node.x = x; node.y = y }
    },

    // ── Edges ────────────────────────────────

    addEdge(from: string, to: string, param: string = 'input') {
      const id = `edge_${from}_${to}`
      if (!this.edges.find(e => e.id === id)) {
        this.edges.push({ id, from, to, param })
      }
    },

    removeEdge(id: string) {
      this.edges = this.edges.filter(e => e.id !== id)
    },

    // ── YAML ─────────────────────────────────

    toYaml(): string {
      let yaml = `name: "${this.pipelineName}"\ndescription: "${this.pipelineDescription}"\nversion: 1\n\nmodels: {}\n\nsteps:\n`
      // Topological sort by edges (simple: use node order for now)
      for (const node of this.nodes) {
        yaml += `  - name: ${node.name}\n    type: ${node.type}\n    model: ${node.model}\n`
        // Find incoming edges to set {ref} params
        const incoming = this.edges.filter(e => e.to === node.id)
        for (const edge of incoming) {
          const sourceNode = this.nodes.find(n => n.id === edge.from)
          if (sourceNode) {
            yaml += `    ${edge.param}: "{${sourceNode.name}}"\n`
          }
        }
        for (const [k, v] of Object.entries(node.params)) {
          if (v === '' || v === null || v === undefined) continue
          if (k === 'batch_count' && v === 1) continue
          // Skip params that are set by edges
          if (incoming.some(e => e.param === k)) continue
          yaml += `    ${k}: ${typeof v === 'string' && v.includes(' ') ? `"${v}"` : v}\n`
        }
      }
      return yaml
    },

    fromYaml(yamlText: string) {
      this.nodes = []
      this.edges = []

      const lines = yamlText.split('\n')
      let current: any = null
      let inSteps = false
      let idx = 0
      const nodeMap: Record<string, string> = {} // name -> id

      // Parse metadata
      for (const line of lines) {
        const nameMatch = line.match(/^name:\s*["']?(.+?)["']?\s*$/)
        const descMatch = line.match(/^description:\s*["']?(.+?)["']?\s*$/)
        if (nameMatch) this.pipelineName = nameMatch[1]
        if (descMatch) this.pipelineDescription = descMatch[1]
      }

      // Parse steps
      for (const line of lines) {
        if (line.trim() === 'steps:') { inSteps = true; continue }
        if (line.match(/^[a-z]/) && line.includes(':') && inSteps && !line.startsWith(' ')) { inSteps = false; continue }

        if (inSteps && line.match(/^\s{2}- name:\s*(.+)/)) {
          if (current) {
            const node = this.addNode(current.type || 'txt2img', 100 + idx * 240, 200)
            node.name = current.name
            node.model = current.model || ''
            node.params = { ...node.params, ...current.params }
            nodeMap[current.name] = node.id
            idx++
          }
          const name = line.match(/name:\s*(.+)/)![1].trim().replace(/['"]/g, '')
          current = { name, type: '', model: '', params: {} }
        } else if (inSteps && current) {
          const m = line.match(/^\s{4}(\w+):\s*(.+)/)
          if (m) {
            const [_, key, rawVal] = m
            const val = rawVal.trim().replace(/^["']|["']$/g, '')
            if (key === 'type') current.type = val
            else if (key === 'model') current.model = val
            else if (key === 'batch_count') current.params.batch_count = parseInt(val)
            else if (!['name', 'ip_adapter', 'controlnet', 'loras'].includes(key)) {
              // Check for {ref} pattern
              const refMatch = val.match(/^\{(.+)\}$/)
              if (refMatch) {
                // Will create edge after all nodes are parsed
                current.params[`_ref_${key}`] = refMatch[1]
              } else {
                current.params[key] = isNaN(Number(val)) ? val : Number(val)
              }
            }
          }
        }
      }
      // Last node
      if (current) {
        const node = this.addNode(current.type || 'txt2img', 100 + idx * 240, 200)
        node.name = current.name
        node.model = current.model || ''
        node.params = { ...node.params, ...current.params }
        nodeMap[current.name] = node.id
      }

      // Create edges from {ref} params
      for (const node of this.nodes) {
        const refKeys = Object.keys(node.params).filter(k => k.startsWith('_ref_'))
        for (const refKey of refKeys) {
          const param = refKey.replace('_ref_', '')
          const sourceName = node.params[refKey]
          const sourceId = nodeMap[sourceName]
          if (sourceId) {
            this.addEdge(sourceId, node.id, param)
          }
          delete node.params[refKey]
        }
      }

      this.selectedNodeId = this.nodes[0]?.id || null
    },

    // ── Models ───────────────────────────────

    async loadModels() {
      try {
        const res = await fetch('/api/models/browse')
        if (res.ok) this.modelInventory = await res.json()
      } catch {}
    },

    async loadNodeTypes() {
      try {
        const res = await fetch('/api/node-types')
        if (res.ok) this.nodeTypes = await res.json()
      } catch {}
    },

    async loadVram() {
      try {
        const res = await fetch('/api/models/status')
        if (res.ok) {
          const data = await res.json()
          this.vramTotal = data.vram_total_mb || 0
          this.vramFree = data.vram_free_mb || 0
        }
      } catch {}
    },

    log(level: string, message: string) {
      const now = new Date()
      const time = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`
      this.consoleLogs.push({ time, level, message })
      if (this.consoleLogs.length > 500) this.consoleLogs.shift()
    },

    // ── Execution ────────────────────────────

    async runGraph() {
      if (this.running) return
      this.running = true
      this.outputs = []
      this.stepStatuses = {}
      this.stepDurations = {}
      this.log('info', `Executing graph: ${this.nodes.length} nodes`)

      // Build graph payload for the executor
      const graph: any = { nodes: {}, edges: [] }
      for (const node of this.nodes) {
        graph.nodes[node.id] = {
          type: node.type,
          widgets: { ...node.params },
        }
      }
      for (const edge of this.edges) {
        graph.edges.push({
          from_node: edge.from,
          from_port: edge.param, // port name on source
          to_node: edge.to,
          to_port: edge.param,   // port name on target
        })
      }

      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      const ws = new WebSocket(`${proto}://${location.host}/api/ws/graph`)

      ws.onopen = () => {
        ws.send(JSON.stringify({ graph, image_filename: this.inputImage?.filename }))
        this.log('info', 'Connected to graph executor')
      }

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data)
        const nodeId = data.node_id
        switch (data.event) {
          case 'node_start':
            this.stepStatuses[nodeId] = 'running'
            this.log('info', `[${data.index + 1}/${data.total}] Running: ${data.type}`)
            break
          case 'node_done':
            this.stepStatuses[nodeId] = data.error ? 'error' : 'done'
            this.stepDurations[nodeId] = data.duration
            if (data.error) this.log('error', `  ${data.type}: ${data.error}`)
            else this.log('info', `  ${data.type}: ${data.duration.toFixed(1)}s`)
            if (data.image_url) {
              this.outputs.push({ url: data.image_url, step: nodeId, timestamp: Date.now() })
              this.selectedOutputIndex = this.outputs.length - 1
            }
            break
          case 'complete':
            this.running = false
            this.log('info', 'Graph execution complete')
            ws.close()
            break
          case 'cancelled':
            this.running = false
            this.log('warn', 'Cancelled')
            ws.close()
            break
          case 'error':
            this.running = false
            this.log('error', data.message)
            ws.close()
            break
        }
      }

      ws.onerror = () => { this.running = false; this.log('error', 'WebSocket failed') }
      ws.onclose = (e) => { if (this.running) { this.running = false; this.log('error', `Connection lost (${e.code})`) } }
    },

    async run() {
      if (this.running) return
      this.running = true
      this.outputs = []
      this.stepStatuses = {}
      this.stepDurations = {}

      const yaml = this.toYaml()
      this.log('info', `Starting pipeline: ${this.pipelineName}`)
      this.log('info', `${this.nodes.length} steps, input: ${this.inputImage?.filename || 'none'}`)

      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      const ws = new WebSocket(`${proto}://${location.host}/api/ws/run`)

      ws.onopen = () => {
        ws.send(JSON.stringify({
          pipeline_yaml: yaml,
          image_filename: this.inputImage?.filename,
        }))
        this.log('info', 'Connected to engine')
      }

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data)
        switch (data.event) {
          case 'step_start':
            this.stepStatuses[data.step] = 'running'
            this.log('info', `Running: ${data.step} (${data.index + 1}/${data.total})`)
            break
          case 'step_done':
            this.stepStatuses[data.step] = 'done'
            this.stepDurations[data.step] = data.duration
            this.log('info', `Done: ${data.step} (${data.duration.toFixed(1)}s)`)
            if (data.url) this.outputs.push({ url: data.url, step: data.step, timestamp: Date.now() })
            if (data.urls) {
              this.log('info', `  ${data.urls.length} images generated`)
              for (const url of data.urls) {
                this.outputs.push({ url, step: data.step, timestamp: Date.now() })
              }
            }
            if (data.text) this.log('info', `  Caption: ${data.text.slice(0, 200)}`)
            if (this.outputs.length) this.selectedOutputIndex = this.outputs.length - 1
            break
          case 'batch_progress':
            this.log('info', `  Batch: ${data.index + 1}/${data.total}`)
            break
          case 'complete':
            this.running = false
            this.log('info', 'Pipeline complete')
            ws.close()
            break
          case 'cancelled':
            this.running = false
            this.log('warn', 'Pipeline cancelled')
            ws.close()
            break
          case 'error':
            this.running = false
            this.log('error', `Error: ${data.message}`)
            ws.close()
            break
        }
      }

      ws.onerror = () => {
        this.running = false
        this.log('error', 'WebSocket connection failed')
      }

      ws.onclose = (event) => {
        if (this.running) {
          this.running = false
          this.log('error', `Connection closed unexpectedly (code: ${event.code})`)
        }
      }
    },

    async cancel() {
      await fetch('/api/cancel', { method: 'POST' })
    },
  },
})
