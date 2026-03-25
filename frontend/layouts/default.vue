<template>
  <div class="h-screen flex flex-col overflow-hidden" style="background: var(--bg-primary)">
    <!-- Title bar -->
    <div class="h-9 flex items-center px-3 shrink-0" style="background: var(--bg-secondary); border-bottom: 1px solid var(--border)">
      <span class="text-[13px] font-semibold tracking-tight" style="color: var(--accent)">vargen</span>
      <div class="flex items-center gap-0.5 ml-6">
        <NuxtLink
          v-for="tab in tabs"
          :key="tab.to"
          :to="tab.to"
          class="px-2.5 py-1 text-[12px] rounded transition-colors"
          :style="$route.path === tab.to
            ? 'background: var(--bg-active); color: var(--text-primary)'
            : 'color: var(--text-secondary)'"
          @mouseenter="($event.target as HTMLElement).style.color = 'var(--text-primary)'"
          @mouseleave="($event.target as HTMLElement).style.color = $route.path === tab.to ? 'var(--text-primary)' : 'var(--text-secondary)'"
        >
          {{ tab.label }}
        </NuxtLink>
      </div>
      <div class="ml-auto flex items-center gap-3">
        <VramBadge />
      </div>
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-hidden">
      <slot />
    </div>

    <!-- Status bar -->
    <div class="h-6 flex items-center px-3 shrink-0 text-[11px]" style="background: var(--accent); color: #000">
      <span class="font-medium">vargen</span>
      <span class="ml-3 opacity-60">v0.1.0</span>
      <span class="ml-auto mono opacity-60" v-if="status">{{ status }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
const tabs = [
  { to: '/', label: 'Generate' },
  { to: '/editor', label: 'Pipelines' },
  { to: '/flow', label: 'Flow' },
  { to: '/gallery', label: 'Gallery' },
  { to: '/models', label: 'Models' },
]

const status = ref('Ready')
</script>
