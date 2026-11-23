<template>
  <div class="admin-page">
    <section class="page-band">
      <div>
        <h1>智能体管理</h1>
        <p>编辑内置与自定义智能体的定位、立场与系统提示词，维护挂载知识库。</p>
      </div>
    </section>

    <section class="panel">
      <a-table
        :columns="columns"
        :data-source="personas"
        :loading="loading"
        row-key="id"
        :pagination="{ pageSize: 15, showSizeChanger: false }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'owner'">
            {{ record.owner_name || '-' }}
          </template>
          <template v-else-if="column.key === 'actions'">
            <a-button size="small" type="primary" ghost @click="openEdit(record)">编辑提示词</a-button>
            <a-button size="small" style="margin-left: 8px" @click="openKnowledge(record)">知识库</a-button>
          </template>
        </template>
      </a-table>
    </section>

    <a-modal
      v-model:open="editOpen"
      :title="`编辑智能体 · ${editing?.name || ''}`"
      width="min(720px, calc(100vw - 32px))"
      :confirm-loading="submitting"
      @ok="submitEdit"
    >
      <a-form layout="vertical" style="margin-top: 16px">
        <a-form-item label="名称">
          <a-input v-model:value="form.name" />
        </a-form-item>
        <a-form-item label="头衔">
          <a-input v-model:value="form.title" />
        </a-form-item>
        <a-form-item label="立场 / 观点">
          <a-input v-model:value="form.stance" />
        </a-form-item>
        <a-form-item label="简介">
          <a-textarea v-model:value="form.bio" :rows="3" />
        </a-form-item>
        <a-form-item label="系统提示词">
          <a-textarea v-model:value="form.system_prompt" :rows="8" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-drawer
      v-model:open="kbOpen"
      :title="`知识库 · ${kbTarget?.name || ''}`"
      width="min(520px, 92vw)"
    >
      <div class="kb-toolbar">
        <a-button size="small" type="primary" ghost :loading="kbUploading" @click="triggerKbUpload">
          <upload-outlined /> 上传资料
        </a-button>
        <input ref="kbInputRef" type="file" style="display: none" @change="handleKbFileChange" />
      </div>
      <a-spin :spinning="kbLoading">
        <a-table :columns="kbColumns" :data-source="kbDocs" row-key="id" :pagination="false" size="small">
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'file_name'">
              {{ record.file_name || record.filename || '-' }}
            </template>
            <template v-else-if="column.key === 'size'">
              {{ formatSize(record.size) }}
            </template>
            <template v-else-if="column.key === 'actions'">
              <a-button size="small" danger @click="removeDoc(record)">删除</a-button>
            </template>
          </template>
        </a-table>
      </a-spin>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { UploadOutlined } from '@ant-design/icons-vue'
import request from '@/utils/request'
import { adminApi } from '@/api/admin'
import './admin.css'

const loading = ref(false)
const submitting = ref(false)
const personas = ref<any[]>([])

const columns = [
  { title: 'ID', key: 'id', dataIndex: 'id' },
  { title: '名称', key: 'name', dataIndex: 'name' },
  { title: '头衔', key: 'title', dataIndex: 'title' },
  { title: '所有者', key: 'owner' },
  { title: '操作', key: 'actions' },
]

const load = async () => {
  loading.value = true
  try {
    personas.value = await adminApi.personas()
  } finally {
    loading.value = false
  }
}

// --- Edit ---
const editOpen = ref(false)
const editing = ref<any>(null)
const form = ref({ name: '', title: '', stance: '', bio: '', system_prompt: '' })

const openEdit = (record: any) => {
  editing.value = record
  form.value = {
    name: record.name || '',
    title: record.title || '',
    stance: record.stance || '',
    bio: record.bio || '',
    system_prompt: record.system_prompt || '',
  }
  editOpen.value = true
}

const submitEdit = async () => {
  if (!editing.value) return
  submitting.value = true
  try {
    await adminApi.updatePersona(editing.value.id, { ...form.value })
    message.success('智能体已更新')
    editOpen.value = false
    await load()
  } finally {
    submitting.value = false
  }
}

// --- Knowledge ---
const kbOpen = ref(false)
const kbLoading = ref(false)
const kbUploading = ref(false)
const kbInputRef = ref<HTMLInputElement | null>(null)
const kbTarget = ref<any>(null)
const kbDocs = ref<any[]>([])
const kbColumns = [
  { title: '文件名', key: 'file_name' },
  { title: '大小', key: 'size' },
  { title: '操作', key: 'actions' },
]

const formatSize = (size?: number) => {
  if (!size) return '-'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

const openKnowledge = async (record: any) => {
  kbTarget.value = record
  kbOpen.value = true
  kbLoading.value = true
  try {
    kbDocs.value = await adminApi.personaKnowledge(record.id)
  } finally {
    kbLoading.value = false
  }
}

const removeDoc = async (doc: any) => {
  await adminApi.deleteKnowledge(doc.id)
  message.success('知识库文件已删除')
  kbDocs.value = kbDocs.value.filter((d) => d.id !== doc.id)
}

const triggerKbUpload = () => kbInputRef.value?.click()

const handleKbFileChange = async (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file || !kbTarget.value) return
  const formData = new FormData()
  formData.append('file', file, file.name)
  kbUploading.value = true
  try {
    await request.post(
      `/personas/${kbTarget.value.id}/knowledge`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    )
    message.success('知识库资料已上传')
    await openKnowledge(kbTarget.value)
  } finally {
    kbUploading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.kb-toolbar {
  margin-bottom: 12px;
}
</style>
