<template>
  <div class="h-full flex">
    <!-- Main: Timeline -->
    <div class="flex-1 flex flex-col overflow-hidden">
      <!-- Toolbar -->
      <div class="h-9 flex items-center gap-2 px-3 shrink-0" style="border-bottom: 1px solid var(--border)">
        <select v-model="selectedPipeline" @change="loadPipeline" class="px-2 py-1 text-[12px] w-48">
          <option value="">New pipeline</option>
          <option v-for="p in pipelines" :key="p.id" :value="p.id">{{ p.name }}</option>
        </select>
        <input v-model="pipelineName" class="px-2 py-1 text-[12px] w-40" style="background: transparent !important; border: none !important" placeholder="pipeline_name" />
        <div class="ml-auto flex gap-1.5">
          <button @click="runPipeline" :disabled="running" class="btn btn-primary">
            {{ running ? 'Running...' : 'Run' }}
          </button>
          <button v-if="running" @click="cancelRun" class="btn btn-danger">Cancel</button>
          <button @click="savePipeline" class="btn btn-ghost">Save</button>
        </div>
      </div>

      <!-- Timeline area -->
      <div class="flex-1 overflow-auto p-6" style="background: var(--bg-primary)">
        <!-- Tracks -->
        <div class="space-y-3">
          <!-- Main track -->
          <div class="flex items-center gap-1">
            <div
              v-for="(step, i) in steps"
              :key="step.id"
              class="flex items-center gap-1"
            >
              <!-- Step block -->
              <div
                @click="selectStep(i)"
                draggable="true"
                @dragstart="onDragStart(i, $event)"
                @dragover.prevent
                @drop="onDrop(i, $event)"
                class="timeline-block cursor-pointer select-none transition-all"
                :class="{ 'ring-1': selectedIndex === i }"
                :style="{
                  background: blockBg(step.type),
                  borderColor: blockBorder(step.type),
                  ringColor: selectedIndex === i ? 'var(--accent)' : 'transparent',
                }"
              >
                <div class="flex items-center gap-1.5 mb-1">
                  <div class="w-2 h-2 rounded-full" :style="{ background: blockDot(step.type) }" />
                  <span class="text-[11px] font-medium" style="color: var(--text-primary)">{{ step.name }}</span>
                </div>
                <div class="text-[10px]" style="color: var(--text-muted)">
                  {{ step.type }} · {{ step.model || '?' }}
                </div>
                <!-- Run status -->
                <div v-if="step.runStatus" class="mt-1 flex items-center gap-1">
                  <div v-if="step.runStatus === 'running'" class="w-2 h-2 border border-t-transparent rounded-full animate-spin" style="border-color: var(--accent); border-top-color: transparent" />
                  <div v-else-if="step.runStatus === 'done'" class="w-2 h-2 rounded-full" style="background: var(--success)" />
                  <span class="text-[9px]" style="color: var(--text-muted)">
                    {{ step.runStatus === 'done' ? `${step.duration?.toFixed(1)}s` : 'running' }}
                  </span>
                </div>
              </div>

              <!-- Connector arrow -->
              <div v-if="i < steps.length - 1" class="flex items-center px-0.5">
                <div class="w-8 h-px" style="background: var(--border)" />
                <div class="w-0 h-0 border-t-4 border-b-4 border-l-4" style="border-color: transparent; border-left-color: var(--border)" />
              </div>
            </div>

            <!-- Add step button -->
            <div
              @click="addStep"
              class="timeline-block cursor-pointer flex items-center justify-center"
              style="background: transparent; border-color: var(--border); border-style: dashed; min-width: 60px"
            >
              <span class="text-[16px]" style="color: var(--text-muted)">+</span>
            </div>
          </div>

          <!-- Modifier tracks (sub-tracks for IP-Adapter, ControlNet) -->
          <template v-for="(step, i) in steps" :key="'mod-' + step.id">
            <div v-if="step.params?.ip_adapter" class="flex items-center gap-1 ml-4" style="margin-top: -8px">
              <div class="w-8" />
              <div
                v-for="j in i" :key="'spacer-ipa-'+j"
                class="flex items-center gap-1"
              >
                <div style="min-width: 140px" />
                <div class="w-12" />
              </div>
              <div class="timeline-block text-[10px]" style="background: rgba(168, 130, 255, 0.1); border-color: rgba(168, 130, 255, 0.3)">
                <span style="color: #a882ff">IP-Adapter</span>
                <div class="mt-0.5" style="color: var(--text-muted)">w: {{ step.params.ip_adapter.weight }}</div>
              </div>
              <div class="text-[10px] px-1" style="color: var(--text-muted)">↗ merges into {{ step.name }}</div>
            </div>
            <div v-if="step.params?.controlnet" class="flex items-center gap-1 ml-4" style="margin-top: -8px">
              <div class="w-8" />
              <div
                v-for="j in i" :key="'spacer-cn-'+j"
                class="flex items-center gap-1"
              >
                <div style="min-width: 140px" />
                <div class="w-12" />
              </div>
              <div class="timeline-block text-[10px]" style="background: rgba(96, 165, 250, 0.1); border-color: rgba(96, 165, 250, 0.3)">
                <span style="color: #60a5fa">ControlNet</span>
                <div class="mt-0.5" style="color: var(--text-muted)">str: {{ step.params.controlnet.strength }}</div>
              </div>
              <div class="text-[10px] px-1" style="color: var(--text-muted)">↗ merges into {{ step.name }}</div>
            </div>
          </template>
        </div>

        <!-- Output preview -->
        <div v-if="outputImages.length" class="mt-8 flex gap-2 flex-wrap">
          <img
            v-for="(url, i) in outputImages"
            :key="i"
            :src="url"
            class="h-32 rounded cursor-pointer hover:opacity-80"
            style="border: 1px solid var(--border)"
            @click="selectedOutput = url"
          />
        </div>

        <!-- Large preview -->
        <div v-if="selectedOutput" class="mt-4">
          <img :src="selectedOutput" class="max-h-96 rounded" style="border: 1px solid var(--border)" />
        </div>
      </div>

      <!-- Status bar info -->
      <div v-if="statusMsg" class="px-3 py-1.5 text-[11px]" style="border-top: 1px solid var(--border); color: var(--text-secondary)">
        {{ statusMsg }}
      </div>
    </div>

    <!-- Right: Step editor sidebar -->
    <div class="w-72 shrink-0" style="border-left: 1px solid var(--border)">
      <StepSidebar
        :step="selectedStep"
        @update="onStepUpdate"
        @delete="deleteStep"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
const api = useApi()
const pipelines = ref<any[]>([])
const selectedPipeline = ref('')
const pipelineName = ref('new_pipeline')
const steps = ref<any[]>([])
const selectedIndex = ref(-1)
const running = ref(false)
const outputImages = ref<string[]>([])
const selectedOutput = ref('')
const statusMsg = ref('')
let stepIdCounter = 0
let dragIndex = -1

const selectedStep = computed(() => selectedIndex.value >= 0 ? steps.value[selectedIndex.value] : null)

onMounted(async () => {
  try { pipelines.value = await api.listPipelines() } catch {}
})

async function loadPipeline() {
  if (!selectedPipeline.value) {
    steps.value = []
    pipelineName.value = 'new_pipeline'
    return
  }
  const data = await api.getPipeline(selectedPipeline.value)
  pipelineName.value = selectedPipeline.value
  parseYamlToSteps(data.yaml)
}

function parseYamlToSteps(yamlText: string) {
  const parsed: any[] = []
  let current: any = null
  let inSteps = false

  for (const line of yamlText.split('\n')) {
    if (line.trim() === 'steps:') { inSteps = true; continue }
    if (line.match(/^[a-z]/) && line.includes(':') && inSteps) { inSteps = false; continue }

    if (inSteps && line.match(/^\s{2}- name:\s*(.+)/)) {
      if (current) parsed.push(current)
      const name = line.match(/name:\s*(.+)/)![1].trim().replace(/['"]/g, '')
      current = { id: `s${stepIdCounter++}`, name, type: '', model: '', params: {} }
    } else if (inSteps && current) {
      const m = line.match(/^\s{4}(\w+):\s*(.+)/)
      if (m) {
        const [_, key, val] = m
        const v = val.trim().replace(/['"]/g, '')
        if (key === 'type') current.type = v
        else if (key === 'model') current.model = v
        else if (key === 'batch_count') current.params.batch_count = parseInt(v)
        else if (!['name', 'ip_adapter', 'controlnet', 'loras'].includes(key)) {
          current.params[key] = isNaN(Number(v)) ? v : Number(v)
        }
      }
    }
  }
  if (current) parsed.push(current)

  // Ensure params have defaults for generation steps
  for (const s of parsed) {
    if (s.type === 'txt2img' || s.type === 'img2img') {
      s.params = {
        prompt: '', negative: '', width: 1024, height: 1024,
        steps: 20, guidance: 3.5, seed: -1, batch_count: 1,
        ...s.params,
      }
    }
    if (s.type === 'vision-llm') {
      s.params = { prompt: '', prepend: '', append: '', max_tokens: 512, ...s.params }
    }
    if (s.type === 'pixel-upscale') {
      s.params = { scale: 2, ...s.params }
    }
  }

  steps.value = parsed
  selectedIndex.value = parsed.length > 0 ? 0 : -1
}

function addStep() {
  const newStep = {
    id: `s${stepIdCounter++}`,
    name: 'new_step',
    type: 'txt2img',
    model: '',
    params: { prompt: '', negative: '', width: 1024, height: 1024, steps: 20, guidance: 3.5, seed: -1, batch_count: 1 },
  }
  steps.value.push(newStep)
  selectedIndex.value = steps.value.length - 1
}

function selectStep(i: number) { selectedIndex.value = i }

function deleteStep() {
  if (selectedIndex.value < 0) return
  steps.value.splice(selectedIndex.value, 1)
  selectedIndex.value = Math.min(selectedIndex.value, steps.value.length - 1)
}

function onStepUpdate() { /* reactivity handles it */ }

function onDragStart(i: number, e: DragEvent) {
  dragIndex = i
  e.dataTransfer!.effectAllowed = 'move'
}

function onDrop(targetIndex: number, e: DragEvent) {
  if (dragIndex < 0 || dragIndex === targetIndex) return
  const item = steps.value.splice(dragIndex, 1)[0]
  steps.value.splice(targetIndex, 0, item)
  selectedIndex.value = targetIndex
  dragIndex = -1
}

function stepsToYaml(): string {
  let yaml = `name: "${pipelineName.value}"\ndescription: "Built in timeline editor"\nversion: 1\n\nmodels: {}\n\nsteps:\n`
  for (const s of steps.value) {
    yaml += `  - name: ${s.name}\n    type: ${s.type}\n    model: ${s.model}\n`
    for (const [k, v] of Object.entries(s.params)) {
      if (v === '' || v === null || v === undefined) continue
      if (k === 'batch_count' && v === 1) continue
      if (typeof v === 'object') {
        yaml += `    ${k}:\n`
        for (const [sk, sv] of Object.entries(v as any)) {
          yaml += `      ${sk}: ${sv}\n`
        }
      } else if (typeof v === 'string' && v.includes('\n')) {
        yaml += `    ${k}: "${v.replace(/"/g, '\\"')}"\n`
      } else {
        yaml += `    ${k}: ${v}\n`
      }
    }
  }
  return yaml
}

async function savePipeline() {
  const yaml = stepsToYaml()
  try {
    await api.savePipeline(pipelineName.value, yaml)
    statusMsg.value = `Saved ${pipelineName.value}.yaml`
    pipelines.value = await api.listPipelines()
    setTimeout(() => statusMsg.value = '', 3000)
  } catch (e: any) {
    statusMsg.value = `Error: ${e.message}`
  }
}

function runPipeline() {
  const yaml = stepsToYaml()
  running.value = true
  outputImages.value = []
  selectedOutput.value = ''

  // Reset step statuses
  steps.value.forEach(s => { s.runStatus = undefined; s.duration = undefined })

  // Use WebSocket with inline YAML
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const ws = new WebSocket(`${proto}://${location.host}/api/ws/run`)

  ws.onopen = () => {
    ws.send(JSON.stringify({ pipeline_yaml: yaml }))
  }

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    const step = steps.value.find(s => s.name === data.step)

    switch (data.event) {
      case 'step_start':
        if (step) step.runStatus = 'running'
        statusMsg.value = `Running: ${data.step}`
        break
      case 'step_done':
        if (step) { step.runStatus = 'done'; step.duration = data.duration }
        if (data.url) outputImages.value.push(data.url)
        if (data.urls) data.urls.forEach((u: string) => outputImages.value.push(u))
        if (data.text) statusMsg.value = `Caption: ${data.text.slice(0, 100)}...`
        break
      case 'batch_progress':
        statusMsg.value = `${data.step}: batch ${data.index + 1}/${data.total}`
        break
      case 'complete':
        running.value = false
        statusMsg.value = 'Complete'
        break
      case 'cancelled':
        running.value = false
        statusMsg.value = 'Cancelled'
        break
      case 'error':
        running.value = false
        statusMsg.value = `Error: ${data.message}`
        break
    }
  }

  ws.onerror = () => { running.value = false; statusMsg.value = 'WebSocket error' }
}

async function cancelRun() {
  await fetch('/api/cancel', { method: 'POST' })
  statusMsg.value = 'Cancelling...'
}

function blockBg(type: string) {
  const map: Record<string, string> = {
    'vision-llm': 'rgba(17, 44, 39, 0.6)', 'txt2img': 'rgba(50, 30, 10, 0.6)',
    'img2img': 'rgba(35, 20, 55, 0.6)', 'refine': 'rgba(35, 20, 55, 0.6)',
    'pixel-upscale': 'rgba(15, 25, 50, 0.6)',
  }
  return map[type] || 'var(--bg-panel)'
}

function blockBorder(type: string) {
  const map: Record<string, string> = {
    'vision-llm': 'rgba(94, 234, 212, 0.3)', 'txt2img': 'rgba(232, 138, 42, 0.3)',
    'img2img': 'rgba(168, 130, 255, 0.3)', 'refine': 'rgba(168, 130, 255, 0.3)',
    'pixel-upscale': 'rgba(96, 165, 250, 0.3)',
  }
  return map[type] || 'var(--border)'
}

function blockDot(type: string) {
  const map: Record<string, string> = {
    'vision-llm': '#5eead4', 'txt2img': '#e88a2a', 'img2img': '#a882ff',
    'refine': '#a882ff', 'pixel-upscale': '#60a5fa',
  }
  return map[type] || '#444'
}
</script>

<style>
.timeline-block {
  min-width: 140px;
  padding: 8px 10px;
  border: 1px solid;
  border-radius: 3px;
  transition: all 0.15s;
}
.timeline-block:hover {
  filter: brightness(1.15);
}
</style>
