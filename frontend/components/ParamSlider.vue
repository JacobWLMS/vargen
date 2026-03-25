<template>
  <div class="flex items-center gap-2">
    <label class="text-[11px] w-20 shrink-0" style="color: var(--text-muted)">{{ label }}</label>
    <input
      type="range"
      :min="min"
      :max="max"
      :step="step"
      :value="modelValue"
      @input="$emit('update:modelValue', parseFloat(($event.target as HTMLInputElement).value))"
      class="flex-1 h-1 rounded-full appearance-none cursor-pointer"
      style="background: var(--bg-active); accent-color: var(--accent)"
    />
    <span class="mono text-[11px] w-10 text-right" style="color: var(--text-secondary)">{{ display }}</span>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  label: string
  modelValue: number
  min: number
  max: number
  step: number
  decimals?: number
}>()

defineEmits(['update:modelValue'])

const display = computed(() => {
  const d = props.decimals ?? (props.step < 1 ? 1 : 0)
  return props.modelValue.toFixed(d)
})
</script>
