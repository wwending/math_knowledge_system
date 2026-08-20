<template>
  <div class="login-container">
    <section class="login-left">
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

    <section class="login-right">
      <div class="form-wrapper">
        <h2>欢迎回来</h2>
        <p class="form-tip">请输入手机号和密码登录系统</p>

        <el-alert
          type="info"
          :closable="false"
          show-icon
          class="login-alert"
          :title="capabilityMessage"
        />

        <el-form
          ref="loginFormRef"
          :model="loginForm"
          :rules="rules"
          size="large"
          class="login-form"
        >
          <el-form-item prop="phone">
            <el-input
              v-model="loginForm.phone"
              placeholder="手机号"
              :prefix-icon="Iphone"
              @keyup.enter="handleLogin"
            />
          </el-form-item>

          <el-form-item prop="password">
            <el-input
              v-model="loginForm.password"
              type="password"
              placeholder="密码"
              show-password
              :prefix-icon="Lock"
              @keyup.enter="handleLogin"
            />
          </el-form-item>

          <p class="password-help">忘记密码暂不开放自助找回，请联系管理员。</p>

          <el-form-item>
            <el-button type="primary" class="login-btn" :loading="loading" @click="handleLogin">
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
import { DataAnalysis, Iphone, Lock } from '@element-plus/icons-vue'

import { getPublicSignupCapabilityState, login, resolvePublicSignupCapability } from '../utils/auth'

const route = useRoute()
const router = useRouter()
const loginFormRef = ref(null)
const loading = ref(false)

const loginForm = reactive({
  phone: '',
  password: ''
})

const rules = {
  phone: [{ required: true, message: '请输入手机号', trigger: 'blur' }],
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
    return '正在确认注册状态...'
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
    return detail || '手机号或密码错误。'
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
      phone: loginForm.phone,
      password: loginForm.password
    })
    ElMessage.success('登录成功。')
    router.replace(
      result?.user?.must_change_password || result?.user?.status === 'pending_password_change'
        ? '/change-password'
        : '/'
    )
  } catch (error) {
    ElMessage.error(getLoginErrorMessage(error))
  } finally {
    loading.value = false
  }
}

watch(
  () => route.query.phone,
  (phone) => {
    if (typeof phone === 'string' && phone.trim()) {
      loginForm.phone = phone.trim()
    }
  },
  { immediate: true }
)

onMounted(() => {
  syncCapabilities()
})
</script>

<style scoped lang="scss">
.login-container {
  display: flex;
  min-height: 100vh;
  width: 100%;
  overflow: hidden;
  background: #f5f7fa;
}

.login-left {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  color: #fff;
  background: linear-gradient(135deg, #1c2434 0%, #2c3e50 100%);

  .brand-content {
    z-index: 1;
    max-width: 420px;
    padding: 0 32px;
    text-align: center;
  }

  .logo-circle {
    display: flex;
    width: 80px;
    height: 80px;
    margin: 0 auto 20px;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.1);
    backdrop-filter: blur(10px);
  }

  h1 {
    margin: 0 0 10px;
    font-size: 36px;
    font-weight: 600;
    letter-spacing: 2px;
  }

  .subtitle {
    margin: 0 0 32px;
    font-size: 18px;
    opacity: 0.9;
  }

  .desc {
    display: inline-block;
    margin: 0;
    padding-top: 20px;
    border-top: 1px solid rgba(255, 255, 255, 0.2);
    font-size: 14px;
    line-height: 1.7;
    opacity: 0.72;
  }

  .bg-circle {
    position: absolute;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.03);
  }

  .circle-1 {
    top: -100px;
    left: -100px;
    width: 400px;
    height: 400px;
  }

  .circle-2 {
    right: -200px;
    bottom: -200px;
    width: 600px;
    height: 600px;
  }
}

.login-right {
  display: flex;
  width: 500px;
  padding: 40px;
  align-items: center;
  justify-content: center;
  background: #fff;

  .form-wrapper {
    width: 100%;
    max-width: 360px;
  }

  h2 {
    margin: 0 0 10px;
    font-size: 28px;
    color: #333;
  }

  .form-tip {
    margin: 0 0 24px;
    color: #999;
    font-size: 14px;
  }
}

.login-alert {
  margin-bottom: 20px;
}

.password-help {
  margin: 0 0 18px;
  color: #8d96a0;
  font-size: 13px;
  line-height: 1.6;
}

.login-btn {
  width: 100%;
  height: 44px;
  border-radius: 8px;
  border-color: #2c3e50;
  background-color: #2c3e50;
  font-size: 16px;

  &:hover {
    border-color: #34495e;
    background-color: #34495e;
  }
}

.form-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 10px;
  font-size: 14px;
}

.footer-text,
.footer-note {
  color: #7b8794;
}

.footer-link {
  color: #2c3e50;
  text-decoration: none;

  &:hover {
    color: #1f2d3d;
  }
}

@media (max-width: 768px) {
  .login-left {
    display: none;
  }

  .login-right {
    width: 100%;
    padding: 24px;
  }
}
</style>
