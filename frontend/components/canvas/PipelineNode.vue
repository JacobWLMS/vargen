<template>
  <div
    class="absolute select-none"
    :style="{ left: node.x + 'px', top: node.y + 'px' }"
    @mousedown.left.stop="onMouseDown"
  >
    <div
      class="pipeline-node"
      :class="{ 'selected': selected }"
      :style="{ background: bg, borderColor: borderCol }"
    >
      <!-- Type stripe -->
      <div class="h-[3px] rounded-t-[3px] -mt-px -mx-px" :style="{ background: dotColor }" />

      <!-- Header -->
      <div class="node-header">
        <div class="w-2 h-2 rounded-full shrink-0" :style="{ background: dotColor }" />
        <span class="text-[11px] font-medium flex-1 truncate" style="color: var(--text-primary)">{{ nodeDef?.label || node.type }}</span>
        <div v-if="status === 'running'" class="w-3 h-3 border border-t-transparent rounded-full animate-spin" style="border-color: var(--accent); border-top-color: transparent" />
        <div v-else-if="status === 'done'" class="w-2.5 h-2.5 rounded-full" style="background: var(--success)" />
        <div v-else-if="status === 'error'" class="w-2.5 h-2.5 rounded-full" style="background: var(--error)" />
      </div>

      <!-- Widgets -->
      <div v-if="nodeDef?.widgets?.length" class="node-body">
        <div v-for="w in nodeDef.widgets" :key="w.name" class="node-widget">
          <!-- Combo -->
          <template v-if="w.type === 'combo'">
            <label class="node-label">{{ w.label }}</label>
            <select
              :value="node.params[w.name] ?? w.default"
              @change.stop="setWidget(w.name, ($event.target as HTMLSelectElement).value)"
              @mousedown.stop
            >
              <option value="">Select...</option>
              <option v-for="opt in getComboOptions(w)" :key="opt" :value="opt">{{ opt }}</option>
            </select>
          </template>

          <!-- Slider -->
          <template v-else-if="w.type === 'slider'">
            <div class="node-slider-row">
              <label class="node-label-inline">{{ w.label }}</label>
              <input
                type="range" :min="w.min" :max="w.max" :step="w.step"
                :value="node.params[w.name] ?? w.default"
                @input.stop="setWidget(w.name, parseFloat(($event.target as HTMLInputElement).value))"
                @mousedown.stop
              />
              <span class="node-slider-val">{{ formatVal(node.params[w.name] ?? w.default, w) }}</span>
            </div>
          </template>

          <!-- Number -->
          <template v-else-if="w.type === 'number'">
            <div class="node-slider-row">
              <label class="node-label-inline">{{ w.label }}</label>
              <input
                type="number" :min="w.min" :max="w.max" :step="w.step"
                :value="node.params[w.name] ?? w.default"
                @input.stop="setWidget(w.name, Number(($event.target as HTMLInputElement).value))"
                @mousedown.stop @focus.stop
              />
            </div>
          </template>

          <!-- Text -->
          <template v-else-if="w.type === 'text'">
            <label class="node-label">{{ w.label }}</label>
            <input
              :value="node.params[w.name] ?? w.default"
              @input.stop="setWidget(w.name, ($event.target as HTMLInputElement).value)"
              @mousedown.stop @focus.stop
              :placeholder="w.label"
            />
          </template>

          <!-- Textarea -->
          <template v-else-if="w.type === 'textarea'">
            <label class="node-label">{{ w.label }}</label>
            <textarea
              :value="node.params[w.name] ?? w.default"
              @input.stop="setWidget(w.name, ($event.target as HTMLTextAreaElement).value)"
              @mousedown.stop @focus.stop
              rows="3" :placeholder="w.label"
            />
          </template>
        </div>
      </div>

      <!-- Duration -->
      <div v-if="duration" class="px-2 pb-1">
        <span class="text-[9px] mono" style="color: var(--text-muted)">{{ duration.toFixed(1) }}s</span>
      </div>

      <!-- Input ports (left) -->
      <div v-if="nodeDef?.inputs?.length" class="port-column port-column-left">
        <div v-for="(port, i) in nodeDef.inputs" :key="port.name" class="port-row">
          <div class="port-dot" :style="{ background: portColor(port.type), borderColor: portColor(port.type) }"
               :data-node-id="node.id" :data-port-name="port.name" :data-port-dir="'in'" />
          <span class="port-label port-label-left" :style="{ color: portColor(port.type) }">{{ port.name }}</span>
        </div>
      </div>

      <!-- Output ports (right) -->
      <div v-if="nodeDef?.outputs?.length" class="port-column port-column-right">
        <div v-for="(port, i) in nodeDef.outputs" :key="port.name" class="port-row port-row-right">
          <span class="port-label port-label-right" :style="{ color: portColor(port.type) }">{{ port.name }}</span>
          <div class="port-dot" :style="{ background: portColor(port.type), borderColor: portColor(port.type) }"
               :data-node-id="node.id" :data-port-name="port.name" :data-port-dir="'out'"
               @mousedown.left.stop="$emit('startConnect', port.name, $event)" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useWorkspaceStore, type GraphNode } from '~/stores/workspace'
const store = useWorkspaceStore()

const props = defineProps<{ node: GraphNode; selected: boolean; status?: string; duration?: number }>()
const emit = defineEmits(['select', 'move', 'startConnect'])

const nodeDef = computed(() => store.nodeTypes[props.node.type])

let isDragging = false, lastX = 0, lastY = 0
function onMouseDown(e: MouseEvent) {
  emit('select')
  isDragging = true; lastX = e.clientX; lastY = e.clientY
  const onMove = (e: MouseEvent) => { if (!isDragging) return; emit('move', e.clientX - lastX, e.clientY - lastY); lastX = e.clientX; lastY = e.clientY }
  const onUp = () => { isDragging = false; window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp) }
  window.addEventListener('mousemove', onMove); window.addEventListener('mouseup', onUp)
}

function setWidget(name: string, value: any) { props.node.params[name] = value }

function getComboOptions(w: any): string[] {
  if (w.name === 'checkpoint') return getModelNames('checkpoints', 'diffusion_models')
  if (w.name === 'lora') return getModelNames('loras')
  if (w.name === 'model' && props.node.type === 'load_upscale_model') return getModelNames('upscale_models')
  return w.options || []
}

function getModelNames(...cats: string[]): string[] {
  const names: string[] = []
  for (const cat of cats) for (const m of (store.modelInventory[cat] || []) as any[]) names.push(m.name)
  return names
}

function formatVal(val: any, w: any): string {
  const n = Number(val); if (isNaN(n)) return String(val ?? '')
  return w.step && w.step < 1 ? n.toFixed(2) : String(n)
}

const PORT_COLORS: Record<string, string> = {
  MODEL: '#b380ff', CLIP: '#ffd500', VAE: '#ff6060', CONDITIONING: '#ffa040',
  LATENT: '#ff80c0', IMAGE: '#60a0ff', MASK: '#40ff40', UPSCALE_MODEL: '#60a0ff',
  STRING: '#80ff80', INT: '#60d060', FLOAT: '#60d060',
}
function portColor(type: string) { return PORT_COLORS[type] || '#666' }

const COLORS: Record<string, { dot: string; bg: string; border: string }> = {
  load_checkpoint: { dot: '#b380ff', bg: 'rgba(60,30,80,0.7)', border: 'rgba(179,128,255,0.25)' },
  load_lora: { dot: '#b380ff', bg: 'rgba(60,30,80,0.7)', border: 'rgba(179,128,255,0.25)' },
  load_image: { dot: '#60a0ff', bg: 'rgba(15,30,60,0.7)', border: 'rgba(96,160,255,0.25)' },
  empty_latent: { dot: '#ff80c0', bg: 'rgba(60,20,40,0.7)', border: 'rgba(255,128,192,0.25)' },
  load_upscale_model: { dot: '#60a0ff', bg: 'rgba(15,30,60,0.7)', border: 'rgba(96,160,255,0.25)' },
  clip_text_encode: { dot: '#ffd500', bg: 'rgba(60,50,10,0.7)', border: 'rgba(255,213,0,0.25)' },
  clip_set_last_layer: { dot: '#ffd500', bg: 'rgba(60,50,10,0.7)', border: 'rgba(255,213,0,0.25)' },
  conditioning_combine: { dot: '#ffa040', bg: 'rgba(60,35,10,0.7)', border: 'rgba(255,160,64,0.25)' },
  ksampler: { dot: '#e88a2a', bg: 'rgba(60,35,10,0.7)', border: 'rgba(232,138,42,0.25)' },
  save_image: { dot: '#22c55e', bg: 'rgba(10,40,20,0.7)', border: 'rgba(34,197,94,0.25)' },
  preview_image: { dot: '#22c55e', bg: 'rgba(10,40,20,0.7)', border: 'rgba(34,197,94,0.25)' },
  upscale_with_model: { dot: '#60a0ff', bg: 'rgba(15,30,60,0.7)', border: 'rgba(96,160,255,0.25)' },
  image_scale: { dot: '#60a0ff', bg: 'rgba(15,30,60,0.7)', border: 'rgba(96,160,255,0.25)' },
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
  overflow: visible;
}
.pipeline-node:hover { box-shadow: 0 0 0 1px rgba(255,255,255,0.08); }
.pipeline-node.selected { box-shadow: 0 0 0 2px var(--accent), 0 0 12px rgba(232,138,42,0.2); }

.node-header {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 10px;
  border-bottom: 1px solid rgba(255,255,255,0.05);
}
.node-body { padding: 6px 8px; }
.node-widget { margin-bottom: 4px; }
.node-widget:last-child { margin-bottom: 0; }

.node-label {
  display: block; font-size: 9px; text-transform: uppercase;
  letter-spacing: 0.04em; color: var(--text-muted); margin-bottom: 2px;
}
.node-label-inline {
  font-size: 9px; color: var(--text-muted); width: 50px; flex-shrink: 0; white-space: nowrap; overflow: hidden;
}

.node-slider-row {
  display: flex; align-items: center; gap: 4px;
}
.node-slider-val {
  font-family: monospace; font-size: 9px; color: var(--text-secondary);
  width: 32px; text-align: right; flex-shrink: 0;
}

/* Inputs within nodes */
.pipeline-node select,
.pipeline-node input:not([type="range"]),
.pipeline-node textarea {
  width: 100% !important;
  box-sizing: border-box !important;
  font-size: 10px !important;
  padding: 2px 4px !important;
  border-radius: 2px !important;
  background: rgba(0,0,0,0.3) !important;
  border: 1px solid rgba(255,255,255,0.08) !important;
  color: var(--text-primary) !important;
}
.pipeline-node input:focus, .pipeline-node select:focus, .pipeline-node textarea:focus {
  border-color: var(--accent) !important;
}
.pipeline-node input[type="range"] {
  flex: 1 !important;
  min-width: 0 !important;
  height: 3px !important;
  appearance: none !important; -webkit-appearance: none !important;
  background: var(--bg-active) !important;
  border: none !important; padding: 0 !important;
  border-radius: 2px !important;
  accent-color: var(--accent);
  cursor: pointer;
}
.pipeline-node input[type="number"] {
  width: auto !important; flex: 1 !important; min-width: 0 !important;
}
.pipeline-node textarea {
  resize: vertical !important; min-height: 40px !important;
}

/* Ports */
.port-column {
  position: absolute; top: 0; height: 100%;
  display: flex; flex-direction: column; justify-content: center; gap: 6px;
  padding-top: 28px;
}
.port-column-left { left: -5px; }
.port-column-right { right: -5px; }

.port-row { display: flex; align-items: center; gap: 3px; height: 14px; }
.port-row-right { flex-direction: row-reverse; text-align: right; }

.port-dot {
  width: 10px; height: 10px; border-radius: 50%;
  border: 1.5px solid; cursor: pointer; flex-shrink: 0;
  transition: transform 0.1s;
}
.port-dot:hover { transform: scale(1.3); }

.port-label {
  font-size: 8px; white-space: nowrap; pointer-events: none;
}
.port-label-left { margin-left: 2px; }
.port-label-right { margin-right: 2px; }
</style>
