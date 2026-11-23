<template>
  <div class="admin-page">
    <section class="page-band">
      <div>
        <h1>用户与积分</h1>
        <p>预付费余额管理：调整额度、变更角色、查看积分流水。</p>
      </div>
    </section>

    <section class="toolbar">
      <a-input-search
        v-model:value="keyword"
        class="search"
        placeholder="搜索用户名"
        allow-clear
        @search="loadUsers"
        @change="onSearchInput"
      />
    </section>

    <section class="panel">
      <a-table
        :columns="columns"
        :data-source="users"
        :loading="loading"
        row-key="id"
        :pagination="{ pageSize: 15, showSizeChanger: false }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'role'">
            <a-tag :color="roleColor(record.role)">{{ roleLabel(record.role) }}</a-tag>
          </template>
          <template v-else-if="column.key === 'credits_balance'">
            <strong>{{ record.credits_balance }}</strong>
          </template>
          <template v-else-if="column.key === 'actions'">
            <a-button size="small" type="primary" ghost @click="openAdjust(record)">调额</a-button>
            <a-button size="small" style="margin-left: 8px" @click="openRole(record)">角色</a-button>
            <a-button size="small" type="link" @click="openTransactions(record)">流水</a-button>
          </template>
        </template>
      </a-table>
    </section>

    <a-modal v-model:open="adjustOpen" title="调整积分" :confirm-loading="submitting" @ok="submitAdjust">
      <a-form layout="vertical" style="margin-top: 16px">
        <a-form-item label="调整对象">
          <strong>{{ adjustTarget?.username }}</strong>（当前余额 {{ adjustTarget?.credits_balance }}）
        </a-form-item>
        <a-form-item label="变动数量（正数增加，负数扣减）">
          <a-input-number v-model:value="adjustAmount" :step="100" :min="-99999" style="width: 100%" />
        </a-form-item>
        <a-form-item label="备注">
          <a-input v-model:value="adjustNote" placeholder="可选，记录本次调整原因" />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal v-model:open="roleOpen" title="变更角色" :confirm-loading="submitting" @ok="submitRole">
      <a-form layout="vertical" style="margin-top: 16px">
        <a-form-item label="目标用户">
          <strong>{{ roleTarget?.username }}</strong>
        </a-form-item>
        <a-form-item label="角色">
          <a-select v-model:value="roleValue" style="width: 100%">
            <a-select-option value="user">普通用户</a-select-option>
            <a-select-option value="admin">管理员</a-select-option>
            <a-select-option value="god">God 模式</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>

    <a-drawer
      v-model:open="txOpen"
      :title="`积分流水 · ${txTarget?.username || ''}`"
      width="min(520px, 92vw)"
    >
      <a-spin :spinning="txLoading">
        <a-table :columns="txColumns" :data-source="transactions" row-key="id" :pagination="false" size="small">
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'change_amount'">
              <span :style="{ color: record.change_amount >= 0 ? '#3bb36b' : '#d4380d' }">
                {{ record.change_amount >= 0 ? '+' : '' }}{{ record.change_amount }}
              </span>
            </template>
            <template v-else-if="column.key === 'balance_after'">
              {{ record.balance_after }}
            </template>
            <template v-else-if="column.key === 'note'">
              {{ record.note || record.reason || '-' }}
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
import { adminApi, type AdminUser } from '@/api/admin'
import './admin.css'

const loading = ref(false)
const submitting = ref(false)
const users = ref<AdminUser[]>([])
const keyword = ref('')

const columns = [
  { title: 'ID', key: 'id', dataIndex: 'id' },
  { title: '用户名', key: 'username', dataIndex: 'username' },
  { title: '角色', key: 'role' },
  { title: '积分余额', key: 'credits_balance' },
  { title: '注册时间', key: 'created_at', dataIndex: 'created_at' },
  { title: '操作', key: 'actions' },
]

const roleLabel = (role: string) => ({ admin: '管理员', god: 'God', user: '普通用户' } as Record<string, string>)[role] || role
const roleColor = (role: string) => ({ admin: 'gold', god: 'purple', user: 'default' } as Record<string, string>)[role] || 'default'

let searchTimer: ReturnType<typeof setTimeout> | undefined

const onSearchInput = () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(loadUsers, 300)
}

const loadUsers = async () => {
  loading.value = true
  try {
    users.value = await adminApi.users({ keyword: keyword.value || undefined, limit: 100 })
  } finally {
    loading.value = false
  }
}

// --- Adjust credits ---
const adjustOpen = ref(false)
const adjustTarget = ref<AdminUser | null>(null)
const adjustAmount = ref<number>(0)
const adjustNote = ref('')

const openAdjust = (user: AdminUser) => {
  adjustTarget.value = user
  adjustAmount.value = 0
  adjustNote.value = ''
  adjustOpen.value = true
}

const submitAdjust = async () => {
  if (!adjustTarget.value) return
  submitting.value = true
  try {
    await adminApi.adjustCredits(adjustTarget.value.id, adjustAmount.value, adjustNote.value || undefined)
    message.success('积分已调整')
    adjustOpen.value = false
    await loadUsers()
  } finally {
    submitting.value = false
  }
}

// --- Role ---
const roleOpen = ref(false)
const roleTarget = ref<AdminUser | null>(null)
const roleValue = ref('user')

const openRole = (user: AdminUser) => {
  roleTarget.value = user
  roleValue.value = user.role
  roleOpen.value = true
}

const submitRole = async () => {
  if (!roleTarget.value) return
  submitting.value = true
  try {
    await adminApi.setRole(roleTarget.value.id, roleValue.value)
    message.success('角色已更新')
    roleOpen.value = false
    await loadUsers()
  } finally {
    submitting.value = false
  }
}

// --- Transactions ---
const txOpen = ref(false)
const txLoading = ref(false)
const txTarget = ref<AdminUser | null>(null)
const transactions = ref<any[]>([])
const txColumns = [
  { title: '变动', key: 'change_amount' },
  { title: '余额', key: 'balance_after' },
  { title: '类型', key: 'category', dataIndex: 'category' },
  { title: '备注', key: 'note' },
]

const openTransactions = async (user: AdminUser) => {
  txTarget.value = user
  txOpen.value = true
  txLoading.value = true
  try {
    transactions.value = await adminApi.userTransactions(user.id)
  } finally {
    txLoading.value = false
  }
}

onMounted(loadUsers)
</script>
