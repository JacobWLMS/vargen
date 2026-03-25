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

    // ── Graph JSON (workflows) ─────────────────

    toGraph(): any {
      const graph: any = {
        name: this.pipelineName,
        description: this.pipelineDescription,
        nodes: {} as Record<string, any>,
        edges: [] as any[],
      }
      for (const node of this.nodes) {
        graph.nodes[node.id] = {
          type: node.type,
          widgets: { ...node.params },
          x: node.x,
          y: node.y,
        }
      }
      for (const edge of this.edges) {
        graph.edges.push({
          from_node: edge.from,
          from_port: edge.param,
          to_node: edge.to,
          to_port: edge.param,
        })
      }
      return graph
    },

    fromGraph(graph: any) {
      this.nodes = []
      this.edges = []
      this.pipelineName = graph.name || 'untitled'
      this.pipelineDescription = graph.description || ''

      for (const [id, nodeDef] of Object.entries(graph.nodes || {})) {
        const nd = nodeDef as any
        const node: GraphNode = {
          id,
          name: id,
          type: nd.type,
          model: nd.widgets?.checkpoint || nd.widgets?.model || nd.widgets?.lora || '',
          params: nd.widgets || {},
          x: nd.x ?? 0,
          y: nd.y ?? 0,
        }
        this.nodes.push(node)
      }

      for (const edge of (graph.edges || [])) {
        this.edges.push({
          id: `e_${edge.from_node}_${edge.to_node}_${edge.from_port}`,
          from: edge.from_node,
          to: edge.to_node,
          param: edge.from_port,
        })
      }

      this.selectedNodeId = this.nodes[0]?.id || null
    },

    async loadWorkflow(id: string) {
      try {
        const res = await fetch(`/api/workflows/${id}`)
        if (res.ok) {
          const graph = await res.json()
          this.fromGraph(graph)
          this.pipelineName = id
          this.log('info', `Loaded workflow: ${graph.name || id}`)
        }
      } catch (e: any) {
        this.log('error', `Failed to load workflow: ${e.message}`)
      }
    },

    async saveWorkflow() {
      const graph = this.toGraph()
      try {
        await fetch(`/api/workflows/${this.pipelineName}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(graph),
        })
        this.log('info', `Saved workflow: ${this.pipelineName}`)
      } catch (e: any) {
        this.log('error', `Save failed: ${e.message}`)
      }
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
        this.log('info', `VRAM: ${this.vramFree}MB free / ${this.vramTotal}MB total`)
      }

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data)
        const nodeId = data.node_id
        switch (data.event) {
          case 'node_start':
            this.stepStatuses[nodeId] = 'running'
            this.log('info', `[${data.index + 1}/${data.total}] ${data.type}...`)
            break
          case 'node_done':
            this.stepStatuses[nodeId] = data.error ? 'error' : 'done'
            this.stepDurations[nodeId] = data.duration
            if (data.error) {
              this.log('error', `  FAILED: ${data.type}`)
              this.log('error', `  ${data.error}`)
            } else {
              this.log('info', `  done in ${data.duration.toFixed(1)}s`)
            }
            if (data.image_url) {
              this.outputs.push({ url: data.image_url, step: nodeId, timestamp: Date.now() })
              this.selectedOutputIndex = this.outputs.length - 1
              this.log('info', `  output saved`)
            }
            // Show backend logs if present
            if (data.logs) {
              for (const l of data.logs) this.log(l.level || 'info', `  ${l.message}`)
            }
            break
          case 'log':
            // Backend can send log events directly
            this.log(data.level || 'info', data.message)
            break
          case 'complete': {
            this.running = false
            const totalTime = Object.values(this.stepDurations).reduce((a, b) => a + (b as number), 0)
            const nodeCount = Object.keys(this.stepStatuses).length
            this.log('info', `Complete: ${nodeCount} nodes in ${totalTime.toFixed(1)}s`)
            ws.close()
            break
          }
          case 'cancelled':
            this.running = false
            this.log('warn', 'Cancelled by user')
            ws.close()
            break
          case 'error':
            this.running = false
            this.log('error', `Execution failed: ${data.message}`)
            ws.close()
            break
        }
      }

      ws.onerror = () => { this.running = false; this.log('error', 'WebSocket connection failed — is the server running?') }
      ws.onclose = (e) => { if (this.running) { this.running = false; this.log('error', `Server disconnected (code ${e.code}). Check terminal for details.`) } }
    },

    async cancel() {
      await fetch('/api/cancel', { method: 'POST' })
    },
  },
})
