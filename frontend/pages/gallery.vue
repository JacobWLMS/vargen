<template>
  <div class="h-full flex flex-col">
    <div class="h-9 flex items-center px-3 shrink-0" style="border-bottom: 1px solid var(--border)">
      <span class="text-[12px]" style="color: var(--text-secondary)">{{ outputs.length }} images</span>
      <button @click="refresh" class="btn btn-ghost text-[11px] ml-auto">Refresh</button>
    </div>

    <div class="flex-1 overflow-y-auto p-3">
      <div v-if="outputs.length" class="grid grid-cols-3 md:grid-cols-5 lg:grid-cols-8 gap-1.5">
        <div
          v-for="img in outputs"
          :key="img.filename"
          @click="selected = img"
          class="cursor-pointer group"
        >
          <img
            :src="api.outputUrl(img.filename)"
            class="w-full aspect-square object-cover rounded transition-opacity group-hover:opacity-80"
            style="border: 1px solid var(--border)"
            loading="lazy"
          />
        </div>
      </div>
      <div v-else class="h-full flex items-center justify-center">
        <p class="text-[12px]" style="color: var(--text-muted)">No outputs yet</p>
      </div>
    </div>

    <!-- Lightbox -->
    <Teleport to="body">
      <div
        v-if="selected"
        @click.self="selected = null"
        class="fixed inset-0 z-50 flex items-center justify-center p-8"
        style="background: rgba(0,0,0,0.95)"
      >
        <button
          @click="selected = null"
          class="absolute top-4 right-4 text-[20px]"
          style="color: var(--text-muted)"
        >&times;</button>
        <img
          :src="api.outputUrl(selected.filename)"
          class="max-h-[90vh] max-w-[90vw] rounded"
        />
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
const api = useApi()
const outputs = ref<any[]>([])
const selected = ref<any>(null)

async function refresh() {
  try { outputs.value = await api.listOutputs() } catch {}
}

onMounted(refresh)
</script>
