<template>
  <div class="w-72 shrink-0 flex flex-col overflow-hidden" style="background: var(--bg-panel); border-left: 1px solid var(--border)">
    <template v-if="node">
      <!-- Header -->
      <div class="px-3 py-2 flex items-center gap-2 shrink-0" style="border-bottom: 1px solid var(--border)">
        <div class="w-2 h-2 rounded-full" :style="{ background: typeColor }" />
        <span class="text-[12px] font-medium" style="color: var(--text-primary)">{{ node.type }}</span>
        <button @click="store.removeNode(node.id)" class="ml-auto text-[10px] px-1.5 py-0.5 rounded" style="color: var(--error)" @mouseenter="($event.target as HTMLElement).style.background = 'rgba(248,81,73,0.1)'" @mouseleave="($event.target as HTMLElement).style.background = 'transparent'">Delete</button>
      </div>

      <!-- Properties -->
      <div class="flex-1 overflow-y-auto p-3 space-y-3 text-[12px]">
        <!-- Name -->
        <div>
          <label style="color: var(--text-muted)">Name</label>
          <input v-model="node.name" class="w-full px-2 py-1 mt-0.5" />
        </div>

        <!-- Model -->
        <div>
          <label style="color: var(--text-muted)">Model</label>
          <input v-model="node.model" class="w-full px-2 py-1 mt-0.5 mono text-[11px]" placeholder="model name" />
        </div>

        <!-- Type-specific params -->
        <template v-if="node.type === 'vision-llm'">
          <Field label="Prompt" v-model="node.params.prompt" type="textarea" />
          <Field label="Prepend" v-model="node.params.prepend" type="textarea" />
          <Field label="Append" v-model="node.params.append" type="textarea" />
          <Slider label="Max tokens" v-model="node.params.max_tokens" :min="64" :max="2048" :step="64" />
        </template>

        <template v-if="node.type === 'txt2img' || node.type === 'img2img'">
          <Field label="Prompt" v-model="node.params.prompt" type="textarea" />
          <Field label="Negative" v-model="node.params.negative" type="textarea" />
          <div class="flex gap-2">
            <Field label="Width" v-model.number="node.params.width" type="number" class="flex-1" />
            <Field label="Height" v-model.number="node.params.height" type="number" class="flex-1" />
          </div>
          <Slider label="Steps" v-model="node.params.steps" :min="1" :max="50" :step="1" />
          <Slider label="Guidance" v-model="node.params.guidance" :min="0" :max="20" :step="0.5" :decimals="1" />
          <Field label="Seed" v-model.number="node.params.seed" type="number" hint="-1 = random" />
          <Slider v-if="node.type === 'img2img'" label="Denoise" v-model="node.params.denoise" :min="0" :max="1" :step="0.05" :decimals="2" />
          <Slider label="Batch" v-model="node.params.batch_count" :min="1" :max="100" :step="1" />
        </template>

        <template v-if="node.type === 'pixel-upscale'">
          <div>
            <label style="color: var(--text-muted)">Scale</label>
            <select v-model.number="node.params.scale" class="w-full px-2 py-1 mt-0.5">
              <option :value="2">2x</option>
              <option :value="4">4x</option>
            </select>
          </div>
        </template>
      </div>
    </template>

    <!-- No selection -->
    <div v-else class="flex-1 flex flex-col items-center justify-center gap-2">
      <p class="text-[11px]" style="color: var(--text-muted)">No step selected</p>
      <p class="text-[10px]" style="color: var(--text-muted)">Double-click canvas to add</p>
    </div>

    <!-- Input image -->
    <div class="shrink-0 p-3" style="border-top: 1px solid var(--border)">
      <p class="text-[11px] font-semibold uppercase tracking-wider mb-1.5" style="color: var(--text-muted)">Input Image</p>
      <div
        @click="openFilePicker"
        @drop.prevent="onImageDrop"
        @dragover.prevent
        class="rounded cursor-pointer overflow-hidden"
        style="border: 1px dashed var(--border)"
      >
        <img v-if="store.inputImage" :src="store.inputImage.previewUrl" class="w-full" />
        <div v-else class="py-4 text-center text-[10px]" style="color: var(--text-muted)">
          Drop or click
        </div>
      </div>
      <input ref="fileInput" type="file" accept="image/*" class="hidden" @change="onFileSelect" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { useWorkspaceStore } from '~/stores/workspace'

const store = useWorkspaceStore()
const fileInput = ref()

const node = computed(() => store.selectedNode)

const typeColors: Record<string, string> = {
  'vision-llm': '#5eead4', 'txt2img': '#e88a2a', 'img2img': '#a882ff',
  'refine': '#a882ff', 'pixel-upscale': '#60a5fa', 'inpaint': '#f472b6',
}
const typeColor = computed(() => typeColors[node.value?.type || ''] || '#444')

function openFilePicker() { fileInput.value?.click() }

function onFileSelect(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (file) uploadImage(file)
}

function onImageDrop(e: DragEvent) {
  const file = e.dataTransfer?.files?.[0]
  if (file?.type.startsWith('image/')) uploadImage(file)
}

async function uploadImage(file: File) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch('/api/upload', { method: 'POST', body: form })
  if (res.ok) {
    const data = await res.json()
    store.inputImage = { filename: data.filename, previewUrl: URL.createObjectURL(file) }
  }
}
</script>

<script lang="ts">
// Inline sub-components
const Field = defineComponent({
  props: ['label', 'modelValue', 'type', 'hint'],
  emits: ['update:modelValue'],
  template: `
    <div>
      <label style="color: var(--text-muted)" class="text-[11px]">{{ label }}</label>
      <textarea v-if="type === 'textarea'" :value="modelValue" @input="$emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)" class="w-full px-2 py-1 mt-0.5 text-[11px]" rows="2" />
      <input v-else :type="type || 'text'" :value="modelValue" @input="$emit('update:modelValue', type === 'number' ? Number(($event.target as HTMLInputElement).value) : ($event.target as HTMLInputElement).value)" class="w-full px-2 py-1 mt-0.5" />
      <p v-if="hint" class="text-[9px] mt-0.5" style="color: var(--text-muted)">{{ hint }}</p>
    </div>
  `,
})

const Slider = defineComponent({
  props: ['label', 'modelValue', 'min', 'max', 'step', 'decimals'],
  emits: ['update:modelValue'],
  template: `
    <div class="flex items-center gap-2">
      <label class="text-[11px] w-16 shrink-0" style="color: var(--text-muted)">{{ label }}</label>
      <input type="range" :min="min" :max="max" :step="step" :value="modelValue" @input="$emit('update:modelValue', parseFloat(($event.target as HTMLInputElement).value))" class="flex-1 h-1 rounded-full appearance-none cursor-pointer" style="background: var(--bg-active); accent-color: var(--accent)" />
      <span class="mono text-[10px] w-8 text-right" style="color: var(--text-secondary)">{{ (modelValue ?? 0).toFixed(decimals ?? 0) }}</span>
    </div>
  `,
})
</script>
