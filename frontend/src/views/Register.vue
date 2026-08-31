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
          创建账号后即可使用题目录入、题库和组卷功能。
        </p>
      </div>
      <div class="bg-circle circle-1"></div>
      <div class="bg-circle circle-2"></div>
    </section>

    <section class="auth-right">
      <div class="form-wrapper">
        <template v-if="publicSignupCapability.loading">
          <h2>正在确认注册状态</h2>
          <p class="form-tip">正在确认当前是否开放注册，请稍后。</p>

          <el-alert
            type="info"
            :closable="false"
            show-icon
            class="auth-alert"
            title="正在确认当前是否开放注册，请稍后。"
          />

          <div class="form-footer single-action">
            <router-link to="/login" class="footer-link">返回登录</router-link>
          </div>
        </template>

        <template v-else-if="publicSignupCapability.enabled">
          <h2>注册新账号</h2>
          <p class="form-tip">请填写用户名、昵称（选填）和密码</p>

          <el-alert
            type="info"
            :closable="false"
            show-icon
            class="auth-alert"
            title="注册成功后将返回登录页，并自动带回用户名。"
          />

          <el-form
            ref="registerFormRef"
            :model="registerForm"
            :rules="rules"
            size="large"
            class="register-form"
          >
            <el-form-item prop="username">
              <el-input
                v-model="registerForm.username"
                name="username"
                autocomplete="username"
                :spellcheck="false"
                aria-label="用户名"
                placeholder="用户名"
                :prefix-icon="User"
              />
            </el-form-item>

            <el-form-item prop="displayName">
              <el-input
                v-model="registerForm.displayName"
                name="displayName"
                autocomplete="name"
                aria-label="昵称（选填）"
                placeholder="昵称（选填，默认等于用户名）"
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
              />
            </el-form-item>

            <el-form-item prop="confirmPassword">
              <el-input
                v-model="registerForm.confirmPassword"
                type="password"
                name="confirmPassword"
                autocomplete="new-password"
                aria-label="确认密码"
                placeholder="确认密码"
                show-password
                :prefix-icon="Lock"
                @keyup.enter="handleRegister"
              />
            </el-form-item>

            <!-- #77: 密码规则前置展示，与改密页文案一致，避免提交失败才得知要求。 -->
            <div class="password-rules">
              <span>密码要求：6～64 个可打印 ASCII 字符，不能全部为空格。</span>
            </div>

            <el-form-item>
              <el-button type="primary" class="auth-btn" :loading="loading" @click="handleRegister">
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
            class="auth-alert"
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
import { DataAnalysis, Lock, User } from '@element-plus/icons-vue'

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
  username: '',
  displayName: '',
  password: '',
  confirmPassword: ''
})

const reservedNames = new Set(['admin', 'administrator', 'root', 'system', 'superadmin', 'super_admin', '管理员', '超级管理员', '系统'])
const accountNamePattern = /^[\p{Script=Han}A-Za-z0-9_]+$/u
const validateAccountName = (required, label) => (rule, value, callback) => {
  const normalized = String(value || '').trim().normalize('NFC')
  if (!normalized && !required) return callback()
  if (!normalized) return callback(new Error(`请输入${label}`))
  if (normalized.length > 32 || !accountNamePattern.test(normalized) || /^_+$/.test(normalized)) {
    return callback(new Error(`${label}须为 1～32 个中文、英文字母、数字或下划线，且不能全为下划线`))
  }
  if (reservedNames.has(normalized.toLocaleLowerCase('en-US'))) return callback(new Error(`${label}不能使用系统保留名`))
  callback()
}
const validatePassword = (rule, value, callback) => {
  if (!/^[\x20-\x7E]{6,64}$/.test(value || '') || !String(value || '').replaceAll(' ', '')) {
    return callback(new Error('密码须为 6～64 个可打印 ASCII 字符，且不能全部为空格'))
  }
  callback()
}
const validateConfirmPassword = (rule, value, callback) => {
  if (value !== registerForm.password) return callback(new Error('两次输入的密码不一致'))
  callback()
}
const rules = {
  username: [{ validator: validateAccountName(true, '用户名'), trigger: 'blur' }],
  displayName: [{ validator: validateAccountName(false, '昵称'), trigger: 'blur' }],
  password: [{ validator: validatePassword, trigger: 'blur' }],
  confirmPassword: [{ validator: validateConfirmPassword, trigger: 'blur' }]
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
    return '用户名已存在。'
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
      username: registerForm.username,
      displayName: registerForm.displayName,
      password: registerForm.password
    })
    ElMessage.success('注册成功，请使用新账号登录。')
    router.replace({
      path: '/login',
      query: { username: registerForm.username.trim() }
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
@use '../assets/auth-layout';

.single-action {
  justify-content: flex-end;
}

.password-rules {
  margin: -10px 0 18px;
  /* #77 引入的规则提示沿用批次一的次级灰标准：#767676 起满足 WCAG AA。 */
  color: #767676;
  font-size: 13px;
  line-height: 1.6;
}
</style>
