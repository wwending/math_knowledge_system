<template>
  <div class="login-container">
    <div class="login-left">
      <div class="brand-content">
        <div class="logo-circle">
          <el-icon :size="40"><DataAnalysis /></el-icon>
        </div>
        <h1>Math Knowledge</h1>
        <p class="subtitle">高中数学错题与知识管理</p>
        <p class="desc">真实登录已启用，失败时会返回明确提示</p>
      </div>
      <div class="bg-circle circle-1"></div>
      <div class="bg-circle circle-2"></div>
    </div>

    <div class="login-right">
      <div class="form-wrapper">
        <h2>欢迎回来</h2>
        <p class="form-tip">请输入用户名和密码登录系统</p>

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
              placeholder="用户名 / 邮箱"
              :prefix-icon="User"
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

          <el-form-item>
            <el-button
              type="primary"
              class="login-btn"
              :loading="loading"
              @click="handleLogin"
            >
              登录
            </el-button>
          </el-form-item>

          <div class="form-footer">
            <el-link type="info" :underline="false">忘记密码</el-link>
            <el-link type="primary" :underline="false">注册新账号</el-link>
          </div>
        </el-form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock, DataAnalysis } from '@element-plus/icons-vue'
import axios from 'axios'

import { API_V1_BASE_URL } from '../config/api'
import { clearAuthSession, setAccessToken } from '../utils/auth'

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

const getLoginErrorMessage = (error) => {
  const status = error.response?.status
  const detail = error.response?.data?.detail

  if (status === 401) {
    return detail || '用户名或密码错误'
  }
  if (status === 403) {
    return detail || '当前账号不可用，请联系管理员'
  }
  if (detail && typeof detail === 'string') {
    return detail
  }
  if (error.message === 'Missing access token') {
    return '登录响应无效，请稍后重试'
  }
  return '登录失败，请检查网络或稍后重试'
}

const handleLogin = async () => {
  if (!loginFormRef.value) return

  const isValid = await loginFormRef.value.validate().then(() => true).catch(() => false)
  if (!isValid) {
    return
  }

  loading.value = true
  try {
    const formData = new URLSearchParams()
    formData.append('username', loginForm.username)
    formData.append('password', loginForm.password)

    const res = await axios.post(`${API_V1_BASE_URL}/auth/token`, formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      skipAuthRedirect: true
    })

    const accessToken = res.data?.access_token
    if (!accessToken) {
      throw new Error('Missing access token')
    }

    setAccessToken(accessToken)
    ElMessage.success('登录成功')
    router.replace('/')
  } catch (error) {
    clearAuthSession()
    ElMessage.error(getLoginErrorMessage(error))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="scss">
.login-container {
  display: flex;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  font-family: 'PingFang SC', 'Helvetica Neue', Helvetica, 'Microsoft YaHei', Arial;
}

.login-left {
  flex: 1;
  background: linear-gradient(135deg, #1c2434 0%, #2c3e50 100%);
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  overflow: hidden;

  .brand-content {
    z-index: 2;
    text-align: center;

    .logo-circle {
      width: 80px;
      height: 80px;
      background: rgba(255, 255, 255, 0.1);
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0 auto 20px;
      backdrop-filter: blur(10px);
    }

    h1 {
      font-size: 36px;
      font-weight: 600;
      margin-bottom: 10px;
      letter-spacing: 2px;
    }

    .subtitle {
      font-size: 18px;
      opacity: 0.9;
      margin-bottom: 40px;
    }

    .desc {
      font-size: 14px;
      opacity: 0.6;
      border-top: 1px solid rgba(255, 255, 255, 0.2);
      padding-top: 20px;
      display: inline-block;
    }
  }

  .bg-circle {
    position: absolute;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.03);
  }

  .circle-1 {
    width: 400px;
    height: 400px;
    top: -100px;
    left: -100px;
  }

  .circle-2 {
    width: 600px;
    height: 600px;
    bottom: -200px;
    right: -200px;
  }
}

.login-right {
  width: 500px;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;

  .form-wrapper {
    width: 100%;
    max-width: 360px;

    h2 {
      font-size: 28px;
      color: #333;
      margin-bottom: 10px;
    }

    .form-tip {
      color: #999;
      margin-bottom: 30px;
      font-size: 14px;
    }

    .login-btn {
      width: 100%;
      height: 44px;
      font-size: 16px;
      border-radius: 8px;
      background-color: #2c3e50;
      border-color: #2c3e50;

      &:hover {
        background-color: #34495e;
        border-color: #34495e;
      }
    }

    .form-footer {
      display: flex;
      justify-content: space-between;
      margin-top: 10px;
    }
  }
}

@media (max-width: 768px) {
  .login-left {
    display: none;
  }

  .login-right {
    width: 100%;
  }
}
</style>
