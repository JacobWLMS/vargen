<template>
  <div class="grid grid-cols-12 gap-6">
    <!-- Sidebar -->
    <div class="col-span-3 space-y-3">
      <h2 class="text-lg font-semibold">Pipelines</h2>
      <div
        v-for="p in pipelines"
        :key="p.id"
        @click="loadPipeline(p.id)"
        class="p-3 rounded-lg border cursor-pointer transition-all"
        :class="activePipeline === p.id
          ? 'border-vargen-500 bg-vargen-950/20'
          : 'border-gray-800 hover:border-gray-600'"
      >
        <p class="text-sm font-medium">{{ p.name }}</p>
        <p class="text-xs text-gray-500 mt-0.5">{{ p.steps }} steps</p>
        <div v-if="p.tags?.length" class="flex gap-1 mt-1.5 flex-wrap">
          <span v-for="tag in p.tags" :key="tag" class="px-1.5 py-0.5 text-[10px] rounded bg-gray-800 text-gray-400">
            {{ tag }}
          </span>
        </div>
      </div>
      <button
        @click="createNew"
        class="w-full py-2 rounded-lg border border-dashed border-gray-700 text-sm text-gray-500 hover:text-white hover:border-gray-500 transition-colors"
      >
        + New Pipeline
      </button>
    </div>

    <!-- Editor -->
    <div class="col-span-9 space-y-4">
      <div class="flex items-center gap-3">
        <input
          v-model="pipelineName"
          class="text-lg font-semibold bg-transparent border-b border-transparent hover:border-gray-700 focus:border-vargen-500 outline-none px-1 py-0.5"
          placeholder="Pipeline name"
        />
        <div class="ml-auto flex gap-2">
          <button
            @click="checkPipelineModels"
            class="px-3 py-1.5 text-xs rounded-lg bg-gray-800 hover:bg-gray-700 transition-colors"
          >
            Check Models
          </button>
          <button
            @click="saveCurrent"
            class="px-3 py-1.5 text-xs rounded-lg bg-vargen-600 hover:bg-vargen-500 text-white transition-colors"
          >
            Save
          </button>
        </div>
      </div>

      <!-- YAML Editor -->
      <div class="relative">
        <textarea
          v-model="yamlContent"
          class="w-full h-[600px] bg-gray-900 border border-gray-800 rounded-xl p-4 font-mono text-sm text-gray-200 resize-none focus:ring-1 focus:ring-vargen-500 focus:border-vargen-500 outline-none"
          spellcheck="false"
        />
      </div>

      <!-- Model check results -->
      <div v-if="modelCheck.length" class="space-y-1">
        <div
          v-for="m in modelCheck"
          :key="m.name"
          class="flex items-center gap-2 p-2 rounded-lg bg-gray-900/50 text-sm"
        >
          <div class="w-2 h-2 rounded-full" :class="m.cached ? 'bg-green-500' : 'bg-yellow-500'" />
          <span class="font-medium">{{ m.name }}</span>
          <span class="text-gray-500">{{ m.repo }}{{ m.file ? '/' + m.file : '' }}</span>
          <span v-if="m.vram_mb" class="text-xs text-gray-600 ml-auto">{{ m.vram_mb }}MB</span>
        </div>
      </div>

      <p v-if="saveStatus" class="text-sm" :class="saveStatus.startsWith('Error') ? 'text-red-400' : 'text-green-400'">
        {{ saveStatus }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
const api = useApi()
const pipelines = ref<any[]>([])
const activePipeline = ref('')
const pipelineName = ref('')
const yamlContent = ref('')
const modelCheck = ref<any[]>([])
const saveStatus = ref('')

onMounted(async () => {
  pipelines.value = await api.listPipelines()
})

async function loadPipeline(id: string) {
  activePipeline.value = id
  const data = await api.getPipeline(id)
  yamlContent.value = data.yaml
  pipelineName.value = id
  modelCheck.value = []
  saveStatus.value = ''
}

async function saveCurrent() {
  if (!pipelineName.value || !yamlContent.value) return
  try {
    await api.savePipeline(pipelineName.value, yamlContent.value)
    saveStatus.value = 'Saved!'
    pipelines.value = await api.listPipelines()
    setTimeout(() => saveStatus.value = '', 2000)
  } catch (e: any) {
    saveStatus.value = `Error: ${e.message}`
  }
}

async function checkPipelineModels() {
  if (!yamlContent.value) return
  try {
    modelCheck.value = await api.checkModels(yamlContent.value)
  } catch (e: any) {
    modelCheck.value = []
    saveStatus.value = `Error: ${e.message}`
  }
}

function createNew() {
  activePipeline.value = ''
  pipelineName.value = 'new_pipeline'
  yamlContent.value = `name: "New Pipeline"
description: ""
version: 1
tags: []

models:
  flux-dev:
    repo: "city96/FLUX.1-dev-gguf"
    file: "flux1-dev-Q4_K_S.gguf"
    format: gguf
    vram_mb: 5300

steps:
  - name: generate
    type: txt2img
    model: flux-dev
    prompt: "your prompt here"
    width: 1024
    height: 1024
    steps: 20
    guidance: 3.5
    seed: -1
`
  modelCheck.value = []
}
</script>
