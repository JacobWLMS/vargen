<template>
  <div>
    <label class="text-[11px]" style="color: var(--text-muted)">{{ label }}</label>
    <select
      :value="modelValue"
      @change="$emit('update:modelValue', ($event.target as HTMLSelectElement).value)"
      class="w-full px-2 py-1 mt-0.5 text-[12px]"
    >
      <option value="">Select model...</option>
      <optgroup v-for="(models, cat) in filteredModels" :key="cat" :label="cat">
        <option v-for="m in models" :key="m.name" :value="m.name">
          {{ m.name }} ({{ m.size_mb }}MB)
        </option>
      </optgroup>
    </select>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  label: string
  modelValue: string
  categories?: string[]
}>()

defineEmits(['update:modelValue'])

const { getModelStatus } = useApi()
const allModels = ref<Record<string, any[]>>({})

onMounted(async () => {
  try {
    const res = await fetch('/api/models/browse')
    if (res.ok) allModels.value = await res.json()
  } catch {}
})

const filteredModels = computed(() => {
  if (!props.categories?.length) return allModels.value
  const result: Record<string, any[]> = {}
  for (const cat of props.categories) {
    if (allModels.value[cat]?.length) result[cat] = allModels.value[cat]
  }
  return result
})
</script>
