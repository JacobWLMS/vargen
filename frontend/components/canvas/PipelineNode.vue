<template>
  <div
    class="absolute select-none"
    :style="{ left: node.x + 'px', top: node.y + 'px' }"
    @mousedown.left.stop="onMouseDown"
  >
    <div
      class="pipeline-node"
      :class="{ selected }"
      :style="{ background: bg, borderColor: borderCol }"
    >
      <!-- Type stripe -->
      <div class="type-stripe" :style="{ background: dotColor }" />

      <!-- Header -->
      <div class="node-header">
        <div class="w-2 h-2 rounded-full shrink-0" :style="{ background: dotColor }" />
        <span class="node-title">{{ nodeDef?.label || node.type }}</span>
        <div v-if="status === 'running'" class="spinner" />
        <div v-else-if="status === 'done'" class="status-dot" style="background: var(--success)" />
        <div v-else-if="status === 'error'" class="status-dot" style="background: var(--error)" />
      </div>

      <!-- Input ports (inside node, top section) -->
      <div v-if="nodeDef?.inputs?.length" class="port-section">
        <div v-for="port in nodeDef.inputs" :key="port.name" class="port-row-in">
          <div class="port-dot-edge port-dot-left"
               :style="{ background: portColor(port.type) }"
               :data-node-id="node.id" :data-port-name="port.name" :data-port-dir="'in'" />
          <span class="port-text" :style="{ color: portColor(port.type) }">{{ port.name }}</span>
        </div>
      </div>

      <!-- Widgets -->
      <div v-if="nodeDef?.widgets?.length" class="node-body">
        <div v-for="w in nodeDef.widgets" :key="w.name" class="node-widget">
          <template v-if="w.type === 'combo'">
            <label class="wlabel">{{ w.label }}</label>
            <select :value="node.params[w.name] ?? w.default"
              @change.stop="setWidget(w.name, ($event.target as HTMLSelectElement).value)"
              @mousedown.stop>
              <option value="">Select...</option>
              <option v-for="opt in getComboOptions(w)" :key="opt" :value="opt">{{ opt }}</option>
            </select>
          </template>

          <template v-else-if="w.type === 'slider'">
            <div class="slider-row">
              <span class="slider-label">{{ w.label }}</span>
              <input type="range" :min="w.min" :max="w.max" :step="w.step"
                :value="node.params[w.name] ?? w.default"
                @input.stop="setWidget(w.name, parseFloat(($event.target as HTMLInputElement).value))"
                @mousedown.stop />
              <span class="slider-val">{{ fmtVal(node.params[w.name] ?? w.default, w) }}</span>
            </div>
          </template>

          <template v-else-if="w.type === 'number'">
            <div class="slider-row">
              <span class="slider-label">{{ w.label }}</span>
              <input type="number" :min="w.min" :max="w.max" :step="w.step"
                :value="node.params[w.name] ?? w.default"
                @input.stop="setWidget(w.name, Number(($event.target as HTMLInputElement).value))"
                @mousedown.stop @focus.stop />
            </div>
          </template>

          <template v-else-if="w.type === 'text'">
            <label class="wlabel">{{ w.label }}</label>
            <input :value="node.params[w.name] ?? w.default"
              @input.stop="setWidget(w.name, ($event.target as HTMLInputElement).value)"
              @mousedown.stop @focus.stop :placeholder="w.label" />
          </template>

          <template v-else-if="w.type === 'textarea'">
            <label class="wlabel">{{ w.label }}</label>
            <textarea :value="node.params[w.name] ?? w.default"
              @input.stop="setWidget(w.name, ($event.target as HTMLTextAreaElement).value)"
              @mousedown.stop @focus.stop rows="3" :placeholder="w.label" />
          </template>
        </div>
      </div>

      <!-- Load Image: drop zone -->
      <div v-if="node.type === 'load_image'" class="node-body">
        <div
          class="image-drop"
          @click.stop="$refs.imgInput?.click()"
          @drop.prevent.stop="onImageDrop"
          @dragover.prevent.stop
        >
          <img v-if="store.inputImage?.previewUrl" :src="store.inputImage.previewUrl" class="image-preview" />
          <span v-else>Drop image or click</span>
        </div>
        <input ref="imgInput" type="file" accept="image/*" style="display:none" @change="onImageSelect" />
      </div>

      <!-- Output ports (inside node, bottom section) -->
      <div v-if="nodeDef?.outputs?.length" class="port-section port-section-out">
        <div v-for="port in nodeDef.outputs" :key="port.name" class="port-row-out">
          <span class="port-text port-text-right" :style="{ color: portColor(port.type) }">{{ port.name }}</span>
          <div class="port-dot-edge port-dot-right"
               :style="{ background: portColor(port.type) }"
               :data-node-id="node.id" :data-port-name="port.name" :data-port-dir="'out'"
               @mousedown.left.stop="$emit('startConnect', port.name, $event)" />
        </div>
      </div>

      <!-- Duration -->
      <div v-if="duration" class="node-footer">{{ duration.toFixed(1) }}s</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useWorkspaceStore, type GraphNode } from '~/stores/workspace'
const store = useWorkspaceStore()
const props = defineProps<{ node: GraphNode; selected: boolean; status?: string; duration?: number }>()
const emit = defineEmits(['select', 'move', 'startConnect'])
const imgInput = ref()
const nodeDef = computed(() => store.nodeTypes[props.node.type])

let isDragging = false, lastX = 0, lastY = 0
function onMouseDown(e: MouseEvent) {
  emit('select'); isDragging = true; lastX = e.clientX; lastY = e.clientY
  const onMove = (e: MouseEvent) => { if (!isDragging) return; emit('move', e.clientX - lastX, e.clientY - lastY); lastX = e.clientX; lastY = e.clientY }
  const onUp = () => { isDragging = false; window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp) }
  window.addEventListener('mousemove', onMove); window.addEventListener('mouseup', onUp)
}
function setWidget(n: string, v: any) { props.node.params[n] = v }
function getComboOptions(w: any): string[] {
  if (w.name === 'checkpoint') return getModelNames('checkpoints', 'diffusion_models')
  if (w.name === 'lora') return getModelNames('loras')
  if (w.name === 'model' && props.node.type === 'load_upscale_model') return getModelNames('upscale_models')
  if (w.name === 'model' && props.node.type === 'load_controlnet') return getModelNames('controlnet')
  if (w.name === 'model' && props.node.type === 'load_flux') return getModelNames('diffusion_models', 'checkpoints')
  return w.options || []
}
function getModelNames(...cats: string[]): string[] {
  return cats.flatMap(c => ((store.modelInventory[c] || []) as any[]).map(m => m.name))
}
function fmtVal(v: any, w: any): string { const n = Number(v); return isNaN(n) ? '' : (w.step && w.step < 1 ? n.toFixed(2) : String(n)) }

async function onImageDrop(e: DragEvent) {
  const file = e.dataTransfer?.files?.[0]
  if (file?.type.startsWith('image/')) await uploadImg(file)
}
async function onImageSelect(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (file) await uploadImg(file)
}
async function uploadImg(file: File) {
  const form = new FormData(); form.append('file', file)
  const res = await fetch('/api/upload', { method: 'POST', body: form })
  if (res.ok) {
    const data = await res.json()
    store.inputImage = { filename: data.filename, previewUrl: URL.createObjectURL(file) }
  }
}

const PORT_COLORS: Record<string, string> = {
  MODEL: '#b380ff', CLIP: '#ffd500', VAE: '#ff6060', CONDITIONING: '#ffa040',
  LATENT: '#ff80c0', IMAGE: '#60a0ff', MASK: '#40ff40', UPSCALE_MODEL: '#60a0ff',
}
function portColor(t: string) { return PORT_COLORS[t] || '#666' }

// Auto-generate bg/border from the node type's accent color (from API)
function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace('#', '')
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]
}

const accentColor = computed(() => nodeDef.value?.color || '#666666')
const dotColor = accentColor
const bg = computed(() => '#0f0f0f')
const borderCol = computed(() => {
  const [r, g, b] = hexToRgb(accentColor.value)
  return `rgba(${r}, ${g}, ${b}, 0.2)`
})
</script>

<style>
.pipeline-node {
  width: 220px; border: 1px solid; border-radius: 4px; position: relative;
}
.pipeline-node:hover { box-shadow: 0 0 0 1px rgba(255,255,255,0.06); }
.pipeline-node.selected { box-shadow: 0 0 0 2px var(--accent), 0 0 12px rgba(232,138,42,0.15); }

.type-stripe { height: 3px; border-radius: 3px 3px 0 0; margin: -1px -1px 0; }
.node-header { display: flex; align-items: center; gap: 6px; padding: 5px 8px; border-bottom: 1px solid rgba(255,255,255,0.04); }
.node-title { font-size: 11px; font-weight: 600; color: var(--text-primary); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.spinner { width: 12px; height: 12px; border: 1.5px solid var(--accent); border-top-color: transparent; border-radius: 50%; animation: spin 0.6s linear infinite; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; }
@keyframes spin { to { transform: rotate(360deg); } }

.node-body { padding: 4px 8px; }
.node-widget { margin-bottom: 3px; }
.node-widget:last-child { margin-bottom: 0; }
.node-footer { padding: 2px 8px 4px; font: 9px monospace; color: var(--text-muted); }

.wlabel { display: block; font-size: 9px; color: var(--text-muted); margin-bottom: 1px; text-transform: uppercase; letter-spacing: 0.03em; }

.slider-row { display: flex; align-items: center; gap: 3px; }
.slider-label { font-size: 9px; color: var(--text-muted); width: 48px; flex-shrink: 0; overflow: hidden; white-space: nowrap; }
.slider-val { font: 9px monospace; color: var(--text-secondary); width: 30px; text-align: right; flex-shrink: 0; }

/* Inputs */
.pipeline-node select, .pipeline-node input:not([type="range"]), .pipeline-node textarea {
  width: 100% !important; box-sizing: border-box !important; font-size: 10px !important;
  padding: 2px 4px !important; border-radius: 2px !important;
  background: rgba(0,0,0,0.3) !important; border: 1px solid rgba(255,255,255,0.06) !important;
  color: var(--text-primary) !important; outline: none !important;
}
.pipeline-node input:focus, .pipeline-node select:focus, .pipeline-node textarea:focus { border-color: var(--accent) !important; }
.pipeline-node input[type="range"] {
  flex: 1 !important; min-width: 0 !important; height: 3px !important;
  -webkit-appearance: none !important; appearance: none !important;
  background: rgba(255,255,255,0.06) !important; border: none !important; padding: 0 !important;
  border-radius: 1px !important; accent-color: var(--accent); cursor: pointer;
}
.pipeline-node input[type="number"] { width: auto !important; flex: 1 !important; min-width: 0 !important; }
.pipeline-node textarea { resize: vertical !important; min-height: 36px !important; }

/* Ports — inside node */
.port-section { padding: 2px 0; border-bottom: 1px solid rgba(255,255,255,0.04); }
.port-section-out { border-bottom: none; border-top: 1px solid rgba(255,255,255,0.04); }

.port-row-in, .port-row-out { display: flex; align-items: center; height: 16px; position: relative; }
.port-row-in { padding-left: 14px; }
.port-row-out { padding-right: 14px; justify-content: flex-end; }

.port-text { font-size: 9px; }
.port-text-right { text-align: right; }

.port-dot-edge {
  width: 8px; height: 8px; border-radius: 50%; position: absolute; cursor: pointer;
  transition: transform 0.1s, box-shadow 0.1s;
}
.port-dot-edge:hover { transform: scale(1.4); box-shadow: 0 0 6px currentColor; }
.port-dot-left { left: -4px; }
.port-dot-right { right: -4px; }

/* Load Image drop zone */
.image-drop {
  border: 1px dashed rgba(255,255,255,0.1); border-radius: 3px; padding: 8px;
  text-align: center; font-size: 10px; color: var(--text-muted); cursor: pointer;
  min-height: 40px; display: flex; align-items: center; justify-content: center;
}
.image-drop:hover { border-color: var(--accent); color: var(--text-secondary); }
.image-preview { max-width: 100%; max-height: 80px; border-radius: 2px; }
</style>
