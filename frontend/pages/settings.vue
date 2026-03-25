<template>
  <div class="h-full flex flex-col">
    <div class="h-9 flex items-center px-3 shrink-0" style="border-bottom: 1px solid var(--border)">
      <span class="text-[12px]" style="color: var(--text-secondary)">Settings</span>
      <button @click="save" class="btn btn-primary ml-auto text-[11px]">Save</button>
    </div>

    <div class="flex-1 overflow-y-auto p-4 max-w-2xl">
      <div v-if="settings" class="space-y-6">
        <!-- Model Paths -->
        <div class="panel">
          <div class="panel-header">Model Directories</div>
          <div class="p-3 space-y-2">
            <p class="text-[11px]" style="color: var(--text-muted)">
              Directories to scan for models. Uses the same structure as ComfyUI (checkpoints/, loras/, vae/, etc.)
            </p>
            <div v-for="(path, i) in settings.model_paths" :key="i" class="flex gap-2 items-center">
              <input :value="path" @input="settings.model_paths[i] = ($event.target as HTMLInputElement).value" class="flex-1 px-2 py-1 mono text-[11px]" />
              <button @click="settings.model_paths.splice(i, 1)" class="btn btn-danger text-[10px]">Remove</button>
            </div>
            <button @click="settings.model_paths.push('')" class="btn btn-ghost text-[11px]">+ Add Path</button>
          </div>
        </div>

        <!-- VRAM Mode -->
        <div class="panel">
          <div class="panel-header">VRAM Management</div>
          <div class="p-3">
            <select v-model="settings.vram_mode" class="w-full px-2 py-1.5 text-[12px]">
              <option value="aggressive">Aggressive offload (lowest VRAM, slowest)</option>
              <option value="balanced">Balanced (recommended for 8GB)</option>
              <option value="keep_loaded">Keep loaded (fastest, needs more VRAM)</option>
            </select>
          </div>
        </div>

        <!-- Defaults -->
        <div class="panel">
          <div class="panel-header">Default Generation Parameters</div>
          <div class="p-3 space-y-2">
            <ParamSlider v-model="settings.defaults.steps" label="Steps" :min="1" :max="50" :step="1" />
            <ParamSlider v-model="settings.defaults.guidance" label="Guidance" :min="0" :max="20" :step="0.5" :decimals="1" />
            <div class="flex gap-2">
              <div class="flex-1">
                <label class="text-[11px]" style="color: var(--text-muted)">Width</label>
                <input v-model.number="settings.defaults.width" type="number" class="w-full px-2 py-1 mt-0.5" />
              </div>
              <div class="flex-1">
                <label class="text-[11px]" style="color: var(--text-muted)">Height</label>
                <input v-model.number="settings.defaults.height" type="number" class="w-full px-2 py-1 mt-0.5" />
              </div>
            </div>
          </div>
        </div>
      </div>

      <p v-if="saveStatus" class="mt-3 text-[11px]" :style="{ color: saveStatus.startsWith('Error') ? 'var(--error)' : 'var(--success)' }">
        {{ saveStatus }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
const settings = ref<any>(null)
const saveStatus = ref('')

onMounted(async () => {
  try {
    const res = await fetch('/api/settings')
    if (res.ok) settings.value = await res.json()
  } catch {}
})

async function save() {
  try {
    const res = await fetch('/api/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings.value),
    })
    if (res.ok) {
      saveStatus.value = 'Saved'
      setTimeout(() => saveStatus.value = '', 2000)
    } else {
      saveStatus.value = `Error: ${res.status}`
    }
  } catch (e: any) {
    saveStatus.value = `Error: ${e.message}`
  }
}
</script>
