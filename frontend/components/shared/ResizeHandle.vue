<template>
  <div
    class="resize-handle"
    :class="'resize-handle-' + side"
    @mousedown="startResize"
  />
</template>

<script setup lang="ts">
const props = defineProps<{
  side: 'left' | 'right' | 'top' | 'bottom'
  modelValue: number
  min?: number
  max?: number
}>()

const emit = defineEmits(['update:modelValue'])

function startResize(e: MouseEvent) {
  e.preventDefault()
  const startPos = props.side === 'left' || props.side === 'right' ? e.clientX : e.clientY
  const startSize = props.modelValue

  const onMove = (e: MouseEvent) => {
    const currentPos = props.side === 'left' || props.side === 'right' ? e.clientX : e.clientY
    let delta = currentPos - startPos
    if (props.side === 'left' || props.side === 'top') delta = -delta
    const newSize = Math.max(props.min ?? 100, Math.min(props.max ?? 800, startSize + delta))
    emit('update:modelValue', newSize)
  }

  const onUp = () => {
    window.removeEventListener('mousemove', onMove)
    window.removeEventListener('mouseup', onUp)
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
  }

  document.body.style.cursor = props.side === 'left' || props.side === 'right' ? 'ew-resize' : 'ns-resize'
  document.body.style.userSelect = 'none'
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
}
</script>
