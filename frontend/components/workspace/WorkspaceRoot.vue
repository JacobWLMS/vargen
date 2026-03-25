<template>
  <div class="h-screen w-screen flex flex-col overflow-hidden" style="background: var(--bg-primary)">
    <WorkspaceTitleBar />

    <div class="flex-1 flex overflow-hidden">
      <!-- Left: Asset Panel -->
      <div v-if="store.assetPanelOpen" class="relative shrink-0 flex" :style="{ width: store.assetPanelWidth + 'px' }">
        <AssetPanel class="flex-1" />
        <ResizeHandle side="right" v-model="store.assetPanelWidth" :min="180" :max="400" />
      </div>

      <!-- Center: Canvas + Bottom -->
      <div class="flex-1 flex flex-col overflow-hidden">
        <PipelineCanvas class="flex-1" />

        <!-- Bottom (Output | Console | Properties) -->
        <div v-if="store.outputBarOpen" class="relative shrink-0" :style="{ height: store.bottomPanelHeight + 'px' }">
          <ResizeHandle side="top" v-model="store.bottomPanelHeight" :min="80" :max="600" />
          <div class="h-7 flex items-center px-1 gap-0.5 shrink-0" style="background: var(--bg-secondary); border-top: 1px solid var(--border)">
            <button v-for="tab in bottomTabs" :key="tab.id" @click="store.bottomTab = tab.id"
              class="px-2.5 py-0.5 text-[11px] rounded"
              :style="store.bottomTab === tab.id ? 'background: var(--bg-active); color: var(--text-primary)' : 'color: var(--text-muted)'"
            >{{ tab.label }}</button>
          </div>
          <div :style="{ height: (store.bottomPanelHeight - 28) + 'px' }" class="overflow-hidden">
            <OutputBar v-if="store.bottomTab === 'output'" />
            <ConsolePanel v-else-if="store.bottomTab === 'console'" />
            <PropertiesPanel v-else-if="store.bottomTab === 'properties'" />
          </div>
        </div>
      </div>

      <!-- Right: YAML Editor (togglable) -->
      <div v-if="store.yamlPanelOpen" class="relative shrink-0 flex" :style="{ width: store.yamlPanelWidth + 'px' }">
        <ResizeHandle side="left" v-model="store.yamlPanelWidth" :min="250" :max="700" />
        <YamlEditor class="flex-1" />
      </div>
    </div>

    <WorkspaceStatusBar />
  </div>
</template>

<script setup lang="ts">
import { useWorkspaceStore } from '~/stores/workspace'
const store = useWorkspaceStore()

const bottomTabs = [
  { id: 'output' as const, label: 'Output' },
  { id: 'console' as const, label: 'Console' },
  { id: 'properties' as const, label: 'Properties' },
]

onMounted(async () => {
  await store.loadModels()
  await store.loadNodeTypes()
  await store.loadVram()
  store.log('info', 'Workspace ready')
  const mc = Object.values(store.modelInventory).reduce((s, a) => s + (a as any[]).length, 0)
  store.log('info', `${mc} models · ${Object.keys(store.nodeTypes).length} node types`)
  setInterval(() => store.loadVram(), 10000)
  window.addEventListener('keydown', onKey)
})
onUnmounted(() => window.removeEventListener('keydown', onKey))

function onKey(e: KeyboardEvent) {
  const inInput = (e.target as HTMLElement).matches('input, textarea, select')
  if (e.ctrlKey && e.key === 'Enter') { e.preventDefault(); store.runGraph() }
  if (e.key === 'Escape') { store.running ? store.cancel() : (store.selectedNodeId = null) }
  if ((e.key === 'Delete' || e.key === 'Backspace') && store.selectedNodeId && !inInput) store.removeNode(store.selectedNodeId)
  if (e.ctrlKey && e.key === '1') { e.preventDefault(); store.assetPanelOpen = !store.assetPanelOpen }
  if (e.ctrlKey && e.key === '3') { e.preventDefault(); store.outputBarOpen = !store.outputBarOpen }
  if (e.ctrlKey && e.key === '`') { e.preventDefault(); store.yamlPanelOpen = !store.yamlPanelOpen }
}
</script>
