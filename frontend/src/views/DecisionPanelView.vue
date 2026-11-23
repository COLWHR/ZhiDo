<template>
  <div class="admin-page">
    <section class="page-band">
      <div>
        <h1>决策内核</h1>
        <p>意图路由小模型 · 三层决策链路可解释面板（模型达标 → 规则兜底 → 大模型仲裁）</p>
      </div>
    </section>

    <section class="stat-grid">
      <div class="stat-card">
        <span class="stat-label">本地模型状态</span>
        <span class="stat-value">{{ overview.dataset.model_available ? '已加载' : '规则兜底' }}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">三层链路准确率</span>
        <span class="stat-value">{{ formatPct(overview.evaluation.model?.accuracy) }}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">三层链路宏 F1</span>
        <span class="stat-value">{{ formatScore(overview.evaluation.model?.macro_f1) }}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">平均单条耗时</span>
        <span class="stat-value">{{ formatMs(overview.evaluation.ml_avg_ms_per_request) }}</span>
      </div>
    </section>

    <section class="panel">
      <h2 class="panel-title">离线评测对比（验证集）</h2>
      <a-table
        :columns="evalColumns"
        :data-source="evalRows"
        :loading="loading"
        row-key="key"
        :pagination="false"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'accuracy'">{{ formatPct(record.accuracy) }}</template>
          <template v-else-if="column.key === 'macro_f1'">{{ formatScore(record.macro_f1) }}</template>
        </template>
      </a-table>
    </section>

    <section class="panel">
      <h2 class="panel-title">最近决策记录</h2>
      <a-table
        :columns="logColumns"
        :data-source="overview.logs"
        :loading="loading"
        row-key="id"
        :pagination="{ pageSize: 15, showSizeChanger: false }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'label'">
            <a-tag color="green">{{ labelText(record.label) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'layer'">
            <a-tag :color="record.layer === 'model' ? 'blue' : 'orange'">{{ layerText(record.layer) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'confidence'">{{ formatPct(record.confidence) }}</template>
          <template v-else-if="column.key === 'elapsed_ms'">{{ formatMs(record.elapsed_ms) }}</template>
          <template v-else-if="column.key === 'text'">
            <span class="detail-cell">{{ record.text || '-' }}</span>
          </template>
        </template>
      </a-table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { decisionApi, type DecisionOverview } from '@/api/decision'
import './admin/admin.css'

const loading = ref(false)
const overview = ref<DecisionOverview>({
  dataset: { model_available: false, model_path: '', dataset_csv: '' },
  evaluation: {},
  logs: [],
})

const LABEL_TEXT: Record<string, string> = {
  chat: '闲聊对话',
  doc: '文档撰写',
  sheet: '表格清单',
  image: '配图/示意图',
  vision: '图片理解',
  risk: '风险拦截',
}

const labelText = (label: string | null) => (label ? LABEL_TEXT[label] || label : '-')
const layerText = (layer: string | null) => (layer === 'model' ? '小模型决策' : layer === 'rule' ? '规则兜底' : '-')

const formatPct = (v?: number | null) => (v == null ? '-' : `${(v * 100).toFixed(1)}%`)
const formatScore = (v?: number | null) => (v == null ? '-' : v.toFixed(3))
const formatMs = (v?: number | null) => (v == null ? '-' : `${v.toFixed(2)} ms`)

const evalColumns = [
  { title: '决策链路', key: 'name', dataIndex: 'name' },
  { title: '准确率', key: 'accuracy' },
  { title: '宏 F1', key: 'macro_f1' },
]

const evalRows = ref([
  {
    key: 'model',
    name: '三层链路（小模型 + 规则兜底）',
    accuracy: overview.value.evaluation.model?.accuracy,
    macro_f1: overview.value.evaluation.model?.macro_f1,
  },
  {
    key: 'rule',
    name: '纯规则基线',
    accuracy: overview.value.evaluation.rule_baseline?.accuracy,
    macro_f1: overview.value.evaluation.rule_baseline?.macro_f1,
  },
])

const logColumns = [
  { title: '时间', key: 'created_at', dataIndex: 'created_at' },
  { title: '场景', key: 'scope', dataIndex: 'scope' },
  { title: '诉求', key: 'text' },
  { title: '标签', key: 'label' },
  { title: '置信度', key: 'confidence' },
  { title: '决策层级', key: 'layer' },
  { title: '命中关键词', key: 'keyword', dataIndex: 'keyword' },
  { title: '耗时', key: 'elapsed_ms' },
]

const load = async () => {
  loading.value = true
  try {
    const data = await decisionApi.overview()
    overview.value = data
    evalRows.value = [
      {
        key: 'model',
        name: '三层链路（小模型 + 规则兜底）',
        accuracy: data.evaluation.model?.accuracy,
        macro_f1: data.evaluation.model?.macro_f1,
      },
      {
        key: 'rule',
        name: '纯规则基线',
        accuracy: data.evaluation.rule_baseline?.accuracy,
        macro_f1: data.evaluation.rule_baseline?.macro_f1,
      },
    ]
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
  max-width: 320px;
}
</style>
