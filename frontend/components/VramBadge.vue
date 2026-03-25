<template>
  <div v-if="status" class="flex items-center gap-1.5 text-[11px] mono" style="color: var(--text-muted)">
    <div class="w-1.5 h-1.5 rounded-full" :style="{ background: vramColor }" />
    {{ status.vram_free_mb }}MB / {{ status.vram_total_mb }}MB
  </div>
</template>

<script setup lang="ts">
const { getModelStatus } = useApi()
const status = ref<any>(null)

const vramColor = computed(() => {
  if (!status.value?.vram_free_mb) return 'var(--text-muted)'
  const pct = status.value.vram_free_mb / status.value.vram_total_mb
  if (pct > 0.5) return 'var(--success)'
  if (pct > 0.2) return 'var(--warning)'
  return 'var(--error)'
})

let interval: ReturnType<typeof setInterval>

onMounted(async () => {
  try { status.value = await getModelStatus() } catch {}
  interval = setInterval(async () => {
    try { status.value = await getModelStatus() } catch {}
  }, 10000)
})

onUnmounted(() => clearInterval(interval))
</script>
