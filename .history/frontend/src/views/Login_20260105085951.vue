<template>
  <div class="login-container">
    <div class="login-left">
      <div class="brand-content">
        <div class="logo-circle">
          <el-icon :size="40"><DataAnalysis /></el-icon>
        </div>
        <h1>Math Knowledge</h1>
        <p class="subtitle">高中数学错题与知识图谱系统</p>
        <p class="desc">AI 赋能 · 智能 OCR · 知识点自动分类</p>
      </div>
      <div class="bg-circle circle-1"></div>
      <div class="bg-circle circle-2"></div>
    </div>

    <div class="login-right">
      <div class="form-wrapper">
        <h2>欢迎回来 👋</h2>
        <p class="form-tip">请输入您的账号密码登录系统</p>

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
              登 录
            </el-button>
          </el-form-item>
          
          <div class="form-footer">
            <el-link type="info" :underline="false">忘记密码？</el-link>
            <el-link type="primary" :underline="false">注册新账号</el-link>
          </div>
        </el-form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock, DataAnalysis } from '@element-plus/icons-vue'
import axios from 'axios' // 确保你安装了 axios

const router = useRouter()
const loginFormRef = ref(null)
const loading = ref(false)

// 表单数据
const loginForm = reactive({
  username: '',
  password: ''
})

// 表单校验规则
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

// 登录逻辑
const handleLogin = async () => {
  if (!loginFormRef.value) return
  
  await loginFormRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true
      try {
        // ⚠️ 这里的 API 地址请根据你后端的实际情况修改
        // 假设是 OAuth2 标准格式： /api/v1/auth/token
        // const res = await axios.post('http://127.0.0.1:8000/api/v1/auth/token', 
        //   new URLSearchParams({
        //     username: loginForm.username,
        //     password: loginForm.password
        //   })
        // )

        // 🔥 模拟登录成功 (等你后端写好 Login 接口后，解开上面的注释)
        setTimeout(() => {
          localStorage.setItem('token', 'fake-jwt-token') // 存储 Token
          localStorage.setItem('username', loginForm.username)
          
          ElMessage.success('登录成功')
          router.push('/') // 跳转回首页
          loading.value = false
        }, 1000)

      } catch (error) {
        ElMessage.error('登录失败：账号或密码错误')
        loading.value = false
      }
    }
  })
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

/* 左侧样式 */
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

  /* 装饰背景圆 */
  .bg-circle {
    position: absolute;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.03);
  }
  .circle-1 { width: 400px; height: 400px; top: -100px; left: -100px; }
  .circle-2 { width: 600px; height: 600px; bottom: -200px; right: -200px; }
}

/* 右侧样式 */
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
      background-color: #2c3e50; /* 与左侧呼应 */
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

/* 响应式：手机端隐藏左侧 */
@media (max-width: 768px) {
  .login-left {
    display: none;
  }
  .login-right {
    width: 100%;
  }
}
</style>