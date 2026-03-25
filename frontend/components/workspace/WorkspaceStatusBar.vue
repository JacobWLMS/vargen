<template>
  <div class="h-6 flex items-center px-3 shrink-0 text-[11px] select-none" style="background: var(--accent); color: #000">
    <span class="font-medium">vargen</span>
    <span class="mx-2 opacity-40">|</span>
    <span class="opacity-60">{{ store.pipelineName }}.yaml</span>
    <span class="mx-2 opacity-40">|</span>
    <span class="opacity-60">{{ store.nodes.length }} steps</span>
    <span class="mx-2 opacity-40">|</span>
    <span>{{ status }}</span>
    <span class="ml-auto mono opacity-60">{{ store.vramFree }} / {{ store.vramTotal }} MB</span>
  </div>
</template>

<script setup lang="ts">
import { useWorkspaceStore } from '~/stores/workspace'

const store = useWorkspaceStore()

const status = computed(() => {
  if (store.running) {
    const running = Object.entries(store.stepStatuses).find(([_, s]) => s === 'running')
    return running ? `Running: ${running[0]}` : 'Running...'
  }
  const done = Object.values(store.stepStatuses).filter(s => s === 'done').length
  if (done > 0) return `Complete (${done} steps)`
  return 'Ready'
})
</script>
