<template>
  <div class="auth-container">
    <section class="auth-left">
      <div class="brand-content">
        <div class="logo-circle">
          <el-icon :size="40"><DataAnalysis /></el-icon>
        </div>
        <h1>Math Knowledge</h1>
        <p class="subtitle">高中数学错题与知识图谱系统</p>
        <p class="desc">
          整理错题、识别知识点、沉淀题库并快速组卷。
        </p>
      </div>
      <div class="bg-circle circle-1"></div>
      <div class="bg-circle circle-2"></div>
    </section>

    <section class="auth-right">
      <div class="form-wrapper">
        <h2>欢迎回来</h2>
        <p class="form-tip">请输入用户名和密码登录系统（历史手机号账号仍可使用手机号）</p>

        <el-alert
          type="info"
          :closable="false"
          show-icon
          class="auth-alert"
          :title="capabilityMessage"
        />

        <el-form
          ref="loginFormRef"
          :model="loginForm"
          :rules="rules"
          size="large"
          class="login-form"
        >
          <el-form-item prop="username">
            <el-input
              v-model="loginForm.username"
              name="username"
              autocomplete="username"
              :spellcheck="false"
              aria-label="用户名"
              placeholder="用户名"
              :prefix-icon="User"
              @keyup.enter="handleLogin"
            />
          </el-form-item>

          <el-form-item prop="password">
            <el-input
              v-model="loginForm.password"
              type="password"
              name="password"
              autocomplete="current-password"
              aria-label="密码"
              placeholder="密码"
              show-password
              :prefix-icon="Lock"
              @keyup.enter="handleLogin"
            />
          </el-form-item>

          <p class="password-help">忘记密码暂不开放自助找回，请联系管理员。</p>

          <el-form-item>
            <el-button type="primary" class="auth-btn" :loading="loading" @click="handleLogin">
              登录
            </el-button>
          </el-form-item>

          <div class="form-footer">
            <span class="footer-text">{{ registerFooterText }}</span>
            <router-link v-if="publicSignupCapability.enabled" to="/register" class="footer-link">
              注册新账号
            </router-link>
            <span v-else class="footer-note">{{ registerClosedNote }}</span>
          </div>
        </el-form>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { DataAnalysis, Lock, User } from '@element-plus/icons-vue'

import { getPublicSignupCapabilityState, login, resolvePublicSignupCapability } from '../utils/auth'

const route = useRoute()
const router = useRouter()
const loginFormRef = ref(null)
const loading = ref(false)

const loginForm = reactive({
  username: '',
  password: ''
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const publicSignupCapability = computed(() => getPublicSignupCapabilityState())

const capabilityMessage = computed(() => {
  if (publicSignupCapability.value.loading) {
    return '正在获取注册状态，请稍后。'
  }
  if (publicSignupCapability.value.failed) {
    return '暂时无法获取注册状态，请稍后重试或联系管理员。'
  }

  return publicSignupCapability.value.enabled
    ? '当前支持自主注册，可直接创建账号。'
    : '当前暂未开放自主注册，请联系管理员开通账号。'
})

const registerFooterText = computed(() => {
  if (publicSignupCapability.value.loading) {
    return '正在确认注册状态…'
  }

  return publicSignupCapability.value.enabled ? '还没有账号？' : '需要新账号？'
})

const registerClosedNote = computed(() => (
  publicSignupCapability.value.loading ? '正在确认' : '请联系管理员开通账号'
))

const syncCapabilities = async () => {
  await resolvePublicSignupCapability({ force: true })
}

const getLoginErrorMessage = (error) => {
  const status = error.response?.status
  const detail = error.response?.data?.detail

  if (status === 401) {
    return detail || '用户名或密码错误。'
  }
  if (status === 403) {
    return detail || '当前账号暂不可用，请联系管理员。'
  }
  if (status === 429) {
    return detail || '登录失败次数过多，请稍后再试。'
  }
  if (detail && typeof detail === 'string') {
    return detail
  }
  if (error.message === 'Missing access token') {
    return '登录响应缺少有效会话，请稍后重试。'
  }
  if (typeof error.message === 'string' && error.message.trim()) {
    return error.message
  }
  return '登录失败，请检查网络后重试。'
}

const handleLogin = async () => {
  if (!loginFormRef.value) {
    return
  }

  const isValid = await loginFormRef.value.validate().then(() => true).catch(() => false)
  if (!isValid) {
    return
  }

  loading.value = true
  try {
    const result = await login({
      username: loginForm.username,
      password: loginForm.password
    })
    ElMessage.success('登录成功。')
    router.replace('/')
  } catch (error) {
    ElMessage.error(getLoginErrorMessage(error))
  } finally {
    loading.value = false
  }
}

watch(
  () => route.query.username,
  (username) => {
    if (typeof username === 'string' && username.trim()) {
      loginForm.username = username.trim()
    }
  },
  { immediate: true }
)

onMounted(() => {
  syncCapabilities()
})
</script>

<style scoped lang="scss">
@use '../assets/auth-layout';

.password-help {
  margin: 0 0 18px;
  color: #767676;
  font-size: 13px;
  line-height: 1.6;
}

.footer-note {
  color: #767676;
}
</style>
