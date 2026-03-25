<template>
  <div v-if="status" class="flex items-center gap-2 text-xs">
    <div class="w-2 h-2 rounded-full" :class="vramColor" />
    <span class="text-gray-500">VRAM: {{ status.vram_free_mb ?? '?' }}MB free / {{ status.vram_total_mb ?? '?' }}MB</span>
  </div>
</template>

<script setup lang="ts">
const { getModelStatus } = useApi()
const status = ref<any>(null)

const vramColor = computed(() => {
  if (!status.value?.vram_free_mb) return 'bg-gray-600'
  const pct = status.value.vram_free_mb / status.value.vram_total_mb
  if (pct > 0.5) return 'bg-green-500'
  if (pct > 0.2) return 'bg-yellow-500'
  return 'bg-red-500'
})

onMounted(async () => {
  try { status.value = await getModelStatus() } catch {}
})

// Poll every 10s
const interval = setInterval(async () => {
  try { status.value = await getModelStatus() } catch {}
}, 10000)

onUnmounted(() => clearInterval(interval))
</script>
