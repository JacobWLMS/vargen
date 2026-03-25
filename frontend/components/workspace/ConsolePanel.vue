<template>
  <div class="h-full flex flex-col" style="background: var(--bg-primary)">
    <!-- Toolbar -->
    <div class="h-6 flex items-center px-2 gap-2 shrink-0" style="border-bottom: 1px solid var(--border)">
      <select v-model="filter" class="text-[10px] px-1 py-0" style="width: auto !important; background: transparent !important; border: none !important; color: var(--text-muted)">
        <option value="all">All</option>
        <option value="info">Info</option>
        <option value="warn">Warnings</option>
        <option value="error">Errors</option>
      </select>
      <span class="text-[9px] mono" style="color: var(--text-muted)">{{ filteredLogs.length }} entries</span>
      <div class="flex-1" />
      <button @click="copyAll" class="text-[9px]" style="color: var(--text-muted)" title="Copy all">Copy</button>
      <button @click="store.consoleLogs = []" class="text-[9px]" style="color: var(--text-muted)" title="Clear">Clear</button>
    </div>

    <!-- Logs -->
    <div ref="container" class="flex-1 overflow-y-auto p-2 mono text-[11px] leading-[1.6]">
      <div v-for="(line, i) in filteredLogs" :key="i" class="log-line" :class="'log-' + line.level">
        <span class="log-time">{{ line.time }}</span>
        <span class="log-level">{{ levelLabel(line.level) }}</span>
        <span>{{ line.message }}</span>
      </div>
      <div v-if="!filteredLogs.length" class="log-empty">
        {{ store.consoleLogs.length ? 'No matching logs' : 'Console output will appear here when you run a workflow' }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useWorkspaceStore } from '~/stores/workspace'

const store = useWorkspaceStore()
const container = ref<HTMLElement>()
const filter = ref('all')

const filteredLogs = computed(() => {
  if (filter.value === 'all') return store.consoleLogs
  return store.consoleLogs.filter(l => l.level === filter.value)
})

watch(() => store.consoleLogs.length, () => {
  nextTick(() => {
    if (container.value) container.value.scrollTop = container.value.scrollHeight
  })
})

function levelLabel(level: string) {
  return { info: 'INF', warn: 'WRN', error: 'ERR', debug: 'DBG' }[level] || level.toUpperCase().slice(0, 3)
}

function copyAll() {
  const text = store.consoleLogs.map(l => `${l.time} [${l.level}] ${l.message}`).join('\n')
  navigator.clipboard.writeText(text)
}
</script>

<style>
.log-line { white-space: pre-wrap; word-break: break-word; }
.log-time { color: var(--text-muted); margin-right: 6px; }
.log-level { margin-right: 6px; font-weight: 600; }
.log-info .log-level { color: var(--accent); }
.log-warn .log-level { color: var(--warning); }
.log-error .log-level { color: var(--error); }
.log-error { color: var(--error); }
.log-warn { color: var(--warning); }
.log-debug .log-level { color: var(--text-muted); }
.log-debug { color: var(--text-muted); }
.log-empty { color: var(--text-muted); padding: 12px 0; text-align: center; }
</style>
