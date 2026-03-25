<template>
  <div class="grid grid-cols-12 gap-6">
    <!-- Left: Input + Controls -->
    <div class="col-span-4 space-y-4">
      <!-- Image Upload -->
      <div
        class="border-2 border-dashed border-gray-700 rounded-xl p-4 text-center cursor-pointer hover:border-vargen-500 transition-colors"
        :class="{ 'border-vargen-500 bg-vargen-950/20': uploadedImage }"
        @click="$refs.fileInput.click()"
        @drop.prevent="onDrop"
        @dragover.prevent
      >
        <input ref="fileInput" type="file" accept="image/*" class="hidden" @change="onFileSelect" />
        <img v-if="previewUrl" :src="previewUrl" class="max-h-64 mx-auto rounded-lg" />
        <div v-else class="py-12 text-gray-500">
          <p class="text-lg font-medium">Drop image here</p>
          <p class="text-sm mt-1">or click to browse</p>
        </div>
      </div>

      <!-- Pipeline Selection -->
      <div>
        <label class="block text-sm font-medium text-gray-400 mb-1">Pipeline</label>
        <select
          v-model="selectedPipeline"
          class="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2.5 text-sm focus:ring-vargen-500 focus:border-vargen-500"
        >
          <option v-for="p in pipelines" :key="p.id" :value="p.id">
            {{ p.name }}
          </option>
        </select>
        <p v-if="pipelineInfo" class="text-xs text-gray-500 mt-1">
          {{ pipelineInfo.description }} — {{ pipelineInfo.steps }} steps
        </p>
      </div>

      <!-- Run Button -->
      <button
        @click="runGeneration"
        :disabled="running || !uploadedImage"
        class="w-full py-3 rounded-xl font-semibold text-sm transition-all"
        :class="running
          ? 'bg-gray-800 text-gray-500 cursor-wait'
          : 'bg-vargen-600 hover:bg-vargen-500 text-white shadow-lg shadow-vargen-600/20'"
      >
        {{ running ? 'Generating...' : 'Generate' }}
      </button>

      <!-- Progress -->
      <div v-if="steps.length" class="space-y-2">
        <div
          v-for="step in steps"
          :key="step.name"
          class="flex items-center gap-3 p-3 rounded-lg bg-gray-900/50 border border-gray-800"
        >
          <div class="w-2 h-2 rounded-full shrink-0" :class="stepColor(step)" />
          <div class="min-w-0 flex-1">
            <p class="text-sm font-medium truncate">{{ step.name }}</p>
            <p v-if="step.status === 'done'" class="text-xs text-gray-500">{{ step.duration?.toFixed(1) }}s</p>
            <p v-if="step.status === 'running' && step.batchProgress" class="text-xs text-vargen-400">
              Batch {{ step.batchProgress.index + 1 }}/{{ step.batchProgress.total }}
            </p>
          </div>
          <div v-if="step.status === 'running'" class="w-4 h-4 border-2 border-vargen-400 border-t-transparent rounded-full animate-spin" />
        </div>
      </div>
    </div>

    <!-- Right: Output -->
    <div class="col-span-8">
      <div v-if="outputImages.length" class="space-y-4">
        <!-- Main result -->
        <img
          :src="outputImages[outputImages.length - 1]"
          class="w-full rounded-xl border border-gray-800 shadow-2xl"
        />
        <!-- Thumbnails -->
        <div v-if="outputImages.length > 1" class="flex gap-2 flex-wrap">
          <img
            v-for="(url, i) in outputImages"
            :key="i"
            :src="url"
            class="w-24 h-24 object-cover rounded-lg border border-gray-800 cursor-pointer hover:border-vargen-500 transition-colors"
            @click="selectedOutput = i"
          />
        </div>
      </div>
      <div v-else class="h-96 flex items-center justify-center border border-gray-800 rounded-xl bg-gray-900/30">
        <p class="text-gray-600">Output will appear here</p>
      </div>

      <!-- Caption preview -->
      <div v-if="captionText" class="mt-4 p-4 rounded-lg bg-gray-900/50 border border-gray-800">
        <p class="text-xs font-medium text-gray-500 mb-1">Caption</p>
        <p class="text-sm text-gray-300">{{ captionText }}</p>
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
  pipelines.value = await api.listPipelines()
  if (pipelines.value.length) selectedPipeline.value = pipelines.value[0].id
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
  if (step.status === 'done') return 'bg-green-500'
  if (step.status === 'running') return 'bg-vargen-400 animate-pulse'
  return 'bg-gray-600'
}

function runGeneration() {
  if (!uploadedImage.value || !selectedPipeline.value) return
  running.value = true
  outputImages.value = []
  captionText.value = ''
  steps.value = []

  api.runPipelineWs(
    selectedPipeline.value,
    uploadedImage.value,
    undefined,
    {
      onStepStart(data) {
        steps.value.push({ name: data.step, status: 'running' })
      },
      onStepDone(data) {
        const step = steps.value.find(s => s.name === data.step)
        if (step) {
          step.status = 'done'
          step.duration = data.duration
        }
        if (data.url) {
          outputImages.value.push(`${api.base}${data.url}`)
        }
        if (data.urls) {
          data.urls.forEach((url: string) => outputImages.value.push(`${api.base}${url}`))
        }
        if (data.text) {
          captionText.value = data.text
        }
      },
      onBatchProgress(data) {
        const step = steps.value.find(s => s.name === data.step)
        if (step) step.batchProgress = data
      },
      onComplete() {
        running.value = false
      },
      onError(msg) {
        running.value = false
        alert(`Error: ${msg}`)
      },
    },
  )
}
</script>
