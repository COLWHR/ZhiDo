<template>
  <div class="team-list-page">
    <div class="page-header fade-in-up">
      <div class="header-content">
        <div class="header-icon">👥</div>
        <div class="header-title">
          <span class="title">我的团队</span>
          <span class="subtitle">把几位智能体拉进同一个群，@ 谁就由谁来接活</span>
        </div>
      </div>
      <a-button type="primary" size="large" @click="openModal" class="create-btn">
        <plus-outlined class="btn-icon" />
        <span>新建团队</span>
      </a-button>
    </div>

    <div class="team-content fade-in-up" style="animation-delay: 0.1s;">
      <a-spin :spinning="loading && teams.length === 0">
        <div v-if="teams.length === 0 && !loading" class="empty-state">
          <div class="empty-content">
            <div class="empty-icon">🎯</div>
            <p class="empty-text">还没有团队</p>
            <p class="empty-subtext">新建一个群，把学习、办公、生活上能搭把手的智能体都拉进来。</p>
            <a-button type="primary" size="large" @click="openModal" class="empty-create-btn">
              <plus-outlined /> 创建第一个团队
            </a-button>
          </div>
        </div>

        <div v-else class="team-grid">
          <a-card
            v-for="item in teams"
            :key="item.id"
            hoverable
            class="team-card glass-card"
            @click="enterTeam(item.id)"
          >
            <a-card-meta>
              <template #title>
                <div class="card-title">
                  <span class="topic">{{ item.name }}</span>
                </div>
              </template>
              <template #description>
                <div class="card-desc">
                  <span class="desc-item" v-if="item.description">{{ item.description }}</span>
                  <span class="desc-item">
                    <user-outlined />
                    {{ item.members.length }} 位成员
                  </span>
                </div>
              </template>
              <template #avatar>
                <a-avatar shape="square" size="large" :style="{ background: '#3bb36b' }" class="card-avatar">
                  {{ item.name[0] }}
                </a-avatar>
              </template>
            </a-card-meta>

            <div class="member-row">
              <IdentityAvatar
                v-for="m in item.members.slice(0, 5)"
                :key="m.persona_id"
                kind="persona"
                :entity="{ name: m.name, avatar: m.avatar }"
                :size="30"
                shape="circle"
              />
              <span v-if="item.members.length > 5" class="member-more">+{{ item.members.length - 5 }}</span>
            </div>

            <div class="card-footer" @click.stop>
              <a-popconfirm
                title="确定删除该团队吗？群聊记录会一并清除。"
                ok-text="确定"
                cancel-text="取消"
                @confirm="handleDelete(item.id)"
                @click.stop
              >
                <a-button type="text" danger size="small" class="delete-btn" @click.stop>
                  <delete-outlined /> 删除
                </a-button>
              </a-popconfirm>
              <span class="action-text" @click="enterTeam(item.id)">
                进入群聊 <arrow-right-outlined class="arrow-icon" />
              </span>
            </div>
          </a-card>
        </div>
      </a-spin>
    </div>

    <a-modal
      v-model:open="visible"
      title="新建团队"
      :confirmLoading="submitting"
      width="560px"
      :footer="null"
      class="create-modal"
    >
      <div class="modal-content">
        <a-form layout="vertical" :model="formState" class="create-form">
          <a-form-item label="团队名称" required>
            <a-input v-model:value="formState.name" placeholder="例如：学习攻坚小组" size="large" class="form-input" />
          </a-form-item>
          <a-form-item label="团队简介">
            <a-textarea v-model:value="formState.description" :rows="2" placeholder="这个团队主要帮你做什么（可选）" />
          </a-form-item>
          <a-form-item label="邀请成员" required>
            <a-select
              v-model:value="formState.persona_ids"
              mode="multiple"
              placeholder="选择加入团队的智能体"
              :options="personaOptions"
              :loading="personaStore.loading"
              size="large"
              style="width: 100%"
              class="form-select"
            >
              <template #option="{ label, avatar }">
                <div class="select-option">
                  <IdentityAvatar kind="persona" :entity="{ name: label, avatar }" :size="28" shape="square" />
                  <span>{{ label }}</span>
                </div>
              </template>
            </a-select>
            <div class="form-hint">💡 提示：群里只有被你 @ 的智能体才会发言，未被 @ 不会自动刷屏。</div>
          </a-form-item>

          <div class="modal-actions">
            <a-button size="large" @click="visible = false" class="cancel-btn">取消</a-button>
            <a-button type="primary" size="large" @click="handleOk" :loading="submitting" class="confirm-btn">
              创建团队
            </a-button>
          </div>
        </a-form>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { PlusOutlined, ArrowRightOutlined, DeleteOutlined, UserOutlined } from '@ant-design/icons-vue'
import IdentityAvatar from '@/components/identity/IdentityAvatar.vue'
import { teamApi, type Team } from '@/api/team'
import { usePersonaStore } from '@/stores/persona'

const router = useRouter()
const personaStore = usePersonaStore()

const teams = ref<Team[]>([])
const loading = ref(false)
const visible = ref(false)
const submitting = ref(false)

const formState = reactive({
  name: '',
  description: '',
  persona_ids: [] as number[],
})

const personaOptions = computed(() =>
  personaStore.personas.map((p) => ({ label: p.name, value: p.id, avatar: p.avatar })),
)

const fetchTeams = async () => {
  loading.value = true
  try {
    teams.value = await teamApi.list()
  } catch (error) {
    console.error('加载团队失败:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchTeams()
  personaStore.fetchPersonas()
})

const openModal = () => {
  formState.name = ''
  formState.description = ''
  formState.persona_ids = []
  visible.value = true
}

const handleOk = async () => {
  if (!formState.name.trim()) {
    message.warning('请输入团队名称')
    return
  }
  if (formState.persona_ids.length === 0) {
    message.warning('请至少选择一位成员')
    return
  }
  submitting.value = true
  try {
    const team = await teamApi.create({
      name: formState.name.trim(),
      description: formState.description.trim(),
      persona_ids: formState.persona_ids,
    })
    message.success('团队创建成功')
    visible.value = false
    router.push(`/teams/${team.id}`)
  } catch (error) {
    console.error('创建团队失败:', error)
  } finally {
    submitting.value = false
  }
}

const enterTeam = (id: number) => router.push(`/teams/${id}`)

const handleDelete = async (id: number) => {
  try {
    await teamApi.remove(id)
    message.success('团队已删除')
    teams.value = teams.value.filter((t) => t.id !== id)
  } catch (error) {
    console.error('删除团队失败:', error)
  }
}
</script>

<style scoped>
.team-list-page {
  padding: 28px 24px;
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
}

.header-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-icon {
  font-size: 34px;
}

.header-title {
  display: flex;
  flex-direction: column;
}

.title {
  font-size: 24px;
  font-weight: 700;
  color: #10213a;
}

.subtitle {
  margin-top: 4px;
  font-size: 13px;
  color: #64748b;
}

.team-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 18px;
}

.team-card {
  border-radius: 20px;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.topic {
  font-weight: 600;
  color: #10213a;
}

.card-desc {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  color: #64748b;
}

.desc-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.member-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 12px 0;
}

.member-more {
  font-size: 12px;
  color: #64748b;
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-top: 1px solid rgba(148, 163, 184, 0.18);
  padding-top: 12px;
}

.action-text {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #3bb36b;
  cursor: pointer;
}

.arrow-icon {
  font-size: 12px;
}

.empty-state {
  padding: 60px 20px;
  text-align: center;
}

.empty-icon {
  font-size: 44px;
  margin-bottom: 12px;
}

.empty-text {
  font-size: 16px;
  font-weight: 600;
  color: #10213a;
}

.empty-subtext {
  font-size: 13px;
  color: #64748b;
  margin: 6px 0 18px;
}

.form-hint {
  margin-top: 8px;
  font-size: 12px;
  color: #94a3b8;
}

.select-option {
  display: flex;
  align-items: center;
  gap: 10px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 18px;
}

@media (max-width: 768px) {
  .team-list-page {
    padding: 18px 14px;
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
