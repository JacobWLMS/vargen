<template>
  <div
    class="absolute select-none"
    :style="{ left: node.x + 'px', top: node.y + 'px' }"
    @mousedown.left.stop="onMouseDown"
  >
    <div
      class="pipeline-node"
      :class="{ 'ring-1 ring-[var(--accent)]': selected }"
      :style="{ background: bg, borderColor: borderCol }"
    >
      <!-- Type stripe -->
      <div class="h-[3px] rounded-t-[3px] -mt-px -mx-px" :style="{ background: dotColor }" />

      <!-- Header -->
      <div class="flex items-center gap-1.5 px-2.5 py-1.5">
        <div class="w-2 h-2 rounded-full shrink-0" :style="{ background: dotColor }" />
        <span class="text-[11px] font-medium flex-1 truncate" style="color: var(--text-primary)">{{ node.name }}</span>
        <!-- Status -->
        <div v-if="status === 'running'" class="w-3 h-3 border border-t-transparent rounded-full animate-spin" style="border-color: var(--accent); border-top-color: transparent" />
        <div v-else-if="status === 'done'" class="w-2.5 h-2.5 rounded-full" style="background: var(--success)" />
        <div v-else-if="status === 'error'" class="w-2.5 h-2.5 rounded-full" style="background: var(--error)" />
      </div>

      <!-- Body -->
      <div class="px-2.5 pb-2 space-y-0.5">
        <p v-if="node.model" class="text-[10px] truncate" style="color: var(--text-muted)">
          <span style="color: var(--text-secondary)">model:</span> {{ node.model }}
        </p>
        <p v-for="(val, key) in summaryParams" :key="key" class="text-[10px] truncate" style="color: var(--text-muted)">
          <span style="color: var(--text-secondary)">{{ key }}:</span> {{ val }}
        </p>
        <p v-if="duration" class="text-[9px] mono" style="color: var(--text-muted)">{{ duration.toFixed(1) }}s</p>
      </div>

      <!-- Ports -->
      <div
        class="absolute left-0 top-1/2 -translate-x-1/2 -translate-y-1/2 w-3 h-3 rounded-full cursor-pointer"
        style="background: var(--bg-active); border: 1.5px solid var(--text-muted)"
        title="Input"
      />
      <div
        class="absolute right-0 top-1/2 translate-x-1/2 -translate-y-1/2 w-3 h-3 rounded-full cursor-pointer"
        style="background: var(--bg-active); border: 1.5px solid var(--text-muted)"
        title="Output"
        @mousedown.left.stop="$emit('startConnect', $event)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { GraphNode } from '~/stores/workspace'

const props = defineProps<{
  node: GraphNode
  selected: boolean
  status?: string
  duration?: number
}>()

const emit = defineEmits(['select', 'move', 'startConnect'])

// Drag state
let isDragging = false
let lastX = 0, lastY = 0

function onMouseDown(e: MouseEvent) {
  emit('select')
  isDragging = true
  lastX = e.clientX
  lastY = e.clientY

  const onMove = (e: MouseEvent) => {
    if (!isDragging) return
    const dx = e.clientX - lastX
    const dy = e.clientY - lastY
    lastX = e.clientX
    lastY = e.clientY
    emit('move', dx, dy)
  }

  const onUp = () => {
    isDragging = false
    window.removeEventListener('mousemove', onMove)
    window.removeEventListener('mouseup', onUp)
  }

  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
}

const colors: Record<string, { dot: string; bg: string; border: string }> = {
  'vision-llm': { dot: '#5eead4', bg: 'rgba(17, 44, 39, 0.7)', border: 'rgba(94, 234, 212, 0.25)' },
  'txt2img': { dot: '#e88a2a', bg: 'rgba(50, 30, 10, 0.7)', border: 'rgba(232, 138, 42, 0.25)' },
  'img2img': { dot: '#a882ff', bg: 'rgba(35, 20, 55, 0.7)', border: 'rgba(168, 130, 255, 0.25)' },
  'refine': { dot: '#a882ff', bg: 'rgba(35, 20, 55, 0.7)', border: 'rgba(168, 130, 255, 0.25)' },
  'pixel-upscale': { dot: '#60a5fa', bg: 'rgba(15, 25, 50, 0.7)', border: 'rgba(96, 165, 250, 0.25)' },
  'inpaint': { dot: '#f472b6', bg: 'rgba(50, 15, 35, 0.7)', border: 'rgba(244, 114, 182, 0.25)' },
  'face-detail': { dot: '#fb923c', bg: 'rgba(50, 30, 10, 0.7)', border: 'rgba(251, 146, 60, 0.25)' },
}

const dotColor = computed(() => colors[props.node.type]?.dot || '#444')
const bg = computed(() => colors[props.node.type]?.bg || 'var(--bg-panel)')
const borderCol = computed(() => colors[props.node.type]?.border || 'var(--border)')

const summaryParams = computed(() => {
  const p = props.node.params
  const result: Record<string, string> = {}
  const show = ['steps', 'guidance', 'width', 'height', 'scale', 'denoise', 'batch_count']
  for (const key of show) {
    if (p[key] !== undefined && p[key] !== '' && !(key === 'batch_count' && p[key] === 1)) {
      result[key] = String(p[key])
    }
  }
  // Show truncated prompt
  if (p.prompt && typeof p.prompt === 'string') {
    const prompt = p.prompt.length > 25 ? p.prompt.slice(0, 25) + '...' : p.prompt
    result.prompt = prompt
  }
  return result
})
</script>

<style>
.pipeline-node {
  width: 180px;
  border: 1px solid;
  border-radius: 4px;
  position: relative;
  transition: box-shadow 0.15s;
}
.pipeline-node:hover {
  box-shadow: 0 0 0 1px rgba(232, 138, 42, 0.15);
}
</style>
