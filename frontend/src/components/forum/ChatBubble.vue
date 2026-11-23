<template>
  <div class="message-item" :class="{ 'message-moderator': isModerator }">
    <div class="message-avatar">
      <IdentityAvatar
        v-if="isModerator"
        key="moderator-avatar"
        kind="persona"
        :entity="{ name: speakerName, title: '主持人' }"
        rank-label="主持"
        :size="40"
        shape="circle"
      />
      <IdentityAvatar
        v-else
        key="participant-avatar"
        :kind="kind"
        :entity="{ name: speakerName, username: speakerName, avatar }"
        :size="40"
        shape="circle"
      />
    </div>
    
    <div class="message-content-wrapper">
      <div class="message-info">
        <span class="speaker-name">
          {{ speakerName }}
          <a-tag v-if="isModerator" color="gold" style="margin-left: 4px; font-size: 10px; line-height: 14px; height: 16px; padding: 0 4px;">主持人</a-tag>
        </span>
        <span class="time">{{ formatTime(timestamp) }}</span>
      </div>
      
      <div class="message-bubble">
        <!-- Thought Process Expansion -->
        <div v-if="thought" class="thought-process">
            <a-collapse ghost :bordered="false" style="background: transparent; padding: 0;">
                <a-collapse-panel key="1" header="思考过程 (点击展开)" style="border: none; padding: 0;">
                    <template #extra>
                        <bulb-outlined />
                    </template>
                    <div class="thought-content">
                        {{ thought }}
                    </div>
                </a-collapse-panel>
            </a-collapse>
            <div class="thought-divider"></div>
        </div>

        <div v-if="isStreaming" class="streaming-indicator">
          <loading-outlined />
        </div>

        <!-- Text content -->
        <div v-if="isTextContent" class="text-content">
          {{ content }}
        </div>

        <!-- Image content -->
        <div v-else-if="isImageContent" class="media-content">
          <img :src="content" alt="Image" class="message-image" />
        </div>

        <!-- Video content -->
        <div v-else-if="isVideoContent" class="media-content">
          <video :src="content" controls class="message-video"></video>
        </div>

        <!-- Audio content -->
        <div v-else-if="isAudioContent" class="media-content">
          <audio :src="content" controls class="message-audio"></audio>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { LoadingOutlined, BulbOutlined } from '@ant-design/icons-vue'
import IdentityAvatar from '@/components/identity/IdentityAvatar.vue'

const props = defineProps<{
  speakerName: string
  content: string
  thought?: string | null // Added thought prop
  timestamp: string
  isSelf: boolean
  isStreaming?: boolean
  moderatorId?: number | null
  avatar?: string
  kind?: 'persona' | 'user'
}>()

const isModerator = computed(() => {
  return !!props.moderatorId || props.speakerName.includes('主持人')
})

const isStreaming = computed(() => {
    return props.isStreaming || false
})

const formatTime = (isoString: string) => {
    if (!isoString) return ''
    const date = new Date(isoString)
    return date.toLocaleTimeString()
}

// Content type detection computed properties
const isTextContent = computed(() => {
  return !isImageContent.value && !isVideoContent.value && !isAudioContent.value
})

const isImageContent = computed(() => {
  const imageExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
  const content = props.content.toLowerCase()
  return imageExtensions.some(ext => content.includes(ext)) || content.startsWith('http') && (content.includes('image') || content.match(/\.(jpg|jpeg|png|gif|webp|bmp)$/))
})

const isVideoContent = computed(() => {
  const videoExtensions = ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm']
  const content = props.content.toLowerCase()
  return videoExtensions.some(ext => content.includes(ext)) || content.startsWith('http') && (content.includes('video') || content.match(/\.(mp4|avi|mov|wmv|flv|webm)$/))
})

const isAudioContent = computed(() => {
  const audioExtensions = ['.mp3', '.wav', '.ogg', '.m4a', '.flac']
  const content = props.content.toLowerCase()
  return audioExtensions.some(ext => content.includes(ext)) || content.startsWith('http') && (content.includes('audio') || content.match(/\.(mp3|wav|ogg|m4a|flac)$/))
})
</script>

<style scoped>
.message-item {
  display: flex;
  margin-bottom: 24px;
  gap: 12px;
}

.message-self {
  flex-direction: row-reverse;
}

.message-content-wrapper {
  max-width: 70%;
  display: flex;
  flex-direction: column;
}

.message-avatar :deep(.ant-avatar img),
.message-avatar .avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.message-self .message-content-wrapper {
  align-items: flex-end;
}

.message-info {
  margin-bottom: 4px;
  font-size: 12px;
  color: #6b7280;
  display: flex;
  align-items: center;
}

.message-self .message-info {
  text-align: right;
  flex-direction: row-reverse;
}

.message-info .time {
  margin-left: 8px;
  font-size: 10px;
}

.message-self .message-info .time {
  margin-left: 0;
  margin-right: 8px;
}

.message-bubble {
  padding: 12px 16px;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 1px 2px rgba(0,0,0,0.03);
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.message-self .message-bubble {
  background: #ebf7ee;
  color: #333;
  border-radius: 8px 0 8px 8px;
}

.message-item:not(.message-self) .message-bubble {
  border-radius: 0 8px 8px 8px;
}

/* Moderator specific styles */
.message-moderator .message-bubble {
  background: #f9f7e8; /* Light gold background */
  border: 1px solid #f0e6cc;
}

.thought-process {
    margin-bottom: 8px;
    font-size: 12px;
}

.thought-content {
    background: rgba(0, 0, 0, 0.03);
    padding: 8px;
    border-radius: 4px;
    margin-top: 4px;
    color: #6b7280;
    font-style: italic;
    white-space: pre-wrap;
}

.thought-divider {
    border-bottom: 1px dashed rgba(0, 0, 0, 0.1);
    margin: 8px 0;
}

/* Customize collapse header style */
:deep(.ant-collapse-header) {
    padding: 0 !important;
    font-size: 12px !important;
    color: #999 !important;
}

:deep(.ant-collapse-content-box) {
    padding: 0 !important;
}

/* Media content styles */
.media-content {
  margin-top: 8px;
}

.message-image {
  max-width: 100%;
  max-height: 300px;
  border-radius: 4px;
  object-fit: contain;
}

.message-video {
  max-width: 100%;
  max-height: 300px;
  border-radius: 4px;
}

.message-audio {
  width: 100%;
  margin-top: 8px;
}

.text-content {
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
