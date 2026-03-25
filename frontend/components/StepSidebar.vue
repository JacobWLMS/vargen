<template>
  <div v-if="step" class="h-full overflow-y-auto" style="background: var(--bg-panel)">
    <div class="panel-header flex items-center gap-2">
      <div class="w-2 h-2 rounded-full" :style="{ background: typeColor }" />
      <span>{{ step.name || 'Untitled' }}</span>
      <button @click="$emit('delete')" class="btn btn-danger ml-auto text-[10px]">Delete</button>
    </div>

    <div class="p-3 space-y-3 text-[12px]">
      <!-- Common fields -->
      <div>
        <label style="color: var(--text-muted)">Step name</label>
        <input v-model="step.name" class="w-full px-2 py-1 mt-0.5" @input="emit" />
      </div>

      <div>
        <label style="color: var(--text-muted)">Type</label>
        <select v-model="step.type" class="w-full px-2 py-1 mt-0.5" @change="emit">
          <option v-for="t in stepTypes" :key="t" :value="t">{{ t }}</option>
        </select>
      </div>

      <ModelSelect v-model="step.model" label="Model" :categories="modelCategories" @update:model-value="emit" />

      <!-- Type-specific fields -->
      <template v-if="step.type === 'vision-llm'">
        <div>
          <label style="color: var(--text-muted)">Prompt</label>
          <textarea v-model="step.params.prompt" class="w-full px-2 py-1 mt-0.5 text-[11px]" rows="3" @input="emit" />
        </div>
        <div>
          <label style="color: var(--text-muted)">Prepend tags</label>
          <textarea v-model="step.params.prepend" class="w-full px-2 py-1 mt-0.5 text-[11px]" rows="2" @input="emit" />
        </div>
        <div>
          <label style="color: var(--text-muted)">Append tags</label>
          <textarea v-model="step.params.append" class="w-full px-2 py-1 mt-0.5 text-[11px]" rows="2" @input="emit" />
        </div>
        <ParamSlider v-model="step.params.max_tokens" label="Max tokens" :min="64" :max="2048" :step="64" @update:model-value="emit" />
      </template>

      <template v-if="step.type === 'txt2img' || step.type === 'img2img'">
        <div>
          <label style="color: var(--text-muted)">Prompt</label>
          <textarea v-model="step.params.prompt" class="w-full px-2 py-1 mt-0.5 text-[11px]" rows="2" @input="emit" />
        </div>
        <div>
          <label style="color: var(--text-muted)">Negative</label>
          <textarea v-model="step.params.negative" class="w-full px-2 py-1 mt-0.5 text-[11px]" rows="2" @input="emit" />
        </div>
        <div class="flex gap-2">
          <div class="flex-1">
            <label style="color: var(--text-muted)">Width</label>
            <input v-model.number="step.params.width" type="number" class="w-full px-2 py-1 mt-0.5" @input="emit" />
          </div>
          <div class="flex-1">
            <label style="color: var(--text-muted)">Height</label>
            <input v-model.number="step.params.height" type="number" class="w-full px-2 py-1 mt-0.5" @input="emit" />
          </div>
        </div>
        <ParamSlider v-model="step.params.steps" label="Steps" :min="1" :max="50" :step="1" @update:model-value="emit" />
        <ParamSlider v-model="step.params.guidance" label="Guidance" :min="0" :max="20" :step="0.5" :decimals="1" @update:model-value="emit" />
        <div>
          <label style="color: var(--text-muted)">Seed</label>
          <input v-model.number="step.params.seed" type="number" class="w-full px-2 py-1 mt-0.5" @input="emit" />
          <p class="text-[10px] mt-0.5" style="color: var(--text-muted)">-1 = random</p>
        </div>
        <ParamSlider v-if="step.type === 'img2img'" v-model="step.params.denoise" label="Denoise" :min="0" :max="1" :step="0.05" :decimals="2" @update:model-value="emit" />
        <ParamSlider v-model="step.params.batch_count" label="Batch" :min="1" :max="100" :step="1" @update:model-value="emit" />

        <!-- Modifiers -->
        <div class="mt-2 pt-2" style="border-top: 1px solid var(--border)">
          <p class="text-[11px] font-medium mb-2" style="color: var(--text-muted)">MODIFIERS</p>
          <button @click="toggleModifier('ip_adapter')" class="btn btn-ghost w-full text-left text-[11px] mb-1">
            {{ step.params.ip_adapter ? '- Remove IP-Adapter' : '+ IP-Adapter' }}
          </button>
          <button @click="toggleModifier('controlnet')" class="btn btn-ghost w-full text-left text-[11px] mb-1">
            {{ step.params.controlnet ? '- Remove ControlNet' : '+ ControlNet' }}
          </button>
          <button @click="addLora" class="btn btn-ghost w-full text-left text-[11px]">+ LoRA</button>
        </div>
      </template>

      <template v-if="step.type === 'pixel-upscale'">
        <div>
          <label style="color: var(--text-muted)">Scale</label>
          <select v-model.number="step.params.scale" class="w-full px-2 py-1 mt-0.5" @change="emit">
            <option :value="2">2x</option>
            <option :value="4">4x</option>
          </select>
        </div>
      </template>
    </div>
  </div>
  <div v-else class="h-full flex items-center justify-center" style="background: var(--bg-panel)">
    <p class="text-[11px]" style="color: var(--text-muted)">Select a step to edit</p>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{ step: any | null }>()
const emitEvent = defineEmits(['update', 'delete'])

const stepTypes = ['vision-llm', 'txt2img', 'img2img', 'refine', 'pixel-upscale', 'inpaint', 'face-detail', 'remove-bg']

const typeColor = computed(() => {
  const colors: Record<string, string> = {
    'vision-llm': '#5eead4', 'txt2img': '#e88a2a', 'img2img': '#a882ff',
    'refine': '#a882ff', 'pixel-upscale': '#60a5fa', 'inpaint': '#f472b6',
    'face-detail': '#fb923c', 'remove-bg': '#34d399',
  }
  return colors[props.step?.type] || '#444'
})

const modelCategories = computed(() => {
  const map: Record<string, string[]> = {
    'vision-llm': ['checkpoints'],
    'txt2img': ['checkpoints', 'diffusion_models'],
    'img2img': ['checkpoints', 'diffusion_models'],
    'refine': ['checkpoints', 'diffusion_models'],
    'pixel-upscale': ['upscale_models'],
  }
  return map[props.step?.type] || []
})

function emit() { emitEvent('update') }

function toggleModifier(mod: string) {
  if (!props.step) return
  if (props.step.params[mod]) {
    delete props.step.params[mod]
  } else {
    props.step.params[mod] = { model: '', weight: 0.8 }
  }
  emit()
}

function addLora() {
  if (!props.step) return
  if (!props.step.params.loras) props.step.params.loras = []
  props.step.params.loras.push({ model: '', weight: 0.7 })
  emit()
}
</script>
