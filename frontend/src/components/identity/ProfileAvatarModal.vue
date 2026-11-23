<template>
  <a-modal
    :open="open"
    title="个人资料"
    :width="440"
    :footer="null"
    :maskClosable="true"
    @cancel="close"
  >
    <div class="profile-card">
      <div class="profile-hero">
        <IdentityAvatar kind="user" :entity="authStore.user" size="xl" shape="circle" />
        <div class="profile-identity">
          <strong>{{ authStore.user?.username || '未登录' }}</strong>
          <span>ID {{ authStore.user?.id ?? '-' }} · {{ roleLabel }}</span>
        </div>
      </div>

      <div class="avatar-actions">
        <a-button type="primary" :loading="uploading" @click="pickFile">
          <picture-outlined />
          更换头像
        </a-button>
        <a-button :disabled="!authStore.user?.avatar || uploading" @click="resetAvatar">
          恢复默认
        </a-button>
        <input
          ref="fileInput"
          type="file"
          accept="image/jpeg,image/png,image/webp,image/gif,image/bmp"
          class="hidden-input"
          data-test="profile-avatar-file"
          @change="onFileChange"
        />
      </div>

      <div class="avatar-hint">
        上传前可拖动裁剪为 1:1，服务端会压缩为 512×512。支持 jpg / png / webp，最大 2MB。
        不设置头像时自动使用与学科匹配的内置插画人像。
      </div>
    </div>

    <AvatarCropModal
      v-model:open="cropOpen"
      :file="pendingFile"
      @confirm="uploadCropped"
    />
  </a-modal>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { message } from 'ant-design-vue'
import { PictureOutlined } from '@ant-design/icons-vue'
import request from '@/utils/request'
import { useAuthStore } from '@/stores/auth'
import IdentityAvatar from './IdentityAvatar.vue'
import AvatarCropModal from './AvatarCropModal.vue'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ (event: 'update:open', value: boolean): void }>()

const authStore = useAuthStore()
const fileInput = ref<HTMLInputElement | null>(null)
const pendingFile = ref<File | null>(null)
const cropOpen = ref(false)
const uploading = ref(false)

const roleLabel = computed(() => {
  switch (authStore.user?.role) {
    case 'admin': return '管理员'
    case 'god': return 'God 模式'
    case 'user': return '普通用户'
    default: return '访客'
  }
})

const close = () => emit('update:open', false)

const pickFile = () => fileInput.value?.click()

const onFileChange = (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (!file.type.startsWith('image/')) {
    message.error('请选择图片文件')
    return
  }
  if (file.size > 2 * 1024 * 1024) {
    message.error('头像不能超过 2MB')
    return
  }
  pendingFile.value = file
  cropOpen.value = true
}

const uploadCropped = async (file: File) => {
  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file, file.name)
    const res = await request.put('/users/me/avatar', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    authStore.setUser(res.data)
    message.success('头像已更新')
  } catch (error) {
    // interceptor already surfaces the message
  } finally {
    uploading.value = false
    pendingFile.value = null
  }
}

const resetAvatar = async () => {
  uploading.value = true
  try {
    const res = await request.delete('/users/me/avatar')
    authStore.setUser(res.data)
    message.success('已恢复默认头像')
  } catch (error) {
    // handled globally
  } finally {
    uploading.value = false
  }
}

defineExpose({ pickFile })
</script>

<style scoped>
.profile-card {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.profile-hero {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 18px;
  border-radius: 16px;
  background: linear-gradient(135deg, #f4f8f5, #ffffff);
  border: 1px solid #e6eeea;
}

.profile-identity {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.profile-identity strong {
  font-size: 16px;
  color: #1a1d1e;
}

.profile-identity span {
  font-size: 12px;
  color: #6b7280;
}

.avatar-actions {
  display: flex;
  gap: 10px;
}

.avatar-hint {
  font-size: 12px;
  line-height: 1.7;
  color: #6b7280;
  background: #f8faf9;
  border-radius: 10px;
  padding: 10px 12px;
}

.hidden-input {
  display: none;
}
</style>
