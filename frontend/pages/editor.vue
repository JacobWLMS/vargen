<template>
  <div class="h-full flex">
    <!-- Sidebar: pipeline list -->
    <div class="w-56 shrink-0 overflow-y-auto" style="border-right: 1px solid var(--border)">
      <div class="p-2 space-y-0.5">
        <div
          v-for="p in pipelines"
          :key="p.id"
          @click="loadPipeline(p.id)"
          class="px-2 py-1.5 rounded cursor-pointer text-[12px] transition-colors"
          :style="activePipeline === p.id
            ? 'background: var(--bg-active); color: var(--text-primary)'
            : 'color: var(--text-secondary)'"
        >
          {{ p.name }}
        </div>
      </div>
      <div class="p-2 pt-0">
        <button @click="createNew" class="btn btn-ghost w-full text-[11px]">+ New</button>
      </div>
    </div>

    <!-- Editor -->
    <div class="flex-1 flex flex-col overflow-hidden">
      <!-- Toolbar -->
      <div class="h-9 flex items-center gap-2 px-3 shrink-0" style="border-bottom: 1px solid var(--border)">
        <input
          v-model="pipelineName"
          class="mono text-[12px] px-1.5 py-0.5 w-48"
          style="background: transparent !important; border: none !important"
          placeholder="filename"
        />
        <div class="ml-auto flex gap-1.5">
          <button @click="checkModels" class="btn btn-ghost text-[11px]">Check Models</button>
          <button @click="saveCurrent" class="btn btn-primary text-[11px]">Save</button>
        </div>
      </div>

      <div class="flex-1 flex overflow-hidden">
        <!-- YAML -->
        <textarea
          v-model="yamlContent"
          class="flex-1 p-4 mono text-[12px] leading-relaxed resize-none outline-none"
          style="background: var(--bg-primary) !important; border: none !important; color: var(--text-primary)"
          spellcheck="false"
        />

        <!-- Model status sidebar -->
        <div v-if="modelCheck.length" class="w-64 shrink-0 overflow-y-auto p-3 space-y-1" style="border-left: 1px solid var(--border)">
          <p class="text-[11px] uppercase tracking-wider mb-2" style="color: var(--text-muted)">Models</p>
          <div
            v-for="m in modelCheck"
            :key="m.name"
            class="flex items-center gap-2 py-1 text-[11px]"
          >
            <div class="w-1.5 h-1.5 rounded-full" :style="{ background: m.cached ? 'var(--success)' : 'var(--warning)' }" />
            <span style="color: var(--text-primary)">{{ m.name }}</span>
            <span v-if="m.vram_mb" class="ml-auto mono" style="color: var(--text-muted)">{{ m.vram_mb }}MB</span>
          </div>
        </div>
      </div>

      <p v-if="saveStatus" class="px-3 py-1 text-[11px]" :style="{ color: saveStatus.startsWith('Error') ? 'var(--error)' : 'var(--success)' }">
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
  try { pipelines.value = await api.listPipelines() } catch {}
})

async function loadPipeline(id: string) {
  activePipeline.value = id
  const data = await api.getPipeline(id)
  yamlContent.value = data.yaml
  pipelineName.value = id
  modelCheck.value = []
}

async function saveCurrent() {
  if (!pipelineName.value) return
  try {
    await api.savePipeline(pipelineName.value, yamlContent.value)
    saveStatus.value = 'Saved'
    pipelines.value = await api.listPipelines()
    setTimeout(() => saveStatus.value = '', 2000)
  } catch (e: any) {
    saveStatus.value = `Error: ${e.message}`
  }
}

async function checkModels() {
  try { modelCheck.value = await api.checkModels(yamlContent.value) } catch {}
}

function createNew() {
  activePipeline.value = ''
  pipelineName.value = 'new_pipeline'
  yamlContent.value = `name: "New Pipeline"
description: ""
version: 1

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
    prompt: ""
    width: 1024
    height: 1024
    steps: 20
    guidance: 3.5
`
}
</script>
