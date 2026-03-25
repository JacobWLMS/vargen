<template>
  <div class="h-[calc(100vh-8rem)]">
    <div class="flex items-center gap-3 mb-4">
      <select
        v-model="selectedPipeline"
        @change="loadPipeline"
        class="bg-gray-900 border border-gray-700 rounded-lg px-3 py-1.5 text-sm"
      >
        <option value="">Select pipeline...</option>
        <option v-for="p in pipelines" :key="p.id" :value="p.id">{{ p.name }}</option>
      </select>
      <button
        @click="exportYaml"
        class="px-3 py-1.5 text-xs rounded-lg bg-gray-800 hover:bg-gray-700 transition-colors"
      >
        Export YAML
      </button>
      <span class="text-xs text-gray-500 ml-auto">Drag to rearrange steps. Click nodes to edit.</span>
    </div>

    <div class="h-full rounded-xl border border-gray-800 overflow-hidden bg-gray-950">
      <VueFlow
        v-model:nodes="nodes"
        v-model:edges="edges"
        :default-viewport="{ zoom: 1, x: 50, y: 50 }"
        fit-view-on-init
        class="vue-flow-dark"
      >
        <Background />
        <Controls />
        <MiniMap />

        <!-- Custom step nodes -->
        <template #node-step="{ data }">
          <div
            class="rounded-xl border-2 p-4 min-w-[240px] shadow-xl"
            :class="nodeStyle(data.stepType)"
          >
            <div class="flex items-center gap-2 mb-2">
              <div class="w-3 h-3 rounded-full" :class="nodeDotColor(data.stepType)" />
              <span class="font-semibold text-sm">{{ data.label }}</span>
              <span class="ml-auto text-[10px] px-1.5 py-0.5 rounded bg-black/20 text-gray-400">
                {{ data.stepType }}
              </span>
            </div>
            <div class="space-y-1 text-xs text-gray-400">
              <p><span class="text-gray-500">model:</span> {{ data.model }}</p>
              <p v-if="data.batchCount > 1">
                <span class="text-vargen-400 font-medium">batch: {{ data.batchCount }}x</span>
              </p>
              <p v-for="(val, key) in data.params" :key="key" class="truncate max-w-[220px]">
                <span class="text-gray-500">{{ key }}:</span> {{ typeof val === 'string' && val.length > 30 ? val.slice(0, 30) + '...' : val }}
              </p>
            </div>
          </div>
        </template>
      </VueFlow>
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

onMounted(async () => {
  pipelines.value = await api.listPipelines()
})

async function loadPipeline() {
  if (!selectedPipeline.value) return
  const data = await api.getPipeline(selectedPipeline.value)
  parsePipelineToFlow(data.yaml)
}

function parsePipelineToFlow(yamlText: string) {
  // Simple YAML parsing for step visualization
  // In production, use the backend to parse and return structured data
  const lines = yamlText.split('\n')
  const stepNodes: any[] = []
  const stepEdges: any[] = []

  let currentStep: any = null
  let stepIndex = 0
  let inSteps = false
  let inModels = false

  for (const line of lines) {
    if (line.trim() === 'steps:') { inSteps = true; inModels = false; continue }
    if (line.trim() === 'models:') { inModels = true; inSteps = false; continue }

    if (inSteps && line.match(/^\s{2}- name:\s*(.+)/)) {
      if (currentStep) stepNodes.push(currentStep)
      const name = line.match(/name:\s*(.+)/)![1].trim()
      currentStep = {
        id: `step-${stepIndex}`,
        type: 'step',
        position: { x: 100 + (stepIndex % 3) * 320, y: 50 + Math.floor(stepIndex / 3) * 250 },
        data: { label: name, stepType: '', model: '', params: {}, batchCount: 1 },
      }
      stepIndex++
    } else if (inSteps && currentStep) {
      const typeMatch = line.match(/^\s{4}type:\s*(.+)/)
      const modelMatch = line.match(/^\s{4}model:\s*(.+)/)
      const batchMatch = line.match(/^\s{4}batch_count:\s*(\d+)/)
      const paramMatch = line.match(/^\s{4}(\w+):\s*(.+)/)

      if (typeMatch) currentStep.data.stepType = typeMatch[1].trim()
      else if (modelMatch) currentStep.data.model = modelMatch[1].trim()
      else if (batchMatch) currentStep.data.batchCount = parseInt(batchMatch[1])
      else if (paramMatch && !['name', 'type', 'model', 'batch_count', 'ip_adapter', 'controlnet', 'loras'].includes(paramMatch[1])) {
        currentStep.data.params[paramMatch[1]] = paramMatch[2].trim()
      }
    }
  }
  if (currentStep) stepNodes.push(currentStep)

  // Create edges between consecutive steps
  for (let i = 0; i < stepNodes.length - 1; i++) {
    stepEdges.push({
      id: `e-${i}`,
      source: stepNodes[i].id,
      target: stepNodes[i + 1].id,
      animated: true,
      style: { stroke: '#f19333' },
    })
  }

  nodes.value = stepNodes
  edges.value = stepEdges
}

function nodeStyle(stepType: string) {
  const styles: Record<string, string> = {
    'vision-llm': 'border-teal-500/50 bg-teal-950/30',
    'txt2img': 'border-vargen-500/50 bg-vargen-950/30',
    'img2img': 'border-purple-500/50 bg-purple-950/30',
    'refine': 'border-purple-500/50 bg-purple-950/30',
    'pixel-upscale': 'border-blue-500/50 bg-blue-950/30',
  }
  return styles[stepType] || 'border-gray-600/50 bg-gray-900/30'
}

function nodeDotColor(stepType: string) {
  const colors: Record<string, string> = {
    'vision-llm': 'bg-teal-400',
    'txt2img': 'bg-vargen-400',
    'img2img': 'bg-purple-400',
    'refine': 'bg-purple-400',
    'pixel-upscale': 'bg-blue-400',
  }
  return colors[stepType] || 'bg-gray-400'
}

function exportYaml() {
  // TODO: convert flow back to YAML
  alert('Export coming soon — edit in Pipeline Editor tab for now')
}
</script>

<style>
.vue-flow-dark .vue-flow__background {
  background-color: #0a0a0a;
}
.vue-flow-dark .vue-flow__minimap {
  background-color: #111;
}
.vue-flow-dark .vue-flow__controls {
  background: #1a1a1a;
  border: 1px solid #333;
}
.vue-flow-dark .vue-flow__controls button {
  background: #1a1a1a;
  color: #999;
  border-bottom: 1px solid #333;
}
.vue-flow-dark .vue-flow__controls button:hover {
  background: #222;
}
</style>
