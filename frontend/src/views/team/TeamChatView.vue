<template>
  <div class="team-chat-page">
    <a-layout class="chat-layout">
      <!-- 右侧成员栏 -->
      <a-layout-sider width="220" class="member-sider">
        <div class="sider-header">
          <h3 class="sider-title">群成员</h3>
          <span class="sider-count">{{ team?.members.length || 0 }}</span>
        </div>
        <div class="member-list">
          <div v-for="m in team?.members || []" :key="m.persona_id" class="member-item">
            <IdentityAvatar kind="persona" :entity="{ name: m.name, avatar: m.avatar }" :size="30" shape="circle" />
            <div class="member-info">
              <div class="member-name">{{ m.name }}</div>
              <div class="member-title">{{ m.title || '智能体' }}</div>
            </div>
          </div>
          <div v-if="!team" class="member-empty">加载中…</div>
        </div>
      </a-layout-sider>

      <a-layout class="chat-section">
        <!-- 头部 -->
        <div class="chat-header">
          <div class="header-left">
            <a-button type="text" @click="goBack">
              <arrow-left-outlined />
            </a-button>
            <div class="team-meta">
              <span class="team-name">{{ team?.name || '团队群聊' }}</span>
              <span class="team-desc">{{ team?.description || '在群里 @ 成员分配任务' }}</span>
            </div>
          </div>
          <span class="status-pill" :class="{ loading }">{{ loading ? '回复中…' : `${messages.length} 条消息` }}</span>
        </div>

        <!-- 消息区 -->
        <div class="messages-container" ref="messagesContainer">
          <div v-if="lastDecision" class="decision-badge">
            <span class="db-label">{{ decisionLabelText(lastDecision.label) }}</span>
            <span class="db-meta">置信度 {{ decisionPct(lastDecision.confidence) }}</span>
            <a-tag :color="lastDecision.layer === 'model' ? 'blue' : 'orange'">
              {{ decisionLayerText(lastDecision.layer) }}
            </a-tag>
            <span v-if="lastDecision.keyword" class="db-meta">关键词 {{ lastDecision.keyword }}</span>
            <span class="db-meta">{{ Number(lastDecision.elapsed_ms).toFixed(2) }} ms</span>
          </div>
          <div v-for="msg in messages" :key="msg.id" class="message-item" :class="msg.sender_type">
            <template v-if="msg.sender_type === 'assistant'">
              <div class="message-avatar">
                <IdentityAvatar kind="persona" :entity="{ name: msg.speaker_name, avatar: avatarOf(msg.persona_id) }" :size="28" shape="circle" />
              </div>
              <div class="message-content">
                <div class="speaker-label-row">
                  <div class="speaker-label">{{ msg.speaker_name }}</div>
                  <button
                    v-if="msg.content"
                    type="button"
                    class="speak-btn"
                    :class="{ active: speakingId === msg.id }"
                    @click="toggleSpeak(msg)"
                  >
                    {{ speakingId === msg.id ? '⏸ 停止' : '🔊 朗读' }}
                  </button>
                </div>
                <div class="message-bubble" v-html="formatMessage(msg.content)"></div>
                <div v-if="msg.attachments?.length" class="message-attachments">
                  <div v-for="att in msg.attachments" :key="att.file_name" class="attachment-card">
                    <div class="attachment-preview" v-if="att.kind === 'image' && att.preview_url">
                      <img :src="att.preview_url" :alt="att.file_name" />
                    </div>
                    <div class="attachment-meta">
                      <div class="attachment-name">{{ att.file_name }}</div>
                      <div class="attachment-sub">{{ att.kind || 'file' }}</div>
                    </div>
                    <a :href="att.storage_url" target="_blank" rel="noreferrer" class="attachment-link">打开</a>
                  </div>
                </div>
              </div>
            </template>

            <template v-else-if="msg.sender_type === 'user'">
              <div class="message-content">
                <div v-if="msg.mentioned_persona_ids?.length" class="mention-row">
                  <a-tag v-for="pid in msg.mentioned_persona_ids" :key="pid" color="green" class="mention-tag">@ {{ nameOf(pid) }}</a-tag>
                </div>
                <div class="message-bubble" v-html="formatMessage(msg.content)"></div>
                <div v-if="msg.attachments?.length" class="message-attachments">
                  <div v-for="att in msg.attachments" :key="att.file_name" class="attachment-card">
                    <div class="attachment-preview" v-if="att.kind === 'image' && att.preview_url">
                      <img :src="att.preview_url" :alt="att.file_name" />
                    </div>
                    <div class="attachment-meta">
                      <div class="attachment-name">{{ att.file_name }}</div>
                      <div class="attachment-sub">{{ att.kind || 'file' }}</div>
                    </div>
                    <a :href="att.storage_url" target="_blank" rel="noreferrer" class="attachment-link">打开</a>
                  </div>
                </div>
              </div>
              <div class="message-avatar">
                <IdentityAvatar kind="user" :entity="authStore.user" :size="28" shape="circle" />
              </div>
            </template>

            <div v-else class="system-bubble">{{ msg.content }}</div>
          </div>

          <div v-if="loading" class="message-item assistant">
            <div class="message-avatar">
              <IdentityAvatar kind="persona" :entity="{ name: '助手' }" :size="28" shape="circle" />
            </div>
            <div class="message-content">
              <div class="message-bubble thinking">
                <span class="dot"></span><span class="dot"></span><span class="dot"></span>
              </div>
            </div>
          </div>
        </div>

        <!-- 输入区 -->
        <div class="input-section">
          <div v-if="selectedMentions.length" class="mention-chips">
            <a-tag v-for="m in selectedMentions" :key="m.persona_id" color="green" closable @close="toggleMention(m.persona_id)">
              @ {{ m.name }}
            </a-tag>
          </div>

          <div class="input-toolbar">
            <a-button type="text" size="small" @click="openMentionFromToolbar">
              <team-outlined /> @ 成员
            </a-button>

            <a-button type="text" size="small" @click="triggerUpload">
              <picture-outlined /> 附件
            </a-button>
            <input
              ref="fileInput"
              type="file"
              accept="image/*,.pdf,.doc,.docx,.txt,.md,.csv,.json,.xlsx,.pptx"
              style="display: none"
              @change="handleFileUpload"
            />
            <span class="tip-text">必须 @ 成员才会回复；支持图片与文档附件</span>
          </div>

          <div v-if="pendingAttachments.length" class="pending-attachments">
            <div v-for="(att, index) in pendingAttachments" :key="att.file_name" class="pending-attachment">
              <span class="pending-name">{{ att.file_name }}</span>
              <button class="pending-remove" type="button" @click="removeAttachment(index)">移除</button>
            </div>
          </div>

          <div v-if="mentionPopupOpen" class="mention-popover">
            <div v-if="filteredMentions.length" class="mention-list">
              <div
                v-for="(m, idx) in filteredMentions"
                :key="m.persona_id"
                class="mention-option"
                :class="{ active: idx === mentionActiveIndex }"
                @mousedown.prevent
                @click="pickMention(m)"
              >
                <IdentityAvatar kind="persona" :entity="{ name: m.name, avatar: m.avatar }" :size="24" shape="circle" />
                <span class="mention-option-name">{{ m.name }}</span>
                <span v-if="m.title" class="mention-option-title">{{ m.title }}</span>
                <a-tag v-if="isSelected(m.persona_id)" color="green" class="mention-option-tag">已选</a-tag>
              </div>
            </div>
            <div v-else class="mention-empty">没有匹配「{{ mentionQuery }}」的成员</div>
          </div>

          <a-textarea
            ref="inputRef"
            v-model:value="inputMessage"
            :rows="3"
            placeholder="输入 @ 选择成员，Enter 发送，Shift+Enter 换行"
            :disabled="loading"
            class="chat-input"
            @input="detectMention"
            @click="detectMention"
            @keydown="onTextareaKeydown"
          />
          <div class="input-actions">
            <a-button type="primary" @click="handleSend" :loading="loading" :disabled="!canSend">
              <send-outlined /> 发送
            </a-button>
          </div>
        </div>
      </a-layout>
    </a-layout>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  ArrowLeftOutlined,
  TeamOutlined,
  PictureOutlined,
  SendOutlined,
} from '@ant-design/icons-vue'
import { marked } from 'marked'
import IdentityAvatar from '@/components/identity/IdentityAvatar.vue'
import request from '@/utils/request'
import { teamApi, type Team, type TeamAttachment, type TeamMessage } from '@/api/team'
import { useAuthStore } from '@/stores/auth'

interface LocalMessage {
  id: number | string
  sender_type: 'user' | 'assistant' | 'system'
  persona_id?: number | null
  speaker_name: string
  content: string
  attachments: TeamAttachment[]
  mentioned_persona_ids: number[]
  timestamp: number
  streaming?: boolean
}

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const team = ref<Team | null>(null)
const messages = ref<LocalMessage[]>([])
const inputMessage = ref('')
const loading = ref(false)
const pendingAttachments = ref<TeamAttachment[]>([])
const selectedMentions = ref<{ persona_id: number; name: string }[]>([])
const fileInput = ref<HTMLInputElement | null>(null)
const messagesContainer = ref<HTMLElement | null>(null)
const inputRef = ref<HTMLTextAreaElement | null>(null)

// Inline mention popup state: opened when the caret follows an unfinished "@".
const mentionPopupOpen = ref(false)
const mentionQuery = ref('')
const mentionAtStart = ref(0)
const mentionActiveIndex = ref(0)

// Browser-side speech synthesis (zero backend / zero API cost).
const speakingId = ref<number | string | null>(null)

// Latest intent decision for the explainability badge in this turn.
const lastDecision = ref<{ label: string; confidence: number; layer: string; keyword: string | null; elapsed_ms: number } | null>(null)

const DECISION_LABEL_TEXT: Record<string, string> = {
  chat: '闲聊对话',
  doc: '文档撰写',
  sheet: '表格清单',
  image: '配图/示意图',
  vision: '图片理解',
  risk: '风险拦截',
}
const decisionLabelText = (label?: string | null) => (label ? DECISION_LABEL_TEXT[label] || label : '-')
const decisionLayerText = (layer?: string | null) => (layer === 'model' ? '小模型决策' : layer === 'rule' ? '规则兜底' : '-')
const decisionPct = (v?: number | null) => (v == null ? '-' : `${(v * 100).toFixed(1)}%`)

const toggleSpeak = (msg: LocalMessage) => {
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
    message.warning('当前浏览器不支持语音朗读')
    return
  }
  if (speakingId.value === msg.id) {
    window.speechSynthesis.cancel()
    speakingId.value = null
    return
  }
  window.speechSynthesis.cancel()
  const text = (msg.content || '').replace(/[#*`>_\[\]()]/g, ' ').replace(/\s+/g, ' ').trim()
  if (!text) return
  const utter = new SpeechSynthesisUtterance(text)
  utter.lang = 'zh-CN'
  utter.rate = 1
  utter.onend = () => {
    if (speakingId.value === msg.id) speakingId.value = null
  }
  utter.onerror = () => {
    if (speakingId.value === msg.id) speakingId.value = null
  }
  speakingId.value = msg.id
  window.speechSynthesis.speak(utter)
}

const teamId = computed(() => Number(route.params.id))

// Track the in-flight SSE request so it can be aborted on navigation/unmount.
let activeController: AbortController | null = null
let activeReader: ReadableStreamDefaultReader<Uint8Array> | null = null

const canSend = computed(
  () => (inputMessage.value.trim() || pendingAttachments.value.length > 0) && !loading.value,
)

const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

const nameOf = (pid?: number | null) => team.value?.members.find((m) => m.persona_id === pid)?.name || '成员'
const avatarOf = (pid?: number | null) => team.value?.members.find((m) => m.persona_id === pid)?.avatar

const isSelected = (pid: number) => selectedMentions.value.some((m) => m.persona_id === pid)

const toggleMention = (pid: number) => {
  const member = team.value?.members.find((m) => m.persona_id === pid)
  if (!member) return
  if (isSelected(pid)) {
    selectedMentions.value = selectedMentions.value.filter((m) => m.persona_id !== pid)
  } else {
    selectedMentions.value.push({ persona_id: pid, name: member.name })
  }
}

const filteredMentions = computed(() => {
  const q = mentionQuery.value.trim().toLowerCase()
  const list = team.value?.members || []
  if (!q) return list
  return list.filter((m) => m.name.toLowerCase().includes(q))
})

const closeMention = () => {
  mentionPopupOpen.value = false
  mentionQuery.value = ''
  mentionActiveIndex.value = 0
}

// Detect an unfinished "@" token right before the caret and open the picker.
const detectMention = () => {
  const el = inputRef.value
  if (!el) {
    closeMention()
    return
  }
  const caret = el.selectionStart ?? inputMessage.value.length
  const slice = inputMessage.value.slice(0, caret)
  const atIdx = slice.lastIndexOf('@')
  if (atIdx === -1) {
    closeMention()
    return
  }
  const between = slice.slice(atIdx + 1)
  if (/\s|[，。！？、：；,.!?;:]/.test(between)) {
    closeMention()
    return
  }
  mentionAtStart.value = atIdx
  mentionQuery.value = between
  mentionActiveIndex.value = 0
  mentionPopupOpen.value = true
}

const pickMention = (member: { persona_id: number; name: string; title?: string | null }) => {
  const el = inputRef.value
  const caret = el?.selectionStart ?? inputMessage.value.length
  const before = inputMessage.value.slice(0, mentionAtStart.value)
  const after = inputMessage.value.slice(caret)
  const inserted = `@${member.name} `
  inputMessage.value = `${before}${inserted}${after}`

  if (!selectedMentions.value.some((m) => m.persona_id === member.persona_id)) {
    selectedMentions.value.push({ persona_id: member.persona_id, name: member.name })
  }
  closeMention()
  nextTick(() => {
    const el2 = inputRef.value
    if (el2) {
      const pos = before.length + inserted.length
      el2.focus()
      el2.setSelectionRange(pos, pos)
    }
  })
}

const openMentionFromToolbar = () => {
  const el = inputRef.value
  const caret = el?.selectionStart ?? inputMessage.value.length
  const before = inputMessage.value.slice(0, caret)
  const after = inputMessage.value.slice(caret)
  inputMessage.value = `${before}@${after}`
  mentionAtStart.value = caret
  mentionQuery.value = ''
  mentionActiveIndex.value = 0
  mentionPopupOpen.value = true
  nextTick(() => {
    const el2 = inputRef.value
    if (el2) {
      el2.focus()
      el2.setSelectionRange(caret + 1, caret + 1)
    }
  })
}

const onTextareaKeydown = (e: KeyboardEvent) => {
  if (!mentionPopupOpen.value) {
    handleSend(e)
    return
  }
  const list = filteredMentions.value
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    mentionActiveIndex.value = Math.min(mentionActiveIndex.value + 1, list.length - 1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    mentionActiveIndex.value = Math.max(mentionActiveIndex.value - 1, 0)
  } else if (e.key === 'Escape') {
    closeMention()
  } else if (e.key === 'Enter' && list.length) {
    e.preventDefault()
    pickMention(list[mentionActiveIndex.value])
  }
}

const formatMessage = (content: string) => (content ? marked.parse(content) : '')

const formatTime = (ts: number) => {
  const d = new Date(ts)
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}

const loadTeam = async () => {
  try {
    const [detail, history] = await Promise.all([
      teamApi.detail(teamId.value),
      teamApi.messages(teamId.value),
    ])
    team.value = detail
    messages.value = history.map((m: TeamMessage) => ({
      id: m.id,
      sender_type: m.sender_type,
      persona_id: m.persona_id,
      speaker_name: m.speaker_name,
      content: m.content,
      attachments: m.attachments || [],
      mentioned_persona_ids: m.mentioned_persona_ids || [],
      timestamp: m.created_at ? new Date(m.created_at).getTime() : Date.now(),
    }))
    await nextTick()
    scrollToBottom()
  } catch (error) {
    console.error('加载团队失败:', error)
    message.error('加载团队失败')
  }
}

const resetDraft = () => {
  inputMessage.value = ''
  pendingAttachments.value = []
  selectedMentions.value = []
  closeMention()
}

const abortActiveStream = () => {
  activeController?.abort()
  activeController = null
  activeReader?.cancel().catch(() => {})
  activeReader = null
}

// Reload when navigating between teams without remounting the component.
watch(teamId, (newId, oldId) => {
  if (!newId || newId === oldId) return
  abortActiveStream()
  messages.value = []
  team.value = null
  resetDraft()
  loadTeam()
})

onMounted(loadTeam)
const cleanupOnUnmount = () => {
  abortActiveStream()
  if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
    window.speechSynthesis.cancel()
  }
}

onUnmounted(cleanupOnUnmount)

const triggerUpload = () => fileInput.value?.click()

const normalizeAttachment = (raw: any): TeamAttachment => ({
  id: raw.id,
  file_name: raw.file_name,
  mime_type: raw.mime_type,
  kind: raw.kind,
  storage_url: raw.storage_url,
  preview_url: raw.preview_url,
  size: raw.size,
  meta: raw.meta || {},
})

const handleFileUpload = async (e: Event) => {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return
  if (file.size > 10 * 1024 * 1024) {
    message.error('文件大小不能超过 10MB')
    return
  }
  try {
    const formData = new FormData()
    formData.append('file', file)
    const res = await request.post('/upload/asset', formData)
    if (res.data) {
      pendingAttachments.value.push(normalizeAttachment(res.data))
      message.success('附件已加入')
    }
  } catch (error) {
    console.error('附件上传失败:', error)
  } finally {
    target.value = ''
  }
}

const removeAttachment = (index: number) => pendingAttachments.value.splice(index, 1)

const goBack = () => router.push('/teams')

const handleSend = async (e?: KeyboardEvent) => {
  if (e && e.shiftKey) return
  e?.preventDefault()
  if (!canSend.value) return

  const content = inputMessage.value.trim()
  const mentionedIds = selectedMentions.value.map((m) => m.persona_id)
  const attachments = pendingAttachments.value.map((a) => ({ ...a }))

  messages.value.push({
    id: `local-${Date.now()}`,
    sender_type: 'user',
    speaker_name: authStore.user?.username || '我',
    content: content || '发送了附件',
    attachments,
    mentioned_persona_ids: mentionedIds,
    timestamp: Date.now(),
  })

  inputMessage.value = ''
  pendingAttachments.value = []
  selectedMentions.value = []
  closeMention()
  lastDecision.value = null
  loading.value = true
  await nextTick()
  scrollToBottom()

  activeController = new AbortController()
  try {
    const response = await fetch(`/api/v1/teams/${teamId.value}/chat/stream`, {
      method: 'POST',
      signal: activeController.signal,
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer ' + (authStore.token || ''),
      },
      body: JSON.stringify({
        content: content || '发送了附件',
        attachments,
        mentioned_persona_ids: mentionedIds,
      }),
    })

    if (!response.ok) {
      const detail = await response.text().catch(() => '')
      throw new Error(detail || '网络请求失败')
    }

    activeReader = response.body?.getReader()
    const reader = activeReader
    if (!reader) throw new Error('未能读取流式响应')

    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() || ''

      for (const part of parts) {
        const line = part.trim()
        if (!line.startsWith('data: ')) continue
        const data = line.slice(6).trim()
        if (!data || data === '[DONE]') continue

        try {
          const parsed = JSON.parse(data)
          await handleStreamEvent(parsed)
        } catch (parseError) {
          console.error('解析流式响应失败:', parseError)
        }
      }
    }
  } catch (error) {
    // Aborted by navigation/unmount: no user-facing error to surface.
    if (error instanceof DOMException && error.name === 'AbortError') return
    console.error('群聊发送失败:', error)
    message.error('发送失败，请稍后重试')
    messages.value.push({
      id: `err-${Date.now()}`,
      sender_type: 'system',
      speaker_name: '系统',
      content: error instanceof Error && error.message ? error.message : '请求出错，请稍后再试。',
      attachments: [],
      mentioned_persona_ids: [],
      timestamp: Date.now(),
    })
  } finally {
    activeController = null
    activeReader = null
    loading.value = false
    await nextTick()
    scrollToBottom()
  }
}

const handleStreamEvent = async (parsed: any) => {
  if (parsed.type === 'decision') {
    lastDecision.value = {
      label: parsed.label,
      confidence: parsed.confidence,
      layer: parsed.layer,
      keyword: parsed.keyword ?? null,
      elapsed_ms: parsed.elapsed_ms ?? null,
    }
    return
  }

  if (parsed.type === 'agent_start') {
    messages.value.push({
      id: `agent-${parsed.persona_id}-${Date.now()}`,
      sender_type: 'assistant',
      persona_id: parsed.persona_id,
      speaker_name: parsed.speaker_name || '成员',
      content: '',
      attachments: [],
      mentioned_persona_ids: [],
      timestamp: Date.now(),
      streaming: true,
    })
    await nextTick()
    scrollToBottom()
    return
  }

  if (parsed.type === 'delta') {
    const target = messages.value.find((m) => m.persona_id === parsed.persona_id && m.streaming)
    if (target) {
      target.content += parsed.content || ''
    } else {
      messages.value.push({
        id: `agent-${parsed.persona_id}-${Date.now()}`,
        sender_type: 'assistant',
        persona_id: parsed.persona_id,
        speaker_name: parsed.speaker_name || '成员',
        content: parsed.content || '',
        attachments: [],
        mentioned_persona_ids: [],
        timestamp: Date.now(),
        streaming: true,
      })
    }
    await nextTick()
    scrollToBottom()
    return
  }

  if (parsed.type === 'artifact') {
    const target =
      messages.value.find((m) => m.persona_id === parsed.persona_id && m.streaming) ||
      messages.value.find((m) => m.persona_id === parsed.persona_id)
    if (target && parsed.attachment) {
      target.attachments = target.attachments || []
      target.attachments.push(parsed.attachment)
    }
    await nextTick()
    scrollToBottom()
    return
  }

  if (parsed.type === 'agent_end') {
    const target = messages.value.find((m) => m.persona_id === parsed.persona_id && m.streaming)
    if (target) target.streaming = false
    return
  }

  if (parsed.type === 'system') {
    messages.value.push({
      id: `sys-${Date.now()}`,
      sender_type: 'system',
      speaker_name: '系统',
      content: parsed.content || '',
      attachments: [],
      mentioned_persona_ids: [],
      timestamp: Date.now(),
    })
    await nextTick()
    scrollToBottom()
    return
  }

  if (parsed.error) {
    messages.value.push({
      id: `err-${Date.now()}`,
      sender_type: 'system',
      speaker_name: '系统',
      content: parsed.error,
      attachments: [],
      mentioned_persona_ids: [],
      timestamp: Date.now(),
    })
  }
}
</script>

<style scoped>
.team-chat-page {
  height: 100vh;
  background: transparent;
}

.chat-layout {
  height: 100%;
}

.member-sider {
  background: rgba(255, 255, 255, 0.82);
  border-right: 1px solid rgba(148, 163, 184, 0.18);
}

.sider-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 22px 18px 14px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);
}

.sider-title {
  font-size: 15px;
  font-weight: 600;
  margin: 0;
  color: #10213a;
}

.sider-count {
  font-size: 12px;
  color: #64748b;
}

.member-list {
  padding: 10px 12px;
  overflow-y: auto;
}

.member-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border-radius: 14px;
}

.member-info {
  min-width: 0;
}

.member-name {
  font-size: 14px;
  font-weight: 500;
  color: #10213a;
}

.member-title {
  font-size: 12px;
  color: #787f84;
}

.member-empty {
  padding: 24px 12px;
  text-align: center;
  font-size: 12px;
  color: #94a3b8;
}

.chat-section {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 16px 24px;
  background: rgba(255, 255, 255, 0.82);
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.team-meta {
  display: flex;
  flex-direction: column;
}

.team-name {
  font-weight: 600;
  color: #10213a;
}

.team-desc {
  font-size: 12px;
  color: #64748b;
}

.status-pill {
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12px;
  color: #1e293b;
  background: rgba(148, 163, 184, 0.14);
}

.status-pill.loading {
  color: #334155;
  background: rgba(59, 179, 107, 0.14);
}

.messages-container {
  flex: 1;
  padding: 26px 24px 22px;
  overflow-y: auto;
}

.decision-badge {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 16px;
  padding: 10px 14px;
  background: #f4faf5;
  border: 1px solid #d7ecdc;
  border-radius: 12px;
  font-size: 13px;
  color: #3d5a46;
}

.decision-badge .db-label {
  font-weight: 700;
  color: #151917;
}

.decision-badge .db-meta {
  color: #6b7c70;
}

.message-item {
  display: flex;
  gap: 14px;
  margin-bottom: 18px;
  align-items: flex-end;
}

.message-item.user {
  flex-direction: row-reverse;
}

.message-avatar {
  flex-shrink: 0;
  margin-top: 4px;
}

.message-content {
  max-width: 70%;
}

.speaker-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.speak-btn {
  border: none;
  background: transparent;
  font-size: 12px;
  color: #64748b;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 8px;
}

.speak-btn:hover {
  background: rgba(59, 179, 107, 0.1);
  color: #37966b;
}

.speak-btn.active {
  color: #37966b;
  background: rgba(59, 179, 107, 0.14);
}

.speaker-label {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 4px;
  padding-left: 4px;
}

.message-bubble {
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.78);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
  line-height: 1.6;
  word-break: break-word;
}

.message-item.user .message-bubble {
  background: #3bb36b;
  color: white;
  border-color: transparent;
  box-shadow: 0 14px 30px rgba(59, 179, 107, 0.22);
}

.mention-row {
  display: flex;
  gap: 6px;
  margin-bottom: 6px;
  justify-content: flex-end;
}

.mention-tag {
  margin-inline-end: 0;
}

.system-bubble {
  margin: 0 auto 18px;
  padding: 8px 14px;
  border-radius: 12px;
  font-size: 12px;
  color: #64748b;
  background: rgba(148, 163, 184, 0.14);
  text-align: center;
}

.message-attachments {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 10px;
}

.attachment-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(148, 163, 184, 0.18);
}

.attachment-preview {
  width: 52px;
  height: 52px;
  border-radius: 12px;
  overflow: hidden;
  flex-shrink: 0;
  background: rgba(148, 163, 184, 0.1);
}

.attachment-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.attachment-meta {
  flex: 1;
  min-width: 0;
}

.attachment-name {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.attachment-sub {
  margin-top: 4px;
  font-size: 12px;
  color: #64748b;
}

.attachment-link {
  font-size: 12px;
  color: #3bb36b;
  text-decoration: none;
  flex-shrink: 0;
}

.thinking {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 16px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #787f84;
  animation: bounce 1.4s infinite ease-in-out both;
}

.dot:nth-child(1) { animation-delay: -0.32s; }
.dot:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.input-section {
  position: relative;
  padding: 16px 24px 20px;
  background: rgba(255, 255, 255, 0.88);
  border-top: 1px solid rgba(148, 163, 184, 0.16);
}

.input-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.tip-text {
  font-size: 12px;
  color: #94a3b8;
}

.mention-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}

.mention-popover {
  position: absolute;
  bottom: 100%;
  left: 24px;
  margin-bottom: 8px;
  width: 260px;
  max-height: 260px;
  overflow-y: auto;
  background: #fff;
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 12px;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.14);
  padding: 6px;
  z-index: 30;
}

.mention-list {
  display: flex;
  flex-direction: column;
}

.mention-option {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 10px;
  cursor: pointer;
}

.mention-option:hover {
  background: rgba(59, 179, 107, 0.1);
}

.mention-option.active {
  background: rgba(59, 179, 107, 0.16);
}

.mention-option-name {
  flex: 1;
  font-size: 14px;
  color: #1e293b;
}

.mention-option-title {
  font-size: 12px;
  color: #94a3b8;
}

.mention-option-tag {
  margin-inline-end: 0;
}

.mention-empty {
  padding: 16px;
  text-align: center;
  font-size: 12px;
  color: #94a3b8;
}

.pending-attachments {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}

.pending-attachment {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(59, 179, 107, 0.12);
  border: 1px solid rgba(59, 179, 107, 0.16);
}

.pending-name {
  font-size: 12px;
  color: #0f172a;
}

.pending-remove {
  border: none;
  background: transparent;
  color: #ef4444;
  cursor: pointer;
  font-size: 12px;
}

.chat-input {
  border-radius: 16px;
  margin-bottom: 12px;
}

.input-actions {
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 960px) {
  .member-sider {
    display: none;
  }

  .message-content {
    max-width: 86%;
  }
}
</style>
