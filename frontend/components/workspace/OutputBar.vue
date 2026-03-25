<template>
  <div class="h-full flex" style="background: var(--bg-secondary)">
    <!-- Progress + thumbnails -->
    <div class="flex-1 overflow-hidden flex flex-col">
      <!-- Step progress -->
      <div v-if="store.running || hasResults" class="px-3 py-1.5 flex gap-1 shrink-0" style="border-bottom: 1px solid var(--border)">
        <div
          v-for="node in store.nodes"
          :key="node.id"
          class="flex items-center gap-1 px-2 py-0.5 rounded text-[10px]"
          :style="{ background: stepBg(node.name), color: stepColor(node.name) }"
        >
          <div v-if="store.stepStatuses[node.name] === 'running'" class="w-2 h-2 border border-t-transparent rounded-full animate-spin" style="border-color: var(--accent); border-top-color: transparent" />
          <div v-else-if="store.stepStatuses[node.name] === 'done'" class="w-1.5 h-1.5 rounded-full" style="background: var(--success)" />
          <div v-else class="w-1.5 h-1.5 rounded-full" style="background: var(--text-muted)" />
          <span>{{ node.name }}</span>
          <span v-if="store.stepDurations[node.name]" class="mono" style="color: var(--text-muted)">{{ store.stepDurations[node.name].toFixed(1) }}s</span>
        </div>
      </div>

      <!-- Output thumbnails -->
      <div class="flex-1 overflow-x-auto flex items-center gap-1.5 px-3">
        <div
          v-for="(output, i) in store.outputs"
          :key="i"
          @click="store.selectedOutputIndex = i"
          class="shrink-0 cursor-pointer rounded overflow-hidden transition-opacity"
          :style="{ opacity: i === store.selectedOutputIndex ? 1 : 0.5, border: i === store.selectedOutputIndex ? '1px solid var(--accent)' : '1px solid var(--border)' }"
        >
          <img :src="output.url" class="h-28 w-auto" />
        </div>
        <div v-if="!store.outputs.length" class="text-[11px]" style="color: var(--text-muted)">
          {{ store.running ? 'Generating...' : 'Output images will appear here' }}
        </div>
      </div>
    </div>

    <!-- Preview (selected output) -->
    <div class="w-48 shrink-0 flex items-center justify-center p-2" style="border-left: 1px solid var(--border)">
      <img
        v-if="store.selectedOutput"
        :src="store.selectedOutput.url"
        class="max-h-full max-w-full rounded"
        style="border: 1px solid var(--border)"
      />
      <span v-else class="text-[10px]" style="color: var(--text-muted)">Preview</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useWorkspaceStore } from '~/stores/workspace'

const store = useWorkspaceStore()

const hasResults = computed(() => Object.keys(store.stepStatuses).length > 0)

function stepBg(name: string) {
  const s = store.stepStatuses[name]
  if (s === 'running') return 'rgba(232, 138, 42, 0.15)'
  if (s === 'done') return 'rgba(63, 185, 80, 0.1)'
  if (s === 'error') return 'rgba(248, 81, 73, 0.1)'
  return 'transparent'
}

function stepColor(name: string) {
  const s = store.stepStatuses[name]
  if (s === 'running') return 'var(--accent)'
  if (s === 'done') return 'var(--success)'
  if (s === 'error') return 'var(--error)'
  return 'var(--text-muted)'
}
</script>
