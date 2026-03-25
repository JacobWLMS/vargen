<template>
  <div class="h-9 flex items-center px-3 gap-2 shrink-0 select-none" style="background: var(--bg-secondary); border-bottom: 1px solid var(--border)">
    <!-- Logo -->
    <span class="text-[13px] font-semibold tracking-tight" style="color: var(--accent)">vargen</span>

    <!-- Menus -->
    <div class="flex gap-0.5 ml-4">
      <div v-for="menu in menus" :key="menu.label" class="relative">
        <button
          @click="openMenu = openMenu === menu.label ? '' : menu.label"
          class="px-2 py-1 text-[12px] rounded"
          :style="openMenu === menu.label ? 'background: var(--bg-active); color: var(--text-primary)' : 'color: var(--text-secondary)'"
        >{{ menu.label }}</button>
        <div
          v-if="openMenu === menu.label"
          class="absolute top-full left-0 mt-0.5 py-1 rounded z-50 min-w-[180px]"
          style="background: var(--bg-panel); border: 1px solid var(--border)"
        >
          <button
            v-for="item in menu.items"
            :key="item.label"
            @click="item.action(); openMenu = ''"
            class="w-full px-3 py-1 text-left text-[12px] flex items-center gap-3"
            style="color: var(--text-secondary)"
            @mouseenter="($event.target as HTMLElement).style.background = 'var(--bg-hover)'"
            @mouseleave="($event.target as HTMLElement).style.background = 'transparent'"
          >
            <span class="flex-1">{{ item.label }}</span>
            <span v-if="item.shortcut" class="mono text-[10px]" style="color: var(--text-muted)">{{ item.shortcut }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Pipeline name -->
    <input
      :value="store.pipelineName"
      @input="store.pipelineName = ($event.target as HTMLInputElement).value"
      class="px-2 py-0.5 text-[12px] mono w-40 ml-4"
      style="background: transparent !important; border: none !important; color: var(--text-muted)"
    />

    <!-- Pipeline picker modal -->
    <div
      v-if="pickerOpen"
      class="fixed inset-0 z-50 flex items-center justify-center"
      style="background: rgba(0,0,0,0.7)"
      @click.self="pickerOpen = false"
    >
      <div class="w-96 max-h-96 rounded overflow-hidden" style="background: var(--bg-panel); border: 1px solid var(--border)">
        <div class="px-3 py-2 flex items-center" style="border-bottom: 1px solid var(--border)">
          <span class="text-[12px] font-medium" style="color: var(--text-primary)">Load Pipeline</span>
          <button @click="pickerOpen = false" class="ml-auto text-[14px]" style="color: var(--text-muted)">&times;</button>
        </div>
        <input
          v-model="pickerFilter"
          placeholder="Filter..."
          class="w-full px-3 py-1.5 text-[12px]"
          style="border: none !important; border-bottom: 1px solid var(--border) !important; border-radius: 0 !important"
          ref="pickerInput"
        />
        <div class="max-h-72 overflow-y-auto">
          <div
            v-for="p in filteredPipelines"
            :key="p.id"
            @click="pickPipeline(p.id)"
            class="px-3 py-2 cursor-pointer"
            style="border-bottom: 1px solid var(--border)"
            @mouseenter="($event.target as HTMLElement).style.background = 'var(--bg-hover)'"
            @mouseleave="($event.target as HTMLElement).style.background = 'transparent'"
          >
            <p class="text-[12px]" style="color: var(--text-primary)">{{ p.name }}</p>
            <p class="text-[10px] mt-0.5" style="color: var(--text-muted)">{{ p.description || p.id }} · {{ p.steps }} steps</p>
            <div v-if="p.tags?.length" class="flex gap-1 mt-1">
              <span v-for="tag in p.tags" :key="tag" class="text-[9px] px-1 py-0.5 rounded" style="background: var(--bg-active); color: var(--text-muted)">{{ tag }}</span>
            </div>
          </div>
          <p v-if="!filteredPipelines.length" class="px-3 py-4 text-[11px] text-center" style="color: var(--text-muted)">No pipelines found</p>
        </div>
      </div>
    </div>

    <!-- Spacer -->
    <div class="flex-1" />

    <!-- VRAM -->
    <div class="flex items-center gap-1.5 text-[11px] mono" style="color: var(--text-muted)">
      <div class="w-1.5 h-1.5 rounded-full" :style="{ background: vramColor }" />
      {{ store.vramFree }}MB / {{ store.vramTotal }}MB
    </div>

    <!-- Run / Cancel -->
    <button v-if="!store.running" @click="store.runGraph()" class="btn btn-primary flex items-center gap-1.5 px-3">
      <span class="text-[10px]">&#9654;</span> Run
    </button>
    <button v-else @click="store.cancel()" class="btn btn-danger px-3">
      Stop
    </button>
  </div>
</template>

<script setup lang="ts">
import { useWorkspaceStore } from '~/stores/workspace'

const store = useWorkspaceStore()
const openMenu = ref('')
const pickerOpen = ref(false)
const pickerFilter = ref('')
const pickerInput = ref<HTMLInputElement>()
const allPipelines = ref<any[]>([])

const filteredPipelines = computed(() =>
  allPipelines.value.filter(p =>
    !pickerFilter.value || p.name.toLowerCase().includes(pickerFilter.value.toLowerCase()) || p.id.includes(pickerFilter.value.toLowerCase())
  )
)

const vramColor = computed(() => {
  if (!store.vramTotal) return '#444'
  const pct = store.vramFree / store.vramTotal
  return pct > 0.5 ? 'var(--success)' : pct > 0.2 ? 'var(--warning)' : 'var(--error)'
})

const menus = [
  {
    label: 'File',
    items: [
      { label: 'New Pipeline', shortcut: '', action: () => { store.nodes = []; store.edges = []; store.pipelineName = 'untitled' } },
      { label: 'Save', shortcut: 'Ctrl+S', action: () => store.saveWorkflow() },
      { label: 'Load...', shortcut: '', action: openPicker },
    ],
  },
  {
    label: 'View',
    items: [
      { label: 'Toggle Assets', shortcut: 'Ctrl+1', action: () => store.assetPanelOpen = !store.assetPanelOpen },
      { label: 'Toggle Properties', shortcut: 'Ctrl+2', action: () => store.propertiesPanelOpen = !store.propertiesPanelOpen },
      { label: 'Toggle Output', shortcut: 'Ctrl+3', action: () => store.outputBarOpen = !store.outputBarOpen },
    ],
  },
]

// Close menu on outside click
if (import.meta.client) {
  window.addEventListener('click', (e) => {
    if (!(e.target as HTMLElement).closest('.relative')) openMenu.value = ''
  })
}

async function openPicker() {
  try {
    const res = await fetch('/api/pipelines')
    allPipelines.value = await res.json()
  } catch {}
  pickerFilter.value = ''
  pickerOpen.value = true
  nextTick(() => pickerInput.value?.focus())
}

async function pickPipeline(id: string) {
  try {
    const res = await fetch(`/api/pipelines/${id}`)
    const data = await res.json()
    store.fromYaml(data.yaml)
    store.pipelineName = id
  } catch {}
  pickerOpen.value = false
}
</script>
