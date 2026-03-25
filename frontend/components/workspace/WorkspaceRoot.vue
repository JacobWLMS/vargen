<template>
  <div class="h-screen w-screen flex flex-col overflow-hidden" style="background: var(--bg-primary)">
    <!-- Title Bar -->
    <WorkspaceTitleBar />

    <!-- Main workspace -->
    <div class="flex-1 flex overflow-hidden">
      <!-- Asset Panel (left) -->
      <AssetPanel v-if="store.assetPanelOpen" />

      <!-- Canvas (center) -->
      <PipelineCanvas class="flex-1" />

      <!-- Properties Panel (right) -->
      <PropertiesPanel v-if="store.propertiesPanelOpen" />
    </div>

    <!-- Output Bar (bottom) -->
    <OutputBar v-if="store.outputBarOpen" />

    <!-- Status Bar -->
    <WorkspaceStatusBar />
  </div>
</template>

<script setup lang="ts">
import { useWorkspaceStore } from '~/stores/workspace'

const store = useWorkspaceStore()

onMounted(async () => {
  await store.loadModels()
  await store.loadVram()

  // Poll VRAM every 10s
  setInterval(() => store.loadVram(), 10000)

  // Keyboard shortcuts
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
})

function onKeydown(e: KeyboardEvent) {
  // Ctrl+Enter: Run
  if (e.ctrlKey && e.key === 'Enter') { e.preventDefault(); store.run() }
  // Escape: Cancel or deselect
  if (e.key === 'Escape') {
    if (store.running) store.cancel()
    else store.selectedNodeId = null
  }
  // Delete: Remove selected node
  if ((e.key === 'Delete' || e.key === 'Backspace') && store.selectedNodeId && !(e.target as HTMLElement).matches('input, textarea, select')) {
    store.removeNode(store.selectedNodeId)
  }
  // Ctrl+1/2/3: Toggle panels
  if (e.ctrlKey && e.key === '1') { e.preventDefault(); store.assetPanelOpen = !store.assetPanelOpen }
  if (e.ctrlKey && e.key === '2') { e.preventDefault(); store.propertiesPanelOpen = !store.propertiesPanelOpen }
  if (e.ctrlKey && e.key === '3') { e.preventDefault(); store.outputBarOpen = !store.outputBarOpen }
}
</script>
