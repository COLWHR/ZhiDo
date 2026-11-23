<template>
  <a-modal
    :open="open"
    title="调整头像"
    :width="420"
    :footer="null"
    :maskClosable="false"
    destroy-on-close
    @cancel="close"
  >
    <div class="crop-body">
      <div
        ref="stageRef"
        class="crop-stage"
        @pointerdown="startDrag"
        @pointermove="onDrag"
        @pointerup="endDrag"
        @pointercancel="endDrag"
      >
        <img
          v-if="previewUrl"
          :src="previewUrl"
          class="crop-image"
          :style="imageStyle"
          draggable="false"
        />
        <div class="crop-mask" />
        <div class="crop-grid">
          <span /><span /><span /><span />
        </div>
        <div class="crop-ring" />
      </div>

      <div class="crop-controls">
        <span class="crop-hint">拖动图片调整位置 · 缩放调整取景</span>
        <a-slider v-model:value="zoom" :min="1" :max="3" :step="0.01" />
      </div>

      <div class="crop-actions">
        <a-button @click="close">取消</a-button>
        <a-button type="primary" :loading="processing" @click="confirm">使用此头像</a-button>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { AVATAR_VIEWPORT, cropAvatarFile, readImageFile } from '@/utils/avatar-image'

const props = defineProps<{ open: boolean; file?: File | null }>()
const emit = defineEmits<{
  (event: 'update:open', value: boolean): void
  (event: 'confirm', file: File): void
}>()

const stageRef = ref<HTMLElement | null>(null)
const previewUrl = ref('')
const zoom = ref(1)
const offsetX = ref(0)
const offsetY = ref(0)
const processing = ref(false)
const naturalSize = ref({ width: 1, height: 1 })

const coverScale = computed(() =>
  Math.max(AVATAR_VIEWPORT / naturalSize.value.width, AVATAR_VIEWPORT / naturalSize.value.height),
)

const displayedSize = computed(() => ({
  width: naturalSize.value.width * coverScale.value,
  height: naturalSize.value.height * coverScale.value,
}))

const maxShift = computed(() => ({
  x: Math.max(0, (displayedSize.value.width * zoom.value - AVATAR_VIEWPORT) / 2),
  y: Math.max(0, (displayedSize.value.height * zoom.value - AVATAR_VIEWPORT) / 2),
}))

const imageStyle = computed(() => ({
  width: `${AVATAR_VIEWPORT}px`,
  height: `${AVATAR_VIEWPORT}px`,
  transform: `translate(${offsetX.value}px, ${offsetY.value}px) scale(${zoom.value})`,
}))

const reset = () => {
  previewUrl.value = ''
  zoom.value = 1
  offsetX.value = 0
  offsetY.value = 0
}

watch(
  () => props.open,
  async (isOpen) => {
    if (!isOpen || !props.file) return
    try {
      reset()
      previewUrl.value = await readImageFile(props.file)
      const image = new Image()
      image.onload = () => {
        naturalSize.value = {
          width: image.naturalWidth || 1,
          height: image.naturalHeight || 1,
        }
      }
      image.src = previewUrl.value
    } catch (error) {
      message.error((error as Error).message || '图片读取失败')
    }
  },
)

watch(zoom, () => {
  offsetX.value = Math.min(Math.max(offsetX.value, -maxShift.value.x), maxShift.value.x)
  offsetY.value = Math.min(Math.max(offsetY.value, -maxShift.value.y), maxShift.value.y)
})

let dragging = false
let startX = 0
let startY = 0
let originX = 0
let originY = 0

const startDrag = (event: PointerEvent) => {
  dragging = true
  startX = event.clientX
  startY = event.clientY
  originX = offsetX.value
  originY = offsetY.value
  ;(event.target as HTMLElement).setPointerCapture?.(event.pointerId)
}

const onDrag = (event: PointerEvent) => {
  if (!dragging) return
  const nextX = originX + (event.clientX - startX)
  const nextY = originY + (event.clientY - startY)
  offsetX.value = Math.min(Math.max(nextX, -maxShift.value.x), maxShift.value.x)
  offsetY.value = Math.min(Math.max(nextY, -maxShift.value.y), maxShift.value.y)
}

const endDrag = () => {
  dragging = false
}

const close = () => emit('update:open', false)

const confirm = async () => {
  if (!props.file) return
  processing.value = true
  try {
    const cropped = await cropAvatarFile(props.file, {
      zoom: zoom.value,
      offsetX: offsetX.value,
      offsetY: offsetY.value,
    })
    emit('confirm', cropped)
    emit('update:open', false)
  } catch (error) {
    message.error((error as Error).message || '头像裁剪失败')
  } finally {
    processing.value = false
  }
}
</script>

<style scoped>
.crop-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.crop-stage {
  position: relative;
  width: 280px;
  height: 280px;
  margin: 0 auto;
  overflow: hidden;
  border-radius: 12px;
  background: #101413;
  cursor: grab;
  touch-action: none;
}

.crop-stage:active {
  cursor: grabbing;
}

.crop-image {
  position: absolute;
  inset: 0;
  object-fit: cover;
  transform-origin: center center;
  will-change: transform;
  user-select: none;
}

.crop-mask {
  position: absolute;
  inset: 0;
  box-shadow: inset 0 0 32px rgba(8, 12, 10, 0.28);
  pointer-events: none;
}

.crop-grid {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.crop-grid span {
  position: absolute;
  background: rgba(255, 255, 255, 0.22);
}

.crop-grid span:nth-child(1),
.crop-grid span:nth-child(2) {
  top: 0;
  bottom: 0;
  width: 1px;
}

.crop-grid span:nth-child(1) { left: 33.33%; }
.crop-grid span:nth-child(2) { left: 66.66%; }

.crop-grid span:nth-child(3),
.crop-grid span:nth-child(4) {
  left: 0;
  right: 0;
  height: 1px;
}

.crop-grid span:nth-child(3) { top: 33.33%; }
.crop-grid span:nth-child(4) { top: 66.66%; }

.crop-ring {
  position: absolute;
  inset: 0;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.55);
  pointer-events: none;
}

.crop-controls {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.crop-hint {
  font-size: 12px;
  color: #6b7280;
}

.crop-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
