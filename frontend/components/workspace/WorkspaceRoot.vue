<template>
  <div class="h-screen w-screen flex flex-col overflow-hidden" style="background: var(--bg-primary)">
    <!-- Title Bar -->
    <WorkspaceTitleBar />

    <!-- Main workspace -->
    <div class="flex-1 flex overflow-hidden">
      <!-- Asset Panel (left, resizable) -->
      <div v-if="store.assetPanelOpen" class="relative shrink-0 flex" :style="{ width: store.assetPanelWidth + 'px' }">
        <AssetPanel class="flex-1" />
        <ResizeHandle side="right" v-model="store.assetPanelWidth" :min="180" :max="400" />
      </div>

      <!-- Center: Canvas + Bottom -->
      <div class="flex-1 flex flex-col overflow-hidden">
        <!-- Canvas -->
        <PipelineCanvas class="flex-1" />

        <!-- Bottom panel (Output + Console, resizable) -->
        <div v-if="store.outputBarOpen" class="relative shrink-0" :style="{ height: store.bottomPanelHeight + 'px' }">
          <ResizeHandle side="top" v-model="store.bottomPanelHeight" :min="100" :max="500" />
          <!-- Tab bar -->
          <div class="h-7 flex items-center px-1 shrink-0" style="background: var(--bg-secondary); border-top: 1px solid var(--border)">
            <button
              v-for="tab in bottomTabs"
              :key="tab.id"
              @click="store.bottomTab = tab.id"
              class="px-2.5 py-0.5 text-[11px] rounded"
              :style="store.bottomTab === tab.id
                ? 'background: var(--bg-active); color: var(--text-primary)'
                : 'color: var(--text-muted)'"
            >{{ tab.label }}</button>
          </div>
          <!-- Tab content -->
          <div class="flex-1 overflow-hidden" :style="{ height: (store.bottomPanelHeight - 28) + 'px' }">
            <OutputBar v-if="store.bottomTab === 'output'" />
            <ConsolePanel v-else-if="store.bottomTab === 'console'" />
          </div>
        </div>
      </div>

      <!-- Properties Panel (right, resizable) -->
      <div v-if="store.propertiesPanelOpen" class="relative shrink-0 flex" :style="{ width: store.propertiesPanelWidth + 'px' }">
        <ResizeHandle side="left" v-model="store.propertiesPanelWidth" :min="200" :max="500" />
        <PropertiesPanel class="flex-1" />
      </div>
    </div>

    <!-- Status Bar -->
    <WorkspaceStatusBar />
  </div>
</template>

<script setup lang="ts">
import { useWorkspaceStore } from '~/stores/workspace'

const store = useWorkspaceStore()

const bottomTabs = [
  { id: 'output' as const, label: 'Output' },
  { id: 'console' as const, label: 'Console' },
]

onMounted(async () => {
  await store.loadModels()
  await store.loadVram()
  store.log('info', 'vargen workspace loaded')
  store.log('info', `VRAM: ${store.vramFree}MB free / ${store.vramTotal}MB total`)

  const modelCount = Object.values(store.modelInventory).reduce((s, arr) => s + (arr as any[]).length, 0)
  store.log('info', `${modelCount} models discovered`)

  setInterval(() => store.loadVram(), 10000)
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
})

function onKeydown(e: KeyboardEvent) {
  if (e.ctrlKey && e.key === 'Enter') { e.preventDefault(); store.run() }
  if (e.key === 'Escape') {
    if (store.running) store.cancel()
    else store.selectedNodeId = null
  }
  if ((e.key === 'Delete' || e.key === 'Backspace') && store.selectedNodeId && !(e.target as HTMLElement).matches('input, textarea, select')) {
    store.removeNode(store.selectedNodeId)
  }
  if (e.ctrlKey && e.key === '1') { e.preventDefault(); store.assetPanelOpen = !store.assetPanelOpen }
  if (e.ctrlKey && e.key === '2') { e.preventDefault(); store.propertiesPanelOpen = !store.propertiesPanelOpen }
  if (e.ctrlKey && e.key === '3') { e.preventDefault(); store.outputBarOpen = !store.outputBarOpen }
  if (e.ctrlKey && e.key === '`') { e.preventDefault(); store.bottomTab = store.bottomTab === 'console' ? 'output' : 'console' }
  if (e.ctrlKey && e.key === 's') { e.preventDefault(); /* save */ }
}
</script>
