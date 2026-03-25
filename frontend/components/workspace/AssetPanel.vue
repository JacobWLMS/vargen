<template>
  <div class="w-full flex flex-col overflow-hidden" style="background: var(--bg-panel); border-right: 1px solid var(--border)">
    <!-- Search -->
    <div class="px-2 py-1.5 shrink-0" style="border-bottom: 1px solid var(--border)">
      <input v-model="search" placeholder="Search..." class="w-full px-2 py-1 text-[11px]" />
    </div>

    <!-- Sections -->
    <div class="flex-1 overflow-y-auto">
      <!-- Node Types -->
      <Section title="Nodes" :count="filteredNodeTypes.length">
        <div
          v-for="nt in filteredNodeTypes"
          :key="nt.type_id"
          draggable="true"
          @dragstart="e => { e.dataTransfer!.setData('vargen/node-type', nt.type_id); e.dataTransfer!.effectAllowed = 'copy' }"
          class="asset-item"
        >
          <span class="w-2 h-2 rounded-full shrink-0" :style="{ background: nt.color }" />
          <span class="flex-1 truncate">{{ nt.label }}</span>
        </div>
      </Section>

      <!-- Models by category -->
      <Section v-for="(models, cat) in filteredModels" :key="cat" :title="cat" :count="models.length">
        <div
          v-for="m in models"
          :key="m.name"
          draggable="true"
          @dragstart="e => { e.dataTransfer!.setData('vargen/model', JSON.stringify({ ...m, category: cat })); e.dataTransfer!.effectAllowed = 'copy' }"
          class="asset-item"
        >
          <span class="w-1.5 h-1.5 rounded-full shrink-0" :style="{ background: fmtColor(m.format) }" />
          <span class="flex-1 truncate">{{ m.name }}</span>
          <span class="text-[9px] mono shrink-0" style="color: var(--text-muted)">{{ m.size_mb }}MB</span>
        </div>
      </Section>

      <!-- Workflows -->
      <Section title="Workflows" :count="workflows.length">
        <div v-for="w in workflows" :key="w.id" @click="store.loadWorkflow(w.id)" class="asset-item cursor-pointer">
          <span class="flex-1 truncate">{{ w.name }}</span>
          <span class="text-[9px] mono shrink-0" style="color: var(--text-muted)">{{ w.nodes }}n</span>
        </div>
      </Section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useWorkspaceStore } from '~/stores/workspace'
const store = useWorkspaceStore()
const search = ref('')
const workflows = ref<any[]>([])

const filteredNodeTypes = computed(() => {
  const all = Object.values(store.nodeTypes) as any[]
  if (!search.value) return all
  return all.filter((n: any) => n.label.toLowerCase().includes(search.value.toLowerCase()))
})

const filteredModels = computed(() => {
  const result: Record<string, any[]> = {}
  for (const [cat, models] of Object.entries(store.modelInventory)) {
    const filtered = (models as any[]).filter(m =>
      !search.value || m.name.toLowerCase().includes(search.value.toLowerCase())
    )
    if (filtered.length) result[cat] = filtered.slice(0, 50) // cap for performance
  }
  return result
})

function fmtColor(fmt: string) {
  return { safetensors: 'var(--success)', gguf: '#60a5fa', bin: 'var(--warning)' }[fmt] || 'var(--text-muted)'
}

onMounted(async () => {
  try { workflows.value = await (await fetch('/api/workflows')).json() } catch {}
})

// Inline section component
const Section = defineComponent({
  props: ['title', 'count'],
  setup(props, { slots }) {
    const open = ref(true)
    return () => h('div', {}, [
      h('button', {
        class: 'w-full px-2 py-1 flex items-center gap-1.5 text-left',
        style: 'border-bottom: 1px solid var(--border)',
        onClick: () => open.value = !open.value,
      }, [
        h('span', { class: 'text-[9px]', style: 'color: var(--text-muted)' }, open.value ? '▼' : '▶'),
        h('span', { class: 'text-[10px] uppercase tracking-wider flex-1', style: 'color: var(--text-muted)' }, props.title),
        h('span', { class: 'text-[9px] mono', style: 'color: var(--text-muted)' }, props.count),
      ]),
      open.value ? h('div', { class: 'py-0.5' }, slots.default?.()) : null,
    ])
  },
})
</script>

<style>
.asset-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 8px;
  font-size: 11px;
  color: var(--text-secondary);
  cursor: grab;
  border-radius: 2px;
}
.asset-item:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}
</style>
