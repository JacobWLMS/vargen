<template>
  <div class="h-full flex flex-col overflow-hidden" style="background: var(--bg-panel); border-left: 1px solid var(--border)">
    <div class="h-7 flex items-center px-2 shrink-0" style="border-bottom: 1px solid var(--border)">
      <span class="text-[11px]" style="color: var(--text-muted)">YAML</span>
      <span class="ml-2 text-[10px] mono" style="color: var(--text-muted)">{{ store.pipelineName }}.yaml</span>
      <button @click="applyYaml" class="btn btn-ghost text-[10px] ml-auto">Apply</button>
    </div>
    <textarea
      ref="editor"
      v-model="yamlText"
      class="flex-1 p-3 mono text-[11px] leading-relaxed resize-none outline-none"
      style="background: var(--bg-primary) !important; border: none !important; color: var(--text-primary)"
      spellcheck="false"
      @input="dirty = true"
    />
  </div>
</template>

<script setup lang="ts">
import { useWorkspaceStore } from '~/stores/workspace'
const store = useWorkspaceStore()
const yamlText = ref('')
const dirty = ref(false)

// Sync from store to editor when graph changes (and not dirty)
watch(() => [store.nodes, store.edges], () => {
  if (!dirty.value) {
    yamlText.value = store.toYaml()
  }
}, { deep: true, immediate: true })

// Also update when panel opens
onMounted(() => {
  yamlText.value = store.toYaml()
})

function applyYaml() {
  store.fromYaml(yamlText.value)
  dirty.value = false
  store.log('info', 'Applied YAML to graph')
}
</script>
