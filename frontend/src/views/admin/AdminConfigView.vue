<template>
  <div class="admin-page">
    <section class="page-band">
      <div>
        <h1>模型与计费配置</h1>
        <p>数据库配置优先于 .env，保存后即时生效；留空则回退到环境变量默认值。</p>
      </div>
    </section>

    <a-spin :spinning="loading">
      <section v-for="group in grouped" :key="group.category" class="panel">
        <h2 class="panel-title">{{ group.label }}</h2>
        <div v-for="item in group.items" :key="item.key" class="config-row">
          <div class="config-meta">
            <div class="config-label">{{ item.label || item.key }}</div>
            <div class="config-desc">{{ item.description || item.key }}</div>
          </div>
          <a-input-password
            v-if="isSecret(item.key)"
            v-model:value="drafts[item.key]"
            placeholder="留空使用环境变量"
          />
          <a-input
            v-else
            v-model:value="drafts[item.key]"
            placeholder="留空使用环境变量"
          />
          <a-button type="primary" ghost :loading="savingKey === item.key" @click="save(item)">
            保存
          </a-button>
        </div>
      </section>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { adminApi, type AdminConfig } from '@/api/admin'
import './admin.css'

const loading = ref(false)
const savingKey = ref<string | null>(null)
const rows = ref<AdminConfig[]>([])
const drafts = ref<Record<string, string>>({})

const CATEGORY_LABELS: Record<string, string> = {
  llm: '大模型接入',
  credit: '计费规则',
}

const grouped = computed(() => {
  const map = new Map<string, AdminConfig[]>()
  for (const item of rows.value) {
    const cat = item.category || 'other'
    if (!map.has(cat)) map.set(cat, [])
    map.get(cat)!.push(item)
  }
  return Array.from(map.entries()).map(([category, items]) => ({
    category,
    label: CATEGORY_LABELS[category] || category,
    items,
  }))
})

const isSecret = (key: string) => key.includes('api_key')

const load = async () => {
  loading.value = true
  try {
    rows.value = await adminApi.configs()
    const draft: Record<string, string> = {}
    for (const item of rows.value) draft[item.key] = item.value ?? ''
    drafts.value = draft
  } finally {
    loading.value = false
  }
}

const save = async (item: AdminConfig) => {
  savingKey.value = item.key
  try {
    const value = drafts.value[item.key] ?? ''
    await adminApi.updateConfig(item.key, value === '' ? null : value)
    message.success('配置已保存，即时生效')
    await load()
  } finally {
    savingKey.value = null
  }
}

onMounted(load)
</script>
