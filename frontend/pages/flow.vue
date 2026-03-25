<template>
  <div class="h-full flex">
    <!-- Canvas -->
    <div class="flex-1 flex flex-col overflow-hidden">
      <!-- Toolbar -->
      <div class="h-9 flex items-center gap-2 px-3 shrink-0" style="border-bottom: 1px solid var(--border)">
        <select
          v-model="selectedPipeline"
          @change="loadPipeline"
          class="px-2 py-1 text-[12px] w-48"
        >
          <option value="">Load pipeline...</option>
          <option v-for="p in pipelines" :key="p.id" :value="p.id">{{ p.name }}</option>
        </select>
        <button @click="addStep" class="btn btn-ghost">+ Add Step</button>
        <div class="ml-auto flex gap-1.5">
          <button @click="exportAndSave" class="btn btn-primary">Save as YAML</button>
        </div>
      </div>

      <!-- Vue Flow -->
      <div class="flex-1 overflow-hidden" style="background: var(--bg-primary)">
        <VueFlow
          v-model:nodes="nodes"
          v-model:edges="edges"
          :default-viewport="{ zoom: 1, x: 50, y: 50 }"
          fit-view-on-init
          @node-click="onNodeClick"
        >
          <Background :gap="20" :size="0.5" />
          <Controls position="bottom-left" />
          <MiniMap />

          <template #node-step="{ data }">
            <div class="flow-node" :style="nodeStyle(data.stepType)">
              <div class="flex items-center gap-2 mb-1.5">
                <div class="w-2 h-2 rounded-full shrink-0" :style="{ background: nodeDotColor(data.stepType) }" />
                <span class="text-[12px] font-medium" style="color: var(--text-primary)">{{ data.label }}</span>
                <span class="ml-auto text-[10px] px-1 py-0.5 rounded mono" style="background: var(--bg-active); color: var(--text-muted)">
                  {{ data.stepType }}
                </span>
              </div>
              <div class="space-y-0.5 text-[11px]" style="color: var(--text-secondary)">
                <p><span style="color: var(--text-muted)">model:</span> {{ data.model }}</p>
                <p v-if="data.batchCount > 1" style="color: var(--accent)">batch: {{ data.batchCount }}x</p>
                <p v-for="(val, key) in displayParams(data.params)" :key="key" class="truncate max-w-[200px]">
                  <span style="color: var(--text-muted)">{{ key }}:</span> {{ val }}
                </p>
              </div>
            </div>
          </template>
        </VueFlow>
      </div>
    </div>

    <!-- Right panel: node editor -->
    <div v-if="editingNode" class="w-72 shrink-0 overflow-y-auto" style="border-left: 1px solid var(--border); background: var(--bg-panel)">
      <div class="panel-header flex items-center">
        <span>Edit Step</span>
        <button @click="deleteNode" class="btn btn-danger ml-auto text-[10px]">Delete</button>
      </div>
      <div class="p-3 space-y-3 text-[12px]">
        <div>
          <label style="color: var(--text-muted)">Name</label>
          <input v-model="editingNode.data.label" class="w-full px-2 py-1 mt-1" @input="syncNode" />
        </div>
        <div>
          <label style="color: var(--text-muted)">Type</label>
          <select v-model="editingNode.data.stepType" class="w-full px-2 py-1 mt-1" @change="syncNode">
            <option value="vision-llm">vision-llm</option>
            <option value="txt2img">txt2img</option>
            <option value="img2img">img2img</option>
            <option value="refine">refine</option>
            <option value="pixel-upscale">pixel-upscale</option>
          </select>
        </div>
        <div>
          <label style="color: var(--text-muted)">Model key</label>
          <input v-model="editingNode.data.model" class="w-full px-2 py-1 mt-1" @input="syncNode" />
        </div>
        <div>
          <label style="color: var(--text-muted)">Batch count</label>
          <input v-model.number="editingNode.data.batchCount" type="number" min="1" class="w-full px-2 py-1 mt-1" @input="syncNode" />
        </div>
        <div>
          <label style="color: var(--text-muted)">Parameters (YAML)</label>
          <textarea
            v-model="editParamsText"
            class="w-full px-2 py-1 mt-1 mono text-[11px]"
            style="min-height: 160px; resize: vertical"
            @input="syncParams"
          />
        </div>
      </div>
    </div>
    <div v-else class="w-72 shrink-0 flex items-center justify-center" style="border-left: 1px solid var(--border); background: var(--bg-panel)">
      <p class="text-[11px]" style="color: var(--text-muted)">Click a node to edit</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { VueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'

const api = useApi()
const pipelines = ref<any[]>([])
const selectedPipeline = ref('')
const nodes = ref<any[]>([])
const edges = ref<any[]>([])
const editingNode = ref<any>(null)
const editParamsText = ref('')
let stepCounter = 0

onMounted(async () => {
  try { pipelines.value = await api.listPipelines() } catch {}
})

async function loadPipeline() {
  if (!selectedPipeline.value) return
  const data = await api.getPipeline(selectedPipeline.value)
  parsePipelineToFlow(data.yaml)
  editingNode.value = null
}

function addStep() {
  const id = `step-${stepCounter++}`
  const y = nodes.value.length ? Math.max(...nodes.value.map(n => n.position.y)) + 180 : 50
  const newNode = {
    id,
    type: 'step',
    position: { x: 100, y },
    data: { label: 'new_step', stepType: 'txt2img', model: 'flux-dev', params: {}, batchCount: 1 },
  }
  nodes.value.push(newNode)

  // Auto-connect to previous node
  if (nodes.value.length > 1) {
    const prev = nodes.value[nodes.value.length - 2]
    edges.value.push({
      id: `e-${prev.id}-${id}`,
      source: prev.id,
      target: id,
      animated: true,
      style: { stroke: 'var(--accent)' },
    })
  }
}

function onNodeClick({ node }: any) {
  editingNode.value = node
  editParamsText.value = Object.entries(node.data.params || {})
    .map(([k, v]) => `${k}: ${v}`)
    .join('\n')
}

function deleteNode() {
  if (!editingNode.value) return
  const id = editingNode.value.id
  nodes.value = nodes.value.filter(n => n.id !== id)
  edges.value = edges.value.filter(e => e.source !== id && e.target !== id)
  editingNode.value = null
}

function syncNode() {
  // Vue Flow reactivity handles this through v-model
}

function syncParams() {
  if (!editingNode.value) return
  const params: Record<string, string> = {}
  for (const line of editParamsText.value.split('\n')) {
    const idx = line.indexOf(':')
    if (idx > 0) {
      const key = line.slice(0, idx).trim()
      const val = line.slice(idx + 1).trim()
      if (key) params[key] = val
    }
  }
  editingNode.value.data.params = params
}

async function exportAndSave() {
  const name = prompt('Pipeline name (filename):', selectedPipeline.value || 'new_pipeline')
  if (!name) return

  // Build YAML from flow
  const stepsYaml = nodes.value.map(n => {
    const d = n.data
    let yaml = `  - name: ${d.label}\n    type: ${d.stepType}\n    model: ${d.model}\n`
    if (d.batchCount > 1) yaml += `    batch_count: ${d.batchCount}\n`
    for (const [k, v] of Object.entries(d.params || {})) {
      yaml += `    ${k}: ${v}\n`
    }
    return yaml
  }).join('\n')

  const yaml = `name: "${name}"\ndescription: "Created in flow editor"\nversion: 1\n\nmodels: {}\n\nsteps:\n${stepsYaml}`

  try {
    await api.savePipeline(name, yaml)
    alert(`Saved as ${name}.yaml`)
    pipelines.value = await api.listPipelines()
  } catch (e: any) {
    alert(`Error: ${e.message}`)
  }
}

function parsePipelineToFlow(yamlText: string) {
  const stepNodes: any[] = []
  const stepEdges: any[] = []
  let currentStep: any = null
  let stepIndex = 0
  let inSteps = false

  for (const line of yamlText.split('\n')) {
    if (line.trim() === 'steps:') { inSteps = true; continue }
    if (line.match(/^[a-z]/) && inSteps) { inSteps = false; continue }

    if (inSteps && line.match(/^\s{2}- name:\s*(.+)/)) {
      if (currentStep) stepNodes.push(currentStep)
      const name = line.match(/name:\s*(.+)/)![1].trim().replace(/"/g, '')
      currentStep = {
        id: `step-${stepIndex}`,
        type: 'step',
        position: { x: 100, y: 50 + stepIndex * 180 },
        data: { label: name, stepType: '', model: '', params: {}, batchCount: 1 },
      }
      stepIndex++
      stepCounter = Math.max(stepCounter, stepIndex)
    } else if (inSteps && currentStep) {
      const typeMatch = line.match(/^\s{4}type:\s*(.+)/)
      const modelMatch = line.match(/^\s{4}model:\s*(.+)/)
      const batchMatch = line.match(/^\s{4}batch_count:\s*(\d+)/)
      const paramMatch = line.match(/^\s{4}(\w+):\s*(.+)/)
      if (typeMatch) currentStep.data.stepType = typeMatch[1].trim().replace(/"/g, '')
      else if (modelMatch) currentStep.data.model = modelMatch[1].trim().replace(/"/g, '')
      else if (batchMatch) currentStep.data.batchCount = parseInt(batchMatch[1])
      else if (paramMatch && !['name', 'type', 'model', 'batch_count', 'ip_adapter', 'controlnet', 'loras'].includes(paramMatch[1])) {
        currentStep.data.params[paramMatch[1]] = paramMatch[2].trim().replace(/"/g, '')
      }
    }
  }
  if (currentStep) stepNodes.push(currentStep)

  for (let i = 0; i < stepNodes.length - 1; i++) {
    stepEdges.push({
      id: `e-${i}`,
      source: stepNodes[i].id,
      target: stepNodes[i + 1].id,
      animated: true,
      style: { stroke: 'var(--accent)' },
    })
  }

  nodes.value = stepNodes
  edges.value = stepEdges
}

function displayParams(params: Record<string, any>) {
  const skip = new Set(['input_image'])
  const result: Record<string, string> = {}
  for (const [k, v] of Object.entries(params || {})) {
    if (skip.has(k)) continue
    const s = String(v)
    result[k] = s.length > 30 ? s.slice(0, 30) + '...' : s
  }
  return result
}

function nodeStyle(stepType: string): Record<string, string> {
  const styles: Record<string, Record<string, string>> = {
    'vision-llm':    { borderColor: 'rgba(94, 234, 212, 0.3)', background: 'rgba(17, 44, 39, 0.5)' },
    'txt2img':       { borderColor: 'rgba(232, 138, 42, 0.3)',  background: 'rgba(50, 30, 10, 0.5)' },
    'img2img':       { borderColor: 'rgba(168, 130, 255, 0.3)', background: 'rgba(35, 20, 55, 0.5)' },
    'refine':        { borderColor: 'rgba(168, 130, 255, 0.3)', background: 'rgba(35, 20, 55, 0.5)' },
    'pixel-upscale': { borderColor: 'rgba(96, 165, 250, 0.3)',  background: 'rgba(15, 25, 50, 0.5)' },
  }
  const s = styles[stepType] || { borderColor: 'var(--border)', background: 'var(--bg-panel)' }
  return { ...s, borderRadius: '3px', border: `1px solid ${s.borderColor}`, padding: '10px 12px', minWidth: '220px' }
}

function nodeDotColor(stepType: string): string {
  const colors: Record<string, string> = {
    'vision-llm': '#5eead4', 'txt2img': '#e88a2a', 'img2img': '#a882ff',
    'refine': '#a882ff', 'pixel-upscale': '#60a5fa',
  }
  return colors[stepType] || '#444'
}
</script>

<style>
.flow-node { transition: border-color 0.15s; }
.vue-flow__background { background-color: #000 !important; }
.vue-flow__minimap { background-color: #0a0a0a !important; border: 1px solid #1a1a1a !important; border-radius: 3px !important; }
.vue-flow__controls { background: #0f0f0f !important; border: 1px solid #1a1a1a !important; border-radius: 3px !important; }
.vue-flow__controls button { background: #0f0f0f !important; color: #666 !important; border-bottom: 1px solid #1a1a1a !important; }
.vue-flow__controls button:hover { background: #1a1a1a !important; color: #ccc !important; }
.vue-flow__edge-path { stroke-width: 1.5 !important; }
</style>
