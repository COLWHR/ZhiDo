<template>
  <span
    class="identity-avatar"
    :class="[`shape-${shape}`, { failed }]"
    :style="boxStyle"
    :title="title"
  >
    <img
      :src="resolvedSrc"
      :alt="altText"
      loading="lazy"
      decoding="async"
      @error="onImageError"
    />
  </span>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  generateFallbackAvatar,
  getAvatarInitial,
  isImageAvatar,
  resolveIdentityAvatar,
  type AvatarEntity,
} from '@/utils/avatar'

type AvatarKind = 'persona' | 'user' | 'counselor'
type AvatarShape = 'circle' | 'square'

const props = withDefaults(
  defineProps<{
    kind?: AvatarKind
    entity?: AvatarEntity | null
    size?: number | 'sm' | 'md' | 'lg' | 'xl'
    shape?: AvatarShape
    rankLabel?: string
    title?: string
  }>(),
  {
    kind: 'persona',
    entity: null,
    size: 40,
    shape: 'circle',
    rankLabel: '研究员',
    title: '',
  },
)

const sizeMap: Record<string, number> = { sm: 24, md: 40, lg: 56, xl: 76 }

const failed = ref(false)
const stage = ref<'upload' | 'portrait' | 'badge'>('portrait')

watch(
  () => props.entity?.avatar,
  () => {
    failed.value = false
    stage.value = isImageAvatar(props.entity?.avatar || '') ? 'upload' : 'portrait'
  },
  { immediate: true },
)

const pixels = computed(() => {
  if (typeof props.size === 'number') return props.size
  return sizeMap[props.size] ?? 40
})

const boxStyle = computed(() => ({
  width: `${pixels.value}px`,
  height: `${pixels.value}px`,
}))

const displayName = computed(
  () => props.entity?.name || props.entity?.username || (props.kind === 'user' ? '我' : '智能体'),
)

const portraitSrc = computed(() =>
  resolveIdentityAvatar(props.kind, { ...(props.entity || {}), avatar: null }, props.rankLabel),
)

const badgeSrc = computed(() =>
  generateFallbackAvatar(props.kind, props.entity, props.rankLabel),
)

const resolvedSrc = computed(() => {
  if (failed.value || stage.value === 'badge') return badgeSrc.value
  if (stage.value === 'upload' && isImageAvatar(props.entity?.avatar || '')) {
    return String(props.entity?.avatar)
  }
  return portraitSrc.value
})

const onImageError = () => {
  if (stage.value === 'upload') {
    stage.value = 'portrait'
    return
  }
  failed.value = true
  stage.value = 'badge'
}

const altText = computed(() => `${displayName.value} 头像`)
const title = computed(() => props.title || `${displayName.value}${props.kind === 'user' ? '' : ' · 智能体'}`)

defineExpose({ initial: computed(() => getAvatarInitial(displayName.value, 'U')) })
</script>

<style scoped>
.identity-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  flex-shrink: 0;
  background: #f4f6f4;
  box-shadow: inset 0 0 0 1px rgba(15, 23, 42, 0.08);
  vertical-align: middle;
  user-select: none;
}

.identity-avatar.shape-circle {
  border-radius: 50%;
}

.identity-avatar.shape-square {
  border-radius: 10px;
}

.identity-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
</style>
