<template>
  <div class="change-password-page">
    <el-card class="change-password-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <div>
            <h1>{{ pageTitle }}</h1>
            <p>{{ pageDescription }}</p>
          </div>
        </div>
      </template>

      <el-alert
        title="如遗忘原密码，当前不开放自助找回，请联系管理员重置。"
        type="info"
        :closable="false"
        show-icon
        class="page-alert"
      />

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" size="large">
        <el-form-item label="当前密码" prop="currentPassword">
          <el-input
            v-model="form.currentPassword"
            type="password"
            show-password
            placeholder="请输入当前密码"
          />
        </el-form-item>

        <el-form-item label="新密码" prop="newPassword">
          <el-input
            v-model="form.newPassword"
            type="password"
            show-password
            placeholder="请输入新密码"
          />
        </el-form-item>

        <el-form-item label="确认新密码" prop="confirmPassword">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            show-password
            placeholder="请再次输入新密码"
            @keyup.enter="handleSubmit"
          />
        </el-form-item>

        <div class="password-rules">
          <span>密码要求：6～64 个可打印 ASCII 字符，不能全部为空格。</span>
        </div>

        <div class="actions">
          <el-button @click="router.replace('/')">返回系统</el-button>
          <el-button type="primary" :loading="submitting" @click="handleSubmit">提交修改</el-button>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { changePassword } from '../utils/auth'

const router = useRouter()
const formRef = ref(null)
const submitting = ref(false)

const form = reactive({
  currentPassword: '',
  newPassword: '',
  confirmPassword: ''
})

const pageTitle = '修改密码'
const pageDescription = '为提升账户安全，请定期更新密码。'

const validateConfirmPassword = (rule, value, callback) => {
  if (!value) {
    callback(new Error('请再次输入新密码'))
    return
  }
  if (value !== form.newPassword) {
    callback(new Error('两次输入的新密码不一致'))
    return
  }
  callback()
}

const rules = {
  currentPassword: [{ required: true, message: '请输入当前密码', trigger: 'blur' }],
  newPassword: [{ required: true, message: '请输入新密码', trigger: 'blur' }],
  confirmPassword: [{ validator: validateConfirmPassword, trigger: 'blur' }]
}

const getErrorMessage = (error) => {
  const detail = error.response?.data?.detail
  if (detail && typeof detail === 'string') {
    return detail
  }
  return '密码修改失败，请稍后重试。'
}

const handleSubmit = async () => {
  if (!formRef.value) {
    return
  }

  const valid = await formRef.value.validate().then(() => true).catch(() => false)
  if (!valid) {
    return
  }

  submitting.value = true
  try {
    await changePassword({
      currentPassword: form.currentPassword,
      newPassword: form.newPassword
    })
    ElMessage.success('密码修改成功。')
    router.replace('/')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped lang="scss">
.change-password-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background:
    radial-gradient(circle at top left, rgba(15, 118, 110, 0.16), transparent 32%),
    linear-gradient(135deg, #f7f4ea 0%, #eef5f3 50%, #f7faf9 100%);
}

.change-password-card {
  width: min(100%, 560px);
  border-radius: 20px;
}

.card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;

  h1 {
    margin: 0 0 8px;
    font-size: 28px;
    color: #193243;
  }

  p {
    margin: 0;
    color: #56707c;
    line-height: 1.6;
  }
}

.page-alert {
  margin-bottom: 20px;
}

.password-rules {
  margin: 4px 0 20px;
  color: #5f6f75;
  font-size: 13px;
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

@media (max-width: 640px) {
  .change-password-page {
    padding: 16px;
  }

  .card-header {
    flex-direction: column;
  }

  .actions {
    flex-direction: column-reverse;
  }
}
</style>
