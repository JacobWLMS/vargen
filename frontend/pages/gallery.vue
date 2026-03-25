<template>
  <div>
    <div class="flex items-center gap-3 mb-6">
      <h2 class="text-lg font-semibold">Gallery</h2>
      <button @click="refresh" class="px-3 py-1.5 text-xs rounded-lg bg-gray-800 hover:bg-gray-700">Refresh</button>
      <span class="text-sm text-gray-500 ml-auto">{{ outputs.length }} images</span>
    </div>

    <div v-if="outputs.length" class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
      <div
        v-for="img in outputs"
        :key="img.filename"
        @click="selected = img"
        class="group cursor-pointer"
      >
        <img
          :src="api.outputUrl(img.filename)"
          class="w-full aspect-square object-cover rounded-lg border border-gray-800 group-hover:border-vargen-500 transition-colors"
          loading="lazy"
        />
        <p class="text-[10px] text-gray-600 mt-1 truncate">{{ img.filename }}</p>
      </div>
    </div>
    <div v-else class="text-center py-20 text-gray-600">
      <p>No generated images yet</p>
      <p class="text-sm mt-1">Run a pipeline to see results here</p>
    </div>

    <!-- Lightbox -->
    <Teleport to="body">
      <div
        v-if="selected"
        @click.self="selected = null"
        class="fixed inset-0 z-50 bg-black/90 flex items-center justify-center p-8"
      >
        <button @click="selected = null" class="absolute top-4 right-4 text-gray-400 hover:text-white text-2xl">&times;</button>
        <img
          :src="api.outputUrl(selected.filename)"
          class="max-h-[90vh] max-w-[90vw] rounded-xl shadow-2xl"
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
  outputs.value = await api.listOutputs()
}

onMounted(refresh)
</script>
