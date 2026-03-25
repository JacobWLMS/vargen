<template>
  <div class="h-full flex">
    <!-- Sidebar: controls -->
    <div class="w-72 shrink-0 overflow-y-auto p-3 space-y-3" style="border-right: 1px solid var(--border)">

      <!-- Image input -->
      <div class="panel">
        <div class="panel-header">Reference Image</div>
        <div
          class="p-2 cursor-pointer"
          @click="($refs.fileInput as HTMLInputElement).click()"
          @drop.prevent="onDrop"
          @dragover.prevent
        >
          <input ref="fileInput" type="file" accept="image/*" class="hidden" @change="onFileSelect" />
          <img v-if="previewUrl" :src="previewUrl" class="w-full rounded" />
          <div v-else class="py-8 text-center text-[12px]" style="color: var(--text-muted)">
            Drop image or click
          </div>
        </div>
      </div>

      <!-- Pipeline -->
      <div class="panel">
        <div class="panel-header">Pipeline</div>
        <div class="p-2">
          <select v-model="selectedPipeline" class="w-full px-2 py-1.5 text-[12px]">
            <option v-for="p in pipelines" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
          <p v-if="pipelineInfo" class="text-[11px] mt-1.5 px-0.5" style="color: var(--text-muted)">
            {{ pipelineInfo.steps }} steps · {{ pipelineInfo.tags?.join(', ') }}
          </p>
        </div>
      </div>

      <!-- Run -->
      <button
        @click="runGeneration"
        :disabled="running || !uploadedImage"
        class="btn btn-primary w-full py-2"
      >
        {{ running ? 'Running...' : 'Generate' }}
      </button>

      <!-- Steps progress -->
      <div v-if="steps.length" class="panel">
        <div class="panel-header">Progress</div>
        <div class="p-1">
          <div
            v-for="step in steps"
            :key="step.name"
            class="flex items-center gap-2 px-2 py-1.5 text-[12px]"
          >
            <div class="w-1.5 h-1.5 rounded-full shrink-0" :style="{ background: stepColor(step) }" />
            <span class="flex-1 truncate">{{ step.name }}</span>
            <span v-if="step.duration" class="mono" style="color: var(--text-muted)">{{ step.duration.toFixed(1) }}s</span>
            <div v-if="step.status === 'running'" class="w-3 h-3 border border-t-transparent rounded-full animate-spin" style="border-color: var(--accent); border-top-color: transparent" />
          </div>
        </div>
      </div>

      <!-- Caption -->
      <div v-if="captionText" class="panel">
        <div class="panel-header">Caption</div>
        <p class="p-2 text-[11px] leading-relaxed" style="color: var(--text-secondary)">{{ captionText }}</p>
      </div>
    </div>

    <!-- Main: output -->
    <div class="flex-1 overflow-y-auto p-4 flex flex-col items-center justify-center" style="background: var(--bg-primary)">
      <template v-if="outputImages.length">
        <img
          :src="outputImages[selectedOutput]"
          class="max-h-[calc(100vh-12rem)] rounded"
          style="border: 1px solid var(--border)"
        />
        <div v-if="outputImages.length > 1" class="flex gap-1.5 mt-3 flex-wrap justify-center">
          <img
            v-for="(url, i) in outputImages"
            :key="i"
            :src="url"
            @click="selectedOutput = i"
            class="w-14 h-14 object-cover rounded cursor-pointer transition-opacity"
            :style="{ opacity: i === selectedOutput ? 1 : 0.4, border: i === selectedOutput ? '1px solid var(--accent)' : '1px solid var(--border)' }"
          />
        </div>
      </template>
      <div v-else class="text-center" style="color: var(--text-muted)">
        <p class="text-[13px]">No output yet</p>
        <p class="text-[11px] mt-1">Upload an image and run a pipeline</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const api = useApi()
const fileInput = ref()
const pipelines = ref<any[]>([])
const selectedPipeline = ref('')
const uploadedImage = ref<string | null>(null)
const previewUrl = ref<string | null>(null)
const running = ref(false)
const outputImages = ref<string[]>([])
const selectedOutput = ref(0)
const captionText = ref('')
const steps = ref<any[]>([])

const pipelineInfo = computed(() => pipelines.value.find(p => p.id === selectedPipeline.value))

onMounted(async () => {
  try {
    pipelines.value = await api.listPipelines()
    if (pipelines.value.length) selectedPipeline.value = pipelines.value[0].id
  } catch {}
})

function onFileSelect(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (file) handleFile(file)
}

function onDrop(e: DragEvent) {
  const file = e.dataTransfer?.files?.[0]
  if (file) handleFile(file)
}

async function handleFile(file: File) {
  previewUrl.value = URL.createObjectURL(file)
  const result = await api.uploadImage(file)
  uploadedImage.value = result.filename
}

function stepColor(step: any) {
  if (step.status === 'done') return 'var(--success)'
  if (step.status === 'running') return 'var(--accent)'
  return 'var(--text-muted)'
}

function runGeneration() {
  if (!uploadedImage.value || !selectedPipeline.value) return
  running.value = true
  outputImages.value = []
  captionText.value = ''
  steps.value = []
  selectedOutput.value = 0

  api.runPipelineWs(selectedPipeline.value, uploadedImage.value, undefined, {
    onStepStart(data) {
      steps.value.push({ name: data.step, status: 'running' })
    },
    onStepDone(data) {
      const step = steps.value.find(s => s.name === data.step)
      if (step) { step.status = 'done'; step.duration = data.duration }
      if (data.url) outputImages.value.push(`${api.base}${data.url}`)
      if (data.urls) data.urls.forEach((u: string) => outputImages.value.push(`${api.base}${u}`))
      if (data.text) captionText.value = data.text
    },
    onBatchProgress(data) {
      const step = steps.value.find(s => s.name === data.step)
      if (step) step.batch = `${data.index + 1}/${data.total}`
    },
    onComplete() { running.value = false },
    onError(msg) { running.value = false; alert(msg) },
  })
}
</script>
