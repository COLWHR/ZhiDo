<template>
  <div class="admin-page">
    <section class="page-band">
      <div>
        <h1>操作审计</h1>
        <p>后台关键写操作的留痕记录，便于追溯与复核。</p>
      </div>
    </section>

    <section class="panel">
      <a-table
        :columns="columns"
        :data-source="logs"
        :loading="loading"
        row-key="id"
        :pagination="{ pageSize: 20, showSizeChanger: false }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'action'">
            <a-tag color="blue">{{ record.action }}</a-tag>
          </template>
          <template v-else-if="column.key === 'detail'">
            <span class="detail-cell">{{ record.detail || '-' }}</span>
          </template>
        </template>
      </a-table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { adminApi } from '@/api/admin'
import './admin.css'

const loading = ref(false)
const logs = ref<any[]>([])

const columns = [
  { title: '时间', key: 'created_at', dataIndex: 'created_at' },
  { title: '操作人', key: 'actor_id', dataIndex: 'actor_id' },
  { title: '动作', key: 'action' },
  { title: '对象类型', key: 'target_type', dataIndex: 'target_type' },
  { title: '对象 ID', key: 'target_id', dataIndex: 'target_id' },
  { title: '详情', key: 'detail' },
]

const load = async () => {
  loading.value = true
  try {
    logs.value = await adminApi.auditLogs(200)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.detail-cell {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  color: #5b665f;
}
</style>
