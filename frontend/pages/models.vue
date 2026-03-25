<template>
  <div class="h-full flex flex-col">
    <div class="h-9 flex items-center px-3 shrink-0" style="border-bottom: 1px solid var(--border)">
      <span class="text-[12px]" style="color: var(--text-secondary)">System</span>
      <button @click="refresh" class="btn btn-ghost text-[11px] ml-auto">Refresh</button>
    </div>

    <div class="flex-1 overflow-y-auto p-4 space-y-4">
      <div v-if="status" class="flex gap-3">
        <div class="panel flex-1 p-3">
          <p class="text-[11px] uppercase tracking-wider" style="color: var(--text-muted)">VRAM Total</p>
          <p class="text-2xl font-light mono mt-1">{{ status.vram_total_mb }}<span class="text-[12px]" style="color: var(--text-muted)">MB</span></p>
        </div>
        <div class="panel flex-1 p-3">
          <p class="text-[11px] uppercase tracking-wider" style="color: var(--text-muted)">VRAM Free</p>
          <p class="text-2xl font-light mono mt-1" :style="{ color: vramColor }">{{ status.vram_free_mb }}<span class="text-[12px]" style="color: var(--text-muted)">MB</span></p>
        </div>
        <div class="panel flex-1 p-3">
          <p class="text-[11px] uppercase tracking-wider" style="color: var(--text-muted)">Loaded</p>
          <p class="text-2xl font-light mono mt-1">{{ status.loaded_models?.length || 0 }}</p>
        </div>
      </div>

      <div v-if="status?.cache_dir" class="panel p-3">
        <p class="text-[11px] uppercase tracking-wider mb-1" style="color: var(--text-muted)">Cache Directory</p>
        <p class="mono text-[12px]" style="color: var(--text-secondary)">{{ status.cache_dir }}</p>
      </div>

      <div v-if="status?.loaded_models?.length" class="panel">
        <div class="panel-header">Loaded Models</div>
        <div class="p-1">
          <div v-for="m in status.loaded_models" :key="m" class="px-3 py-1.5 text-[12px] mono" style="color: var(--text-secondary)">
            {{ m }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const api = useApi()
const status = ref<any>(null)

const vramColor = computed(() => {
  if (!status.value) return 'var(--text-primary)'
  const pct = status.value.vram_free_mb / status.value.vram_total_mb
  if (pct > 0.5) return 'var(--success)'
  if (pct > 0.2) return 'var(--warning)'
  return 'var(--error)'
})

async function refresh() {
  try { status.value = await api.getModelStatus() } catch {}
}
onMounted(refresh)
</script>
