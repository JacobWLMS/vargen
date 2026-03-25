<template>
  <div class="min-h-screen bg-gray-950 text-gray-100">
    <!-- Nav -->
    <nav class="border-b border-gray-800 bg-gray-950/80 backdrop-blur-sm sticky top-0 z-50">
      <div class="max-w-[1800px] mx-auto px-4 h-14 flex items-center gap-6">
        <NuxtLink to="/" class="text-lg font-bold text-vargen-400 tracking-tight">vargen</NuxtLink>
        <div class="flex gap-1">
          <NuxtLink
            v-for="link in links"
            :key="link.to"
            :to="link.to"
            class="px-3 py-1.5 rounded-md text-sm font-medium transition-colors"
            :class="$route.path === link.to
              ? 'bg-gray-800 text-white'
              : 'text-gray-400 hover:text-white hover:bg-gray-800/50'"
          >
            {{ link.label }}
          </NuxtLink>
        </div>
        <div class="ml-auto flex items-center gap-3">
          <VramBadge />
        </div>
      </div>
    </nav>

    <!-- Content -->
    <main class="max-w-[1800px] mx-auto px-4 py-6">
      <slot />
    </main>
  </div>
</template>

<script setup lang="ts">
const links = [
  { to: '/', label: 'Generate' },
  { to: '/editor', label: 'Pipelines' },
  { to: '/flow', label: 'Flow Editor' },
  { to: '/gallery', label: 'Gallery' },
  { to: '/models', label: 'Models' },
]
</script>
