<template>
  <div class="w-60 shrink-0 flex flex-col overflow-hidden" style="background: var(--bg-panel); border-right: 1px solid var(--border)">
    <!-- Models -->
    <div class="flex-1 overflow-y-auto">
      <button @click="modelsOpen = !modelsOpen" class="w-full px-3 py-1.5 flex items-center gap-1 text-left" style="border-bottom: 1px solid var(--border)">
        <span class="text-[10px]" style="color: var(--text-muted)">{{ modelsOpen ? '▼' : '▶' }}</span>
        <span class="text-[11px] font-semibold uppercase tracking-wider" style="color: var(--text-muted)">Models</span>
        <span class="ml-auto text-[10px]" style="color: var(--text-muted)">{{ totalModels }}</span>
      </button>
      <div v-if="modelsOpen" class="px-1 py-1">
        <input v-model="modelFilter" placeholder="Filter..." class="w-full px-2 py-1 text-[11px] mb-1" />
        <div v-for="(models, category) in filteredModels" :key="category">
          <p class="px-2 py-0.5 text-[10px] uppercase tracking-wider" style="color: var(--text-muted)">{{ category }}</p>
          <div
            v-for="m in models"
            :key="m.name"
            draggable="true"
            @dragstart="onModelDrag(m, category, $event)"
            class="px-2 py-1 rounded cursor-grab text-[11px] flex items-center gap-1.5 group"
            style="color: var(--text-secondary)"
            @mouseenter="($event.target as HTMLElement).style.background = 'var(--bg-hover)'"
            @mouseleave="($event.target as HTMLElement).style.background = 'transparent'"
          >
            <span class="w-1.5 h-1.5 rounded-full shrink-0" :style="{ background: formatColor(m.format) }" />
            <span class="flex-1 truncate">{{ m.name }}</span>
            <span class="text-[9px]" style="color: var(--text-muted)">{{ m.size_mb }}MB</span>
          </div>
        </div>
        <p v-if="totalModels === 0" class="px-2 py-4 text-[11px] text-center" style="color: var(--text-muted)">
          No models found.<br/>Check Settings → Model Paths
        </p>
      </div>
    </div>

    <!-- Step Types -->
    <div style="border-top: 1px solid var(--border)">
      <button @click="stepsOpen = !stepsOpen" class="w-full px-3 py-1.5 flex items-center gap-1 text-left">
        <span class="text-[10px]" style="color: var(--text-muted)">{{ stepsOpen ? '▼' : '▶' }}</span>
        <span class="text-[11px] font-semibold uppercase tracking-wider" style="color: var(--text-muted)">Steps</span>
      </button>
      <div v-if="stepsOpen" class="px-1 py-1">
        <div
          v-for="st in stepTypes"
          :key="st.type"
          draggable="true"
          @dragstart="onStepDrag(st.type, $event)"
          class="px-2 py-1.5 rounded cursor-grab flex items-center gap-2"
          @mouseenter="($event.target as HTMLElement).style.background = 'var(--bg-hover)'"
          @mouseleave="($event.target as HTMLElement).style.background = 'transparent'"
        >
          <span class="w-2 h-2 rounded-full shrink-0" :style="{ background: st.color }" />
          <div>
            <p class="text-[11px]" style="color: var(--text-primary)">{{ st.type }}</p>
            <p class="text-[10px]" style="color: var(--text-muted)">{{ st.desc }}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Pipelines -->
    <div style="border-top: 1px solid var(--border)">
      <button @click="pipelinesOpen = !pipelinesOpen" class="w-full px-3 py-1.5 flex items-center gap-1 text-left">
        <span class="text-[10px]" style="color: var(--text-muted)">{{ pipelinesOpen ? '▼' : '▶' }}</span>
        <span class="text-[11px] font-semibold uppercase tracking-wider" style="color: var(--text-muted)">Pipelines</span>
      </button>
      <div v-if="pipelinesOpen" class="px-1 py-1 max-h-40 overflow-y-auto">
        <div
          v-for="p in pipelines"
          :key="p.id"
          @click="loadPipeline(p.id)"
          class="px-2 py-1 rounded cursor-pointer text-[11px]"
          style="color: var(--text-secondary)"
          @mouseenter="($event.target as HTMLElement).style.background = 'var(--bg-hover)'"
          @mouseleave="($event.target as HTMLElement).style.background = 'transparent'"
        >
          {{ p.name }}
          <span class="text-[9px]" style="color: var(--text-muted)">{{ p.steps }}s</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useWorkspaceStore } from '~/stores/workspace'

const store = useWorkspaceStore()
const modelFilter = ref('')
const modelsOpen = ref(true)
const stepsOpen = ref(true)
const pipelinesOpen = ref(true)
const pipelines = ref<any[]>([])

const stepTypes = [
  { type: 'vision-llm', color: '#5eead4', desc: 'Caption / describe' },
  { type: 'txt2img', color: '#e88a2a', desc: 'Generate from text' },
  { type: 'img2img', color: '#a882ff', desc: 'Refine / transform' },
  { type: 'pixel-upscale', color: '#60a5fa', desc: 'Upscale image' },
  { type: 'inpaint', color: '#f472b6', desc: 'Inpaint region' },
  { type: 'face-detail', color: '#fb923c', desc: 'Enhance faces' },
]

const filteredModels = computed(() => {
  const inv = store.modelInventory
  const result: Record<string, any[]> = {}
  for (const [cat, models] of Object.entries(inv)) {
    const filtered = (models as any[]).filter(m =>
      !modelFilter.value || m.name.toLowerCase().includes(modelFilter.value.toLowerCase())
    )
    if (filtered.length) result[cat] = filtered
  }
  return result
})

const totalModels = computed(() =>
  Object.values(store.modelInventory).reduce((sum, arr) => sum + (arr as any[]).length, 0)
)

function formatColor(fmt: string) {
  return { safetensors: 'var(--success)', gguf: '#60a5fa', bin: 'var(--warning)', pth: 'var(--warning)' }[fmt] || 'var(--text-muted)'
}

function onModelDrag(model: any, category: string, e: DragEvent) {
  e.dataTransfer!.setData('application/vargen-model', JSON.stringify({ ...model, category }))
  e.dataTransfer!.effectAllowed = 'copy'
}

function onStepDrag(type: string, e: DragEvent) {
  e.dataTransfer!.setData('application/vargen-step', type)
  e.dataTransfer!.effectAllowed = 'copy'
}

async function loadPipeline(id: string) {
  try {
    const res = await fetch(`/api/pipelines/${id}`)
    const data = await res.json()
    store.fromYaml(data.yaml)
    store.pipelineName = id
  } catch {}
}

onMounted(async () => {
  try {
    const res = await fetch('/api/pipelines')
    if (res.ok) pipelines.value = await res.json()
  } catch {}
})
</script>
