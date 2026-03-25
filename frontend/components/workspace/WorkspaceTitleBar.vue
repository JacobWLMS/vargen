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

    <!-- Spacer -->
    <div class="flex-1" />

    <!-- VRAM -->
    <div class="flex items-center gap-1.5 text-[11px] mono" style="color: var(--text-muted)">
      <div class="w-1.5 h-1.5 rounded-full" :style="{ background: vramColor }" />
      {{ store.vramFree }}MB / {{ store.vramTotal }}MB
    </div>

    <!-- Run / Cancel -->
    <button v-if="!store.running" @click="store.run()" class="btn btn-primary flex items-center gap-1.5 px-3">
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
      { label: 'Save', shortcut: 'Ctrl+S', action: savePipeline },
      { label: 'Load...', shortcut: '', action: loadPipeline },
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

async function savePipeline() {
  const yaml = store.toYaml()
  try {
    await fetch(`/api/pipelines/${store.pipelineName}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ yaml }),
    })
  } catch {}
}

async function loadPipeline() {
  try {
    const res = await fetch('/api/pipelines')
    const pipelines = await res.json()
    // Simple: load first one for now. TODO: proper picker
    if (pipelines.length) {
      const data = await (await fetch(`/api/pipelines/${pipelines[0].id}`)).json()
      store.fromYaml(data.yaml)
    }
  } catch {}
}
</script>
