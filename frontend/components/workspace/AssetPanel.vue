<template>
  <div class="w-full flex flex-col overflow-hidden" style="background: var(--bg-panel); border-right: 1px solid var(--border)">
    <!-- Tab bar -->
    <div class="flex shrink-0" style="border-bottom: 1px solid var(--border)">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        @click="activeTab = tab.id"
        class="flex-1 py-1.5 text-[10px] uppercase tracking-wider text-center transition-colors"
        :style="activeTab === tab.id
          ? 'color: var(--text-primary); border-bottom: 2px solid var(--accent); background: var(--bg-secondary)'
          : 'color: var(--text-muted); border-bottom: 2px solid transparent'"
      >{{ tab.label }}</button>
    </div>

    <!-- Search (shared) -->
    <div class="px-2 py-1 shrink-0" style="border-bottom: 1px solid var(--border)">
      <input v-model="search" :placeholder="searchPlaceholder" class="w-full px-2 py-1 text-[11px]" />
    </div>

    <!-- Tab content -->
    <div class="flex-1 overflow-y-auto">
      <!-- NODES tab -->
      <template v-if="activeTab === 'nodes'">
        <div v-for="(nodes, cat) in nodesByCategory" :key="cat" class="mb-1">
          <div class="px-2 py-1 text-[9px] uppercase tracking-wider" style="color: var(--text-muted); border-bottom: 1px solid var(--border)">{{ cat }}</div>
          <div
            v-for="nt in nodes"
            :key="nt.type_id"
            draggable="true"
            @dragstart="e => { e.dataTransfer!.setData('vargen/node-type', nt.type_id); e.dataTransfer!.effectAllowed = 'copy' }"
            class="asset-item"
          >
            <span class="w-2 h-2 rounded-full shrink-0" :style="{ background: nt.color }" />
            <span class="flex-1 truncate">{{ nt.label }}</span>
          </div>
        </div>
      </template>

      <!-- MODELS tab -->
      <template v-if="activeTab === 'models'">
        <div v-for="(models, cat) in filteredModels" :key="cat" class="mb-1">
          <div class="px-2 py-1 text-[9px] uppercase tracking-wider" style="color: var(--text-muted); border-bottom: 1px solid var(--border)">{{ cat }} ({{ models.length }})</div>
          <div
            v-for="m in models"
            :key="m.name"
            draggable="true"
            @dragstart="e => { e.dataTransfer!.setData('vargen/model', JSON.stringify({ ...m, category: cat })); e.dataTransfer!.effectAllowed = 'copy' }"
            class="asset-item"
          >
            <span class="w-1.5 h-1.5 rounded-full shrink-0" :style="{ background: fmtColor(m.format) }" />
            <span class="flex-1 truncate">{{ m.name }}</span>
            <span class="text-[9px] mono shrink-0" style="color: var(--text-muted)">{{ m.size_mb > 1024 ? (m.size_mb/1024).toFixed(1) + 'GB' : m.size_mb + 'MB' }}</span>
          </div>
        </div>
        <p v-if="!Object.keys(filteredModels).length" class="px-3 py-6 text-[11px] text-center" style="color: var(--text-muted)">
          No models found. Check Settings.
        </p>
      </template>

      <!-- WORKFLOWS tab -->
      <template v-if="activeTab === 'workflows'">
        <div
          v-for="w in filteredWorkflows"
          :key="w.id"
          @click="store.loadWorkflow(w.id)"
          class="asset-item cursor-pointer"
        >
          <span class="flex-1">
            <span class="block truncate">{{ w.name }}</span>
            <span class="block text-[9px]" style="color: var(--text-muted)">{{ w.description || '' }}</span>
          </span>
          <span class="text-[9px] mono shrink-0" style="color: var(--text-muted)">{{ w.nodes }}n</span>
        </div>
        <p v-if="!filteredWorkflows.length" class="px-3 py-6 text-[11px] text-center" style="color: var(--text-muted)">
          No workflows saved yet.
        </p>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useWorkspaceStore } from '~/stores/workspace'
const store = useWorkspaceStore()
const search = ref('')
const activeTab = ref<'nodes' | 'models' | 'workflows'>('nodes')
const workflows = ref<any[]>([])

const tabs = [
  { id: 'nodes' as const, label: 'Nodes' },
  { id: 'models' as const, label: 'Models' },
  { id: 'workflows' as const, label: 'Workflows' },
]

const searchPlaceholder = computed(() => {
  return { nodes: 'Search nodes...', models: 'Search models...', workflows: 'Search workflows...' }[activeTab.value]
})

const nodesByCategory = computed(() => {
  const all = Object.values(store.nodeTypes) as any[]
  const filtered = search.value
    ? all.filter((n: any) => n.label.toLowerCase().includes(search.value.toLowerCase()))
    : all
  const groups: Record<string, any[]> = {}
  for (const n of filtered) {
    groups[n.category] = groups[n.category] || []
    groups[n.category].push(n)
  }
  return groups
})

const filteredModels = computed(() => {
  const result: Record<string, any[]> = {}
  for (const [cat, models] of Object.entries(store.modelInventory)) {
    const filtered = (models as any[]).filter(m =>
      !search.value || m.name.toLowerCase().includes(search.value.toLowerCase())
    )
    if (filtered.length) result[cat] = filtered.slice(0, 100)
  }
  return result
})

const filteredWorkflows = computed(() => {
  if (!search.value) return workflows.value
  return workflows.value.filter(w =>
    w.name.toLowerCase().includes(search.value.toLowerCase())
  )
})

function fmtColor(fmt: string) {
  return { safetensors: 'var(--success)', gguf: '#60a5fa', bin: 'var(--warning)' }[fmt] || 'var(--text-muted)'
}

onMounted(async () => {
  try { workflows.value = await (await fetch('/api/workflows')).json() } catch {}
})
</script>

<style>
.asset-item {
  display: flex; align-items: center; gap: 6px;
  padding: 4px 8px; font-size: 11px;
  color: var(--text-secondary); cursor: grab; border-radius: 2px;
}
.asset-item:hover {
  background: var(--bg-hover); color: var(--text-primary);
}
</style>
