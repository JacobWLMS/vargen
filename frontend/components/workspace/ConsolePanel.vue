<template>
  <div ref="container" class="overflow-y-auto p-2 mono text-[11px] leading-relaxed" style="background: var(--bg-primary)">
    <div v-for="(line, i) in store.consoleLogs" :key="i" :style="{ color: lineColor(line) }">
      <span style="color: var(--text-muted)">{{ line.time }}</span>
      <span class="mx-1" :style="{ color: levelColor(line.level) }">[{{ line.level }}]</span>
      {{ line.message }}
    </div>
    <div v-if="!store.consoleLogs.length" style="color: var(--text-muted)">Console output will appear here</div>
  </div>
</template>

<script setup lang="ts">
import { useWorkspaceStore } from '~/stores/workspace'

const store = useWorkspaceStore()
const container = ref<HTMLElement>()

watch(() => store.consoleLogs.length, () => {
  nextTick(() => {
    if (container.value) container.value.scrollTop = container.value.scrollHeight
  })
})

function lineColor(line: any) {
  if (line.level === 'error') return 'var(--error)'
  if (line.level === 'warn') return 'var(--warning)'
  return 'var(--text-secondary)'
}

function levelColor(level: string) {
  if (level === 'error') return 'var(--error)'
  if (level === 'warn') return 'var(--warning)'
  if (level === 'info') return 'var(--accent)'
  return 'var(--text-muted)'
}
</script>
