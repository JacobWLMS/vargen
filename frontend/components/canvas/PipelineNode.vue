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
      <div class="flex items-center gap-1.5 px-2.5 py-1.5" style="border-bottom: 1px solid rgba(255,255,255,0.05)">
        <div class="w-2 h-2 rounded-full shrink-0" :style="{ background: dotColor }" />
        <span class="text-[11px] font-medium flex-1 truncate" style="color: var(--text-primary)">{{ nodeDef?.label || node.type }}</span>
        <div v-if="status === 'running'" class="w-3 h-3 border border-t-transparent rounded-full animate-spin" style="border-color: var(--accent); border-top-color: transparent" />
        <div v-else-if="status === 'done'" class="w-2.5 h-2.5 rounded-full" style="background: var(--success)" />
        <div v-else-if="status === 'error'" class="w-2.5 h-2.5 rounded-full" style="background: var(--error)" />
      </div>

      <!-- Widgets (rendered inline on the node) -->
      <div v-if="nodeDef?.widgets?.length" class="px-2 py-1.5 space-y-1.5">
        <div v-for="w in nodeDef.widgets" :key="w.name">
          <!-- Combo / Select -->
          <template v-if="w.type === 'combo'">
            <label class="text-[9px] uppercase tracking-wider" style="color: var(--text-muted)">{{ w.label }}</label>
            <select
              :value="node.params[w.name] ?? w.default"
              @change.stop="setWidget(w.name, ($event.target as HTMLSelectElement).value)"
              class="w-full px-1.5 py-0.5 text-[10px]"
              @mousedown.stop
            >
              <option value="">Select...</option>
              <option v-for="opt in getComboOptions(w)" :key="opt" :value="opt">{{ opt }}</option>
            </select>
          </template>

          <!-- Slider -->
          <template v-else-if="w.type === 'slider'">
            <div class="flex items-center gap-1">
              <label class="text-[9px] w-14 shrink-0 truncate" style="color: var(--text-muted)">{{ w.label }}</label>
              <input
                type="range" :min="w.min" :max="w.max" :step="w.step"
                :value="node.params[w.name] ?? w.default"
                @input.stop="setWidget(w.name, parseFloat(($event.target as HTMLInputElement).value))"
                @mousedown.stop
                class="flex-1 h-0.5 appearance-none cursor-pointer"
                style="accent-color: var(--accent); background: var(--bg-active)"
              />
              <span class="mono text-[9px] w-8 text-right shrink-0" style="color: var(--text-secondary)">
                {{ formatVal(node.params[w.name] ?? w.default, w) }}
              </span>
            </div>
          </template>

          <!-- Number -->
          <template v-else-if="w.type === 'number'">
            <div class="flex items-center gap-1">
              <label class="text-[9px] w-14 shrink-0 truncate" style="color: var(--text-muted)">{{ w.label }}</label>
              <input
                type="number" :min="w.min" :max="w.max" :step="w.step"
                :value="node.params[w.name] ?? w.default"
                @input.stop="setWidget(w.name, Number(($event.target as HTMLInputElement).value))"
                @mousedown.stop @focus.stop
                class="flex-1 px-1 py-0.5 text-[10px] mono"
              />
            </div>
          </template>

          <!-- Text -->
          <template v-else-if="w.type === 'text'">
            <label class="text-[9px] uppercase tracking-wider" style="color: var(--text-muted)">{{ w.label }}</label>
            <input
              :value="node.params[w.name] ?? w.default"
              @input.stop="setWidget(w.name, ($event.target as HTMLInputElement).value)"
              @mousedown.stop @focus.stop
              class="w-full px-1.5 py-0.5 text-[10px]"
              :placeholder="w.label"
            />
          </template>

          <!-- Textarea -->
          <template v-else-if="w.type === 'textarea'">
            <label class="text-[9px] uppercase tracking-wider" style="color: var(--text-muted)">{{ w.label }}</label>
            <textarea
              :value="node.params[w.name] ?? w.default"
              @input.stop="setWidget(w.name, ($event.target as HTMLTextAreaElement).value)"
              @mousedown.stop @focus.stop
              class="w-full px-1.5 py-0.5 text-[10px] resize-y"
              rows="3"
              :placeholder="w.label"
            />
          </template>
        </div>
      </div>

      <!-- Duration -->
      <div v-if="duration" class="px-2.5 pb-1">
        <span class="text-[9px] mono" style="color: var(--text-muted)">{{ duration.toFixed(1) }}s</span>
      </div>

      <!-- Input ports (left side) -->
      <div v-if="nodeDef?.inputs?.length" class="absolute left-0 top-0 h-full flex flex-col justify-center gap-2 -translate-x-1/2" style="padding-top: 30px">
        <div v-for="port in nodeDef.inputs" :key="port.name" class="relative group">
          <div
            class="w-3 h-3 rounded-full cursor-pointer"
            :style="{ background: portColor(port.type), border: '1.5px solid ' + portBorder(port.type) }"
            :title="port.name + ' (' + port.type + ')'"
          />
          <span class="absolute left-4 top-1/2 -translate-y-1/2 text-[8px] whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none" :style="{ color: portColor(port.type) }">{{ port.name }}</span>
        </div>
      </div>

      <!-- Output ports (right side) -->
      <div v-if="nodeDef?.outputs?.length" class="absolute right-0 top-0 h-full flex flex-col justify-center gap-2 translate-x-1/2" style="padding-top: 30px">
        <div v-for="port in nodeDef.outputs" :key="port.name" class="relative group">
          <div
            class="w-3 h-3 rounded-full cursor-pointer"
            :style="{ background: portColor(port.type), border: '1.5px solid ' + portBorder(port.type) }"
            :title="port.name + ' (' + port.type + ')'"
            @mousedown.left.stop="$emit('startConnect', $event)"
          />
          <span class="absolute right-4 top-1/2 -translate-y-1/2 text-[8px] whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none" :style="{ color: portColor(port.type) }">{{ port.name }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useWorkspaceStore, type GraphNode } from '~/stores/workspace'

const store = useWorkspaceStore()

const props = defineProps<{
  node: GraphNode
  selected: boolean
  status?: string
  duration?: number
}>()

const emit = defineEmits(['select', 'move', 'startConnect'])

const nodeDef = computed(() => store.nodeTypes[props.node.type])

// Drag
let isDragging = false
let lastX = 0, lastY = 0
function onMouseDown(e: MouseEvent) {
  emit('select')
  isDragging = true
  lastX = e.clientX; lastY = e.clientY
  const onMove = (e: MouseEvent) => {
    if (!isDragging) return
    emit('move', e.clientX - lastX, e.clientY - lastY)
    lastX = e.clientX; lastY = e.clientY
  }
  const onUp = () => { isDragging = false; window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp) }
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
}

function setWidget(name: string, value: any) {
  props.node.params[name] = value
}

function getComboOptions(w: any): string[] {
  // For model-related combos, populate from model inventory
  if (w.name === 'checkpoint') return getModelNames('checkpoints', 'diffusion_models')
  if (w.name === 'lora') return getModelNames('loras')
  if (w.name === 'model' && props.node.type === 'load_upscale_model') return getModelNames('upscale_models')
  if (w.name === 'sampler' || w.name === 'scheduler') return w.options || []
  return w.options || []
}

function getModelNames(...categories: string[]): string[] {
  const names: string[] = []
  for (const cat of categories) {
    const models = (store.modelInventory[cat] || []) as any[]
    for (const m of models) names.push(m.name)
  }
  return names
}

function formatVal(val: any, w: any): string {
  if (val === null || val === undefined) return ''
  const num = Number(val)
  if (isNaN(num)) return String(val)
  if (w.step && w.step < 1) return num.toFixed(2)
  return String(num)
}

// Port type colors (matching ComfyUI conventions)
const PORT_COLORS: Record<string, string> = {
  MODEL: '#b380ff', CLIP: '#ffd500', VAE: '#ff6060',
  CONDITIONING: '#ffa040', LATENT: '#ff80c0', IMAGE: '#60a0ff',
  MASK: '#40ff40', UPSCALE_MODEL: '#60a0ff', STRING: '#80ff80',
  INT: '#60d060', FLOAT: '#60d060',
}
function portColor(type: string) { return PORT_COLORS[type] || '#666' }
function portBorder(type: string) { return PORT_COLORS[type] || '#444' }

// Node colors
const COLORS: Record<string, { dot: string; bg: string; border: string }> = {
  load_checkpoint: { dot: '#b380ff', bg: 'rgba(60, 30, 80, 0.7)', border: 'rgba(179, 128, 255, 0.25)' },
  load_lora: { dot: '#b380ff', bg: 'rgba(60, 30, 80, 0.7)', border: 'rgba(179, 128, 255, 0.25)' },
  load_image: { dot: '#60a0ff', bg: 'rgba(15, 30, 60, 0.7)', border: 'rgba(96, 160, 255, 0.25)' },
  empty_latent: { dot: '#ff80c0', bg: 'rgba(60, 20, 40, 0.7)', border: 'rgba(255, 128, 192, 0.25)' },
  load_upscale_model: { dot: '#60a0ff', bg: 'rgba(15, 30, 60, 0.7)', border: 'rgba(96, 160, 255, 0.25)' },
  clip_text_encode: { dot: '#ffd500', bg: 'rgba(60, 50, 10, 0.7)', border: 'rgba(255, 213, 0, 0.25)' },
  clip_set_last_layer: { dot: '#ffd500', bg: 'rgba(60, 50, 10, 0.7)', border: 'rgba(255, 213, 0, 0.25)' },
  conditioning_combine: { dot: '#ffa040', bg: 'rgba(60, 35, 10, 0.7)', border: 'rgba(255, 160, 64, 0.25)' },
  ksampler: { dot: '#e88a2a', bg: 'rgba(60, 35, 10, 0.7)', border: 'rgba(232, 138, 42, 0.25)' },
  save_image: { dot: '#22c55e', bg: 'rgba(10, 40, 20, 0.7)', border: 'rgba(34, 197, 94, 0.25)' },
  preview_image: { dot: '#22c55e', bg: 'rgba(10, 40, 20, 0.7)', border: 'rgba(34, 197, 94, 0.25)' },
  upscale_with_model: { dot: '#60a0ff', bg: 'rgba(15, 30, 60, 0.7)', border: 'rgba(96, 160, 255, 0.25)' },
  image_scale: { dot: '#60a0ff', bg: 'rgba(15, 30, 60, 0.7)', border: 'rgba(96, 160, 255, 0.25)' },
}
const dotColor = computed(() => COLORS[props.node.type]?.dot || nodeDef.value?.color || '#666')
const bg = computed(() => COLORS[props.node.type]?.bg || 'var(--bg-panel)')
const borderCol = computed(() => COLORS[props.node.type]?.border || 'var(--border)')
</script>

<style>
.pipeline-node {
  width: 220px;
  border: 1px solid;
  border-radius: 4px;
  position: relative;
}
.pipeline-node:hover {
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.05);
}
.pipeline-node input, .pipeline-node select, .pipeline-node textarea {
  font-size: 10px !important;
  padding: 2px 4px !important;
  border-radius: 2px !important;
  background: rgba(0,0,0,0.3) !important;
  border: 1px solid rgba(255,255,255,0.08) !important;
}
.pipeline-node input:focus, .pipeline-node select:focus, .pipeline-node textarea:focus {
  border-color: var(--accent) !important;
}
.pipeline-node input[type="range"] {
  border: none !important;
  padding: 0 !important;
  background: transparent !important;
}
</style>
