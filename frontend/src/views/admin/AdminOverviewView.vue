<template>
  <div class="admin-page">
    <section class="page-band">
      <div>
        <h1>管理后台</h1>
        <p>账户积分、模型配置、智能体与 Skill 的统一运营中心。</p>
      </div>
    </section>

    <a-spin :spinning="loading">
      <section class="stat-grid">
        <div class="stat-card">
          <span class="stat-value">{{ credits.user_count ?? '-' }}</span>
          <span class="stat-label">注册用户</span>
        </div>
        <div class="stat-card">
          <span class="stat-value">{{ credits.total_balance ?? '-' }}</span>
          <span class="stat-label">账户积分总额</span>
        </div>
        <div class="stat-card">
          <span class="stat-value">{{ credits.total_issued ?? '-' }}</span>
          <span class="stat-label">累计发放积分</span>
        </div>
        <div class="stat-card">
          <span class="stat-value">{{ credits.total_consumed ?? '-' }}</span>
          <span class="stat-label">累计消耗积分</span>
        </div>
        <div class="stat-card">
          <span class="stat-value">{{ counts.personas ?? '-' }}</span>
          <span class="stat-label">智能体</span>
        </div>
        <div class="stat-card">
          <span class="stat-value">{{ counts.skills ?? '-' }}</span>
          <span class="stat-label">Skill</span>
        </div>
        <div class="stat-card">
          <span class="stat-value">{{ counts.forums ?? '-' }}</span>
          <span class="stat-label">圆桌场次</span>
        </div>
      </section>

      <section class="panel">
        <h2 class="panel-title">运营入口</h2>
        <div class="link-grid">
          <router-link to="/admin/users" class="link-card">
            <div class="link-title">用户与积分</div>
            <div class="link-desc">查看余额、调整额度、变更角色与积分流水</div>
          </router-link>
          <router-link to="/admin/config" class="link-card">
            <div class="link-title">模型与计费配置</div>
            <div class="link-desc">动态配置大模型 API、模型名与扣费标准</div>
          </router-link>
          <router-link to="/admin/personas" class="link-card">
            <div class="link-title">智能体管理</div>
            <div class="link-desc">编辑内置智能体提示词与挂载知识库</div>
          </router-link>
          <router-link to="/admin/skills" class="link-card">
            <div class="link-title">Skill 管理</div>
            <div class="link-desc">维护全局技能的描述、状态与参数</div>
          </router-link>
          <router-link to="/admin/audit" class="link-card">
            <div class="link-title">操作审计</div>
            <div class="link-desc">追溯后台关键操作记录</div>
          </router-link>
        </div>
      </section>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { adminApi } from '@/api/admin'
import './admin.css'

const loading = ref(false)
const credits = ref<Record<string, number>>({})
const counts = ref<Record<string, number>>({})

const load = async () => {
  loading.value = true
  try {
    const data = await adminApi.overview()
    credits.value = data.credits || {}
    counts.value = data.counts || {}
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
