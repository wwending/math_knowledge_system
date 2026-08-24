<template>
  <div class="register-container">
    <section class="register-left">
      <div class="brand-content">
        <div class="logo-circle">
          <el-icon :size="40"><DataAnalysis /></el-icon>
        </div>
        <h1>Math Knowledge</h1>
        <p class="subtitle">高中数学错题与知识图谱系统</p>
        <p class="desc">
          创建账号后即可使用题目录入、题库和组卷功能。
        </p>
      </div>
      <div class="bg-circle circle-1"></div>
      <div class="bg-circle circle-2"></div>
    </section>

    <section class="register-right">
      <div class="form-wrapper">
        <template v-if="publicSignupCapability.loading">
          <h2>正在确认注册状态</h2>
          <p class="form-tip">正在确认当前是否开放注册，请稍后。</p>

          <el-alert
            type="info"
            :closable="false"
            show-icon
            class="register-alert"
            title="正在确认当前是否开放注册，请稍后。"
          />

          <div class="form-footer single-action">
            <router-link to="/login" class="footer-link">返回登录</router-link>
          </div>
        </template>

        <template v-else-if="publicSignupCapability.enabled">
          <h2>注册新账号</h2>
          <p class="form-tip">请填写手机号、显示名称和密码</p>

          <el-alert
            type="info"
            :closable="false"
            show-icon
            class="register-alert"
            title="注册成功后将返回登录页，并自动带回手机号。"
          />

          <el-form
            ref="registerFormRef"
            :model="registerForm"
            :rules="rules"
            size="large"
            class="register-form"
          >
            <el-form-item prop="phone">
              <el-input
                v-model="registerForm.phone"
                name="phone"
                autocomplete="username"
                inputmode="numeric"
                :spellcheck="false"
                aria-label="手机号"
                placeholder="手机号"
                :prefix-icon="Iphone"
              />
            </el-form-item>

            <el-form-item prop="displayName">
              <el-input
                v-model="registerForm.displayName"
                name="displayName"
                autocomplete="name"
                aria-label="显示名称"
                placeholder="显示名称"
                :prefix-icon="User"
              />
            </el-form-item>

            <el-form-item prop="password">
              <el-input
                v-model="registerForm.password"
                type="password"
                name="password"
                autocomplete="new-password"
                aria-label="密码"
                placeholder="密码"
                show-password
                :prefix-icon="Lock"
                @keyup.enter="handleRegister"
              />
            </el-form-item>

            <el-form-item>
              <el-button type="primary" class="register-btn" :loading="loading" @click="handleRegister">
                注册
              </el-button>
            </el-form-item>

            <div class="form-footer">
              <span class="footer-text">已有账号？</span>
              <router-link to="/login" class="footer-link">返回登录</router-link>
            </div>
          </el-form>
        </template>

        <template v-else>
          <h2>{{ closedStateTitle }}</h2>
          <p class="form-tip">{{ closedStateTip }}</p>

          <el-alert
            :type="publicSignupCapability.failed ? 'warning' : 'info'"
            :closable="false"
            show-icon
            class="register-alert"
            :title="closedStateAlert"
          />

          <div class="form-footer single-action">
            <router-link to="/login" class="footer-link">返回登录</router-link>
          </div>
        </template>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { DataAnalysis, Iphone, Lock, User } from '@element-plus/icons-vue'

import {
  getPublicSignupCapabilityState,
  PUBLIC_SIGNUP_DISABLED_DETAIL,
  register,
  resolvePublicSignupCapability
} from '../utils/auth'

const router = useRouter()
const registerFormRef = ref(null)
const loading = ref(false)

const registerForm = reactive({
  phone: '',
  displayName: '',
  password: ''
})

const rules = {
  phone: [{ required: true, message: '请输入手机号', trigger: 'blur' }],
  displayName: [{ required: true, message: '请输入显示名称', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const publicSignupCapability = computed(() => getPublicSignupCapabilityState())

const closedStateTitle = computed(() => (
  publicSignupCapability.value.failed ? '暂时无法获取注册状态' : '当前暂未开放自主注册'
))

const closedStateTip = computed(() => (
  publicSignupCapability.value.failed
    ? '请稍后重试或联系管理员。'
    : '请联系管理员开通账号，或返回登录页继续使用已有账号。'
))

const closedStateAlert = computed(() => (
  publicSignupCapability.value.failed
    ? '暂时无法获取注册状态，请稍后重试或联系管理员。'
    : '当前暂未开放自主注册，请联系管理员开通账号。'
))

const syncPublicSignupCapability = async ({ force = false } = {}) => {
  await resolvePublicSignupCapability({ force })
}

const handleDisabledSignup = async () => {
  await syncPublicSignupCapability({ force: true })
  ElMessage.error('当前暂未开放自主注册，请联系管理员开通账号。')
  router.replace('/login')
}

const getRegisterErrorMessage = (error) => {
  const detail = error.response?.data?.detail

  if (detail === PUBLIC_SIGNUP_DISABLED_DETAIL || error.response?.status === 403) {
    return '当前暂未开放自主注册，请联系管理员开通账号。'
  }
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg).filter(Boolean).join('；') || '注册失败，请检查输入后重试。'
  }
  if (typeof detail === 'string' && detail.trim()) {
    return detail
  }
  if (error.response?.status === 409) {
    return '手机号已存在。'
  }
  return '注册失败，请稍后重试。'
}

const handleRegister = async () => {
  if (publicSignupCapability.value.loading || !publicSignupCapability.value.enabled || !registerFormRef.value) {
    return
  }

  const isValid = await registerFormRef.value.validate().then(() => true).catch(() => false)
  if (!isValid) {
    return
  }

  loading.value = true
  try {
    await register({
      phone: registerForm.phone,
      displayName: registerForm.displayName,
      password: registerForm.password
    })
    ElMessage.success('注册成功，请使用新账号登录。')
    router.replace({
      path: '/login',
      query: { phone: registerForm.phone.trim() }
    })
  } catch (error) {
    if (error.response?.data?.detail === PUBLIC_SIGNUP_DISABLED_DETAIL || error.response?.status === 403) {
      await handleDisabledSignup()
      return
    }
    ElMessage.error(getRegisterErrorMessage(error))
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (publicSignupCapability.value.status === 'idle') {
    syncPublicSignupCapability({ force: true })
  }
})
</script>

<style scoped lang="scss">
.register-container {
  display: flex;
  min-height: 100vh;
  width: 100%;
  overflow: hidden;
  background: #f5f7fa;
}

.register-left {
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

.register-right {
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
    color: #767676;
    font-size: 14px;
  }
}

.register-alert {
  margin-bottom: 20px;
}

.register-btn {
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

.single-action {
  justify-content: flex-end;
}

.footer-text {
  color: #767676;
}

.footer-link {
  color: #2c3e50;
  text-decoration: none;

  &:hover {
    color: #1f2d3d;
  }
}

@media (max-width: 768px) {
  .register-left {
    display: none;
  }

  .register-right {
    width: 100%;
    padding: 24px;
  }
}
</style>
