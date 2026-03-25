<template>
  <div
    ref="viewport"
    class="relative overflow-hidden cursor-grab"
    :class="{ 'cursor-grabbing': isPanning }"
    style="background: var(--bg-primary)"
    @mousedown.middle="startPan"
    @mousedown.left="onCanvasMouseDown"
    @mousemove="onMouseMove"
    @mouseup="onMouseUp"
    @wheel="onZoom"
    @dblclick="onDoubleClick"
    @dragover.prevent
    @drop="onDrop"
  >
    <!-- Dot grid -->
    <div class="absolute inset-0 pointer-events-none canvas-grid" :style="gridStyle" />

    <!-- Transform surface -->
    <div :style="surfaceStyle">
      <!-- Edges (SVG) -->
      <svg class="absolute top-0 left-0 pointer-events-none" style="overflow: visible; width: 1px; height: 1px">
        <path
          v-for="edge in store.edges"
          :key="edge.id"
          :d="edgePath(edge)"
          fill="none"
          :stroke="edgeColor(edge)"
          :stroke-width="edgeWidth(edge)"
          :class="{ 'edge-flowing': isEdgeFlowing(edge) }"
        />
      </svg>

      <!-- Nodes -->
      <PipelineNode
        v-for="node in store.nodes"
        :key="node.id"
        :node="node"
        :selected="node.id === store.selectedNodeId"
        :status="store.stepStatuses[node.name]"
        :duration="store.stepDurations[node.name]"
        @select="store.selectedNodeId = node.id"
        @move="(dx, dy) => onNodeDrag(node.id, dx, dy)"
        @start-connect="(port, ev) => onStartConnect(node.id, port, ev)"
      />

      <!-- Connection being drawn -->
      <svg v-if="connecting" class="absolute top-0 left-0 pointer-events-none" style="overflow: visible; width: 1px; height: 1px">
        <path :d="connectingPath" fill="none" stroke="var(--accent)" stroke-width="2" opacity="0.6" stroke-dasharray="6 3" />
      </svg>
    </div>

    <!-- Empty state -->
    <div v-if="!store.nodes.length" class="absolute inset-0 flex items-center justify-center pointer-events-none">
      <div class="text-center">
        <p class="text-[14px]" style="color: var(--text-muted)">Double-click to add a step</p>
        <p class="text-[11px] mt-1" style="color: var(--text-muted)">or drag from the asset panel</p>
      </div>
    </div>

    <!-- Quick-add menu -->
    <div
      v-if="quickAdd.open"
      class="absolute z-50 py-1 rounded"
      :style="{ left: quickAdd.x + 'px', top: quickAdd.y + 'px', background: 'var(--bg-panel)', border: '1px solid var(--border)', minWidth: '180px' }"
    >
      <div
        v-for="st in quickAddTypes"
        :key="st.type"
        @click="addNodeAtQuickAdd(st.type)"
        class="px-3 py-1.5 flex items-center gap-2 cursor-pointer text-[12px]"
        style="color: var(--text-secondary)"
        @mouseenter="($event.target as HTMLElement).style.background = 'var(--bg-hover)'"
        @mouseleave="($event.target as HTMLElement).style.background = 'transparent'"
      >
        <span class="w-2 h-2 rounded-full" :style="{ background: st.color }" />
        {{ st.type }}
      </div>
    </div>

    <!-- Zoom indicator -->
    <div class="absolute bottom-2 left-2 text-[10px] mono" style="color: var(--text-muted)">
      {{ Math.round(store.zoom * 100) }}%
    </div>
  </div>
</template>

<script setup lang="ts">
import { useWorkspaceStore, type GraphEdge } from '~/stores/workspace'

const store = useWorkspaceStore()
const viewport = ref<HTMLElement>()

// Pan state
const isPanning = ref(false)
const panStart = { x: 0, y: 0 }

// Connection drawing state
const connecting = ref(false)
const connectFrom = ref('')
const connectFromPort = ref('')
const connectMouse = reactive({ x: 0, y: 0 })

// Quick-add menu
const quickAdd = reactive({ open: false, x: 0, y: 0, canvasX: 0, canvasY: 0 })

const quickAddTypes = computed(() => {
  return Object.values(store.nodeTypes).map((nt: any) => ({
    type: nt.type_id,
    label: nt.label,
    color: nt.color,
  }))
})

const surfaceStyle = computed(() => ({
  transform: `translate(${store.pan.x}px, ${store.pan.y}px) scale(${store.zoom})`,
  transformOrigin: '0 0',
  position: 'absolute' as const,
  top: '0', left: '0',
  width: '1px', height: '1px',
}))

const gridStyle = computed(() => {
  const size = 20 * store.zoom
  const ox = store.pan.x % size
  const oy = store.pan.y % size
  return {
    backgroundImage: `radial-gradient(circle, #111 ${store.zoom > 0.5 ? '1px' : '0.5px'}, transparent 1px)`,
    backgroundSize: `${size}px ${size}px`,
    backgroundPosition: `${ox}px ${oy}px`,
  }
})

function startPan(e: MouseEvent) {
  isPanning.value = true
  panStart.x = e.clientX - store.pan.x
  panStart.y = e.clientY - store.pan.y
}

function onCanvasMouseDown(e: MouseEvent) {
  if (e.target === viewport.value || (e.target as HTMLElement).classList.contains('canvas-grid')) {
    // Click on empty canvas — deselect and start pan
    store.selectedNodeId = null
    quickAdd.open = false
    if (e.shiftKey || e.button === 0) {
      isPanning.value = true
      panStart.x = e.clientX - store.pan.x
      panStart.y = e.clientY - store.pan.y
    }
  }
}

function onMouseMove(e: MouseEvent) {
  if (isPanning.value) {
    store.pan.x = e.clientX - panStart.x
    store.pan.y = e.clientY - panStart.y
  }
  if (connecting.value) {
    const rect = viewport.value!.getBoundingClientRect()
    connectMouse.x = (e.clientX - rect.left - store.pan.x) / store.zoom
    connectMouse.y = (e.clientY - rect.top - store.pan.y) / store.zoom
  }
}

function onMouseUp(e: MouseEvent) {
  isPanning.value = false
  if (connecting.value) {
    connecting.value = false

    // Find if mouse is over a node's input port area (left side of a node)
    const rect = viewport.value!.getBoundingClientRect()
    const canvasX = (e.clientX - rect.left - store.pan.x) / store.zoom
    const canvasY = (e.clientY - rect.top - store.pan.y) / store.zoom

    for (const node of store.nodes) {
      if (node.id === connectFrom.value) continue // can't connect to self

      // Check if cursor is near the left side of this node (input port area)
      const nodeLeft = node.x
      const nodeTop = node.y
      const nodeHeight = 100 // approximate
      const portZone = 30

      if (canvasX >= nodeLeft - portZone && canvasX <= nodeLeft + portZone &&
          canvasY >= nodeTop && canvasY <= nodeTop + nodeHeight + 60) {
        // Find a compatible input port
        const targetDef = store.nodeTypes[node.type]
        const sourceDef = store.nodeTypes[store.nodeById(connectFrom.value)?.type || '']
        const sourceOutput = sourceDef?.outputs?.find((p: any) => p.name === connectFromPort.value)

        if (targetDef?.inputs && sourceOutput) {
          const targetPort = targetDef.inputs.find((p: any) => p.type === sourceOutput.type)
          if (targetPort) {
            store.addEdge(connectFrom.value, node.id, sourceOutput.name)
            store.log('info', `Connected: ${connectFrom.value}.${sourceOutput.name} → ${node.id}.${targetPort.name}`)
            return
          }
        }
        // If no type match, connect anyway with the port name
        store.addEdge(connectFrom.value, node.id, connectFromPort.value)
        store.log('info', `Connected: ${connectFrom.value} → ${node.id}`)
        return
      }
    }
  }
}

function onZoom(e: WheelEvent) {
  e.preventDefault()
  const delta = e.deltaY > 0 ? 0.9 : 1.1
  const newZoom = Math.min(2, Math.max(0.25, store.zoom * delta))

  // Zoom toward cursor
  const rect = viewport.value!.getBoundingClientRect()
  const cx = e.clientX - rect.left
  const cy = e.clientY - rect.top
  store.pan.x = cx - (cx - store.pan.x) * (newZoom / store.zoom)
  store.pan.y = cy - (cy - store.pan.y) * (newZoom / store.zoom)
  store.zoom = newZoom
}

function onDoubleClick(e: MouseEvent) {
  const rect = viewport.value!.getBoundingClientRect()
  quickAdd.x = e.clientX - rect.left
  quickAdd.y = e.clientY - rect.top
  quickAdd.canvasX = (quickAdd.x - store.pan.x) / store.zoom
  quickAdd.canvasY = (quickAdd.y - store.pan.y) / store.zoom
  quickAdd.open = true
}

function addNodeAtQuickAdd(type: string) {
  const node = store.addNode(type, quickAdd.canvasX, quickAdd.canvasY)

  // Auto-connect to the last node
  if (store.nodes.length > 1) {
    const prev = store.nodes[store.nodes.length - 2]
    store.addEdge(prev.id, node.id, type === 'vision-llm' ? 'input_image' : 'input')
  }

  quickAdd.open = false
}

function onDrop(e: DragEvent) {
  const rect = viewport.value!.getBoundingClientRect()
  const x = (e.clientX - rect.left - store.pan.x) / store.zoom
  const y = (e.clientY - rect.top - store.pan.y) / store.zoom

  // Handle node type drop
  const nodeType = e.dataTransfer?.getData('vargen/node-type')
  if (nodeType) {
    store.addNode(nodeType, x, y)
    return
  }

  // Handle model drop — create appropriate loader node
  const modelData = e.dataTransfer?.getData('vargen/model')
  if (modelData) {
    const model = JSON.parse(modelData)
    const loaderMap: Record<string, string> = {
      checkpoints: 'load_checkpoint', diffusion_models: 'load_checkpoint',
      upscale_models: 'load_upscale_model', loras: 'load_lora',
    }
    const nodeType = loaderMap[model.category] || 'load_checkpoint'
    const node = store.addNode(nodeType, x, y)
    // Set the model widget
    const widgetKey = { load_checkpoint: 'checkpoint', load_lora: 'lora', load_upscale_model: 'model' }[nodeType] || 'checkpoint'
    node.params[widgetKey] = model.name
    return
  }

  // Handle image drop
  const files = e.dataTransfer?.files
  if (files?.length) {
    const file = files[0]
    if (file.type.startsWith('image/')) {
      uploadImage(file)
    }
  }
}

async function uploadImage(file: File) {
  const form = new FormData()
  form.append('file', file)
  try {
    const res = await fetch('/api/upload', { method: 'POST', body: form })
    if (res.ok) {
      const data = await res.json()
      store.inputImage = { filename: data.filename, previewUrl: URL.createObjectURL(file) }
    }
  } catch {}
}

function onNodeDrag(id: string, dx: number, dy: number) {
  const node = store.nodeById(id)
  if (node) {
    node.x += dx / store.zoom
    node.y += dy / store.zoom
  }
}

function onStartConnect(nodeId: string, portName: string, e: MouseEvent) {
  connecting.value = true
  connectFrom.value = nodeId
  connectFromPort.value = portName
  const node = store.nodeById(nodeId)!
  connectMouse.x = node.x + 220
  connectMouse.y = node.y + 40
}

// Edge rendering
function edgePath(edge: GraphEdge): string {
  const from = store.nodeById(edge.from)
  const to = store.nodeById(edge.to)
  if (!from || !to) return ''

  const x1 = from.x + 220 // right side of node
  const y1 = from.y + 50  // vertical center (approx)
  const x2 = to.x          // left side of node
  const y2 = to.y + 50
  const cpx = Math.max(Math.abs(x2 - x1) * 0.4, 50)
  return `M ${x1} ${y1} C ${x1 + cpx} ${y1}, ${x2 - cpx} ${y2}, ${x2} ${y2}`
}

const connectingPath = computed(() => {
  const from = store.nodeById(connectFrom.value)
  if (!from) return ''
  const x1 = from.x + 220
  const y1 = from.y + 50
  const cpx = Math.max(Math.abs(connectMouse.x - x1) * 0.4, 50)
  return `M ${x1} ${y1} C ${x1 + cpx} ${y1}, ${connectMouse.x - cpx} ${connectMouse.y}, ${connectMouse.x} ${connectMouse.y}`
})

function edgeColor(edge: GraphEdge): string {
  if (isEdgeFlowing(edge)) return 'var(--accent)'
  return '#1a1a1a'
}

function edgeWidth(edge: GraphEdge): number {
  return isEdgeFlowing(edge) ? 2 : 1.5
}

function isEdgeFlowing(edge: GraphEdge): boolean {
  const from = store.nodeById(edge.from)
  const to = store.nodeById(edge.to)
  if (!from || !to) return false
  return store.stepStatuses[from.name] === 'done' && store.stepStatuses[to.name] === 'running'
}
</script>

<style>
@keyframes edge-flow { to { stroke-dashoffset: -20; } }
.edge-flowing { stroke-dasharray: 8 4; animation: edge-flow 0.5s linear infinite; }
</style>
