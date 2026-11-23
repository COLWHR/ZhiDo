<template>
  <div class="admin-page">
    <section class="page-band">
      <div>
        <h1>Skill 管理</h1>
        <p>维护全局技能的名称、分类、状态与描述说明。</p>
      </div>
    </section>

    <section class="panel">
      <a-table
        :columns="columns"
        :data-source="skills"
        :loading="loading"
        row-key="id"
        :pagination="{ pageSize: 15, showSizeChanger: false }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-tag :color="record.status === 'enabled' ? 'green' : 'default'">
              {{ record.status || '-' }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'description'">
            <span class="desc-cell">{{ record.description || '-' }}</span>
          </template>
          <template v-else-if="column.key === 'actions'">
            <a-button size="small" type="primary" ghost @click="openEdit(record)">编辑</a-button>
          </template>
        </template>
      </a-table>
    </section>

    <a-modal
      v-model:open="editOpen"
      :title="`编辑 Skill · ${editing?.skill_key || ''}`"
      width="min(640px, calc(100vw - 32px))"
      :confirm-loading="submitting"
      @ok="submitEdit"
    >
      <a-form layout="vertical" style="margin-top: 16px">
        <a-form-item label="名称">
          <a-input v-model:value="form.name" />
        </a-form-item>
        <a-form-item label="分类">
          <a-input v-model:value="form.category" />
        </a-form-item>
        <a-form-item label="状态">
          <a-select v-model:value="form.status" style="width: 100%">
            <a-select-option value="enabled">启用</a-select-option>
            <a-select-option value="disabled">停用</a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="form.description" :rows="4" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { adminApi } from '@/api/admin'
import './admin.css'

const loading = ref(false)
const submitting = ref(false)
const skills = ref<any[]>([])

const columns = [
  { title: 'Key', key: 'skill_key', dataIndex: 'skill_key' },
  { title: '名称', key: 'name', dataIndex: 'name' },
  { title: '分类', key: 'category', dataIndex: 'category' },
  { title: '状态', key: 'status' },
  { title: '描述', key: 'description' },
  { title: '操作', key: 'actions' },
]

const load = async () => {
  loading.value = true
  try {
    skills.value = await adminApi.skills()
  } finally {
    loading.value = false
  }
}

const editOpen = ref(false)
const editing = ref<any>(null)
const form = ref({ name: '', category: '', description: '', status: 'enabled' })

const openEdit = (record: any) => {
  editing.value = record
  form.value = {
    name: record.name || '',
    category: record.category || '',
    description: record.description || '',
    status: record.status === 'disabled' ? 'disabled' : 'enabled',
  }
  editOpen.value = true
}

const submitEdit = async () => {
  if (!editing.value) return
  submitting.value = true
  try {
    await adminApi.updateSkill(editing.value.id, { ...form.value })
    message.success('Skill 已更新')
    editOpen.value = false
    await load()
  } finally {
    submitting.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.desc-cell {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  color: #5b665f;
}
</style>
