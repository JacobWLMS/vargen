<template>
  <div>
    <div class="flex items-center gap-3 mb-6">
      <h2 class="text-lg font-semibold">Models</h2>
      <button @click="refresh" class="px-3 py-1.5 text-xs rounded-lg bg-gray-800 hover:bg-gray-700">Refresh</button>
    </div>

    <div v-if="status" class="grid grid-cols-3 gap-4 mb-8">
      <div class="p-4 rounded-xl bg-gray-900 border border-gray-800">
        <p class="text-xs text-gray-500 mb-1">VRAM Total</p>
        <p class="text-2xl font-bold">{{ status.vram_total_mb }}MB</p>
      </div>
      <div class="p-4 rounded-xl bg-gray-900 border border-gray-800">
        <p class="text-xs text-gray-500 mb-1">VRAM Free</p>
        <p class="text-2xl font-bold" :class="vramFreeColor">{{ status.vram_free_mb }}MB</p>
      </div>
      <div class="p-4 rounded-xl bg-gray-900 border border-gray-800">
        <p class="text-xs text-gray-500 mb-1">Loaded Models</p>
        <p class="text-2xl font-bold">{{ status.loaded_models?.length || 0 }}</p>
      </div>
    </div>

    <div v-if="status?.cache_dir" class="mb-6">
      <p class="text-sm text-gray-500">Cache: <code class="text-gray-400">{{ status.cache_dir }}</code></p>
    </div>

    <div v-if="status?.loaded_models?.length" class="space-y-2">
      <h3 class="text-sm font-medium text-gray-400">Currently Loaded</h3>
      <div v-for="m in status.loaded_models" :key="m" class="p-3 rounded-lg bg-gray-900 border border-gray-800 text-sm">
        {{ m }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const api = useApi()
const status = ref<any>(null)

const vramFreeColor = computed(() => {
  if (!status.value) return ''
  const pct = status.value.vram_free_mb / status.value.vram_total_mb
  if (pct > 0.5) return 'text-green-400'
  if (pct > 0.2) return 'text-yellow-400'
  return 'text-red-400'
})

async function refresh() {
  status.value = await api.getModelStatus()
}

onMounted(refresh)
</script>
