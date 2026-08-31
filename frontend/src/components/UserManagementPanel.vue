<template>
  <section class="user-management-panel">
    <div class="panel-header">
      <div>
        <h2>用户管理</h2>
        <p>超级管理员创建账号、控制启停用、调整角色、重置密码并治理公开注册。</p>
      </div>
      <div class="panel-actions">
        <el-button @click="loadUsers">刷新</el-button>
        <el-button type="primary" @click="openCreateDialog">创建用户</el-button>
      </div>
    </div>

    <el-card shadow="never" class="signup-setting-card">
      <div class="table-header">
        <div><strong>公开注册</strong><p>关闭后只阻止新的匿名注册，不影响登录和代创建账号。</p></div>
        <el-switch v-model="publicSignupEnabled" :loading="signupSettingLoading" @change="updatePublicSignupSetting" />
      </div>
    </el-card>

    <el-alert
      title="审计已覆盖登录成功/失败、创建用户、启停用、角色变更、重置密码和用户自助改密。"
      type="info"
      :closable="false"
      show-icon
      class="panel-alert"
    />

    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" :model="filters" class="filters">
        <el-form-item label="关键字">
          <el-input
            v-model="filters.q"
            clearable
            placeholder="用户名 / 历史手机号 / 昵称"
            @keyup.enter="loadUsers"
          />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="filters.role" clearable placeholder="全部角色">
            <el-option v-for="item in roleOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" clearable placeholder="全部状态">
            <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadUsers">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="table-header">
          <span>用户列表</span>
          <span class="count-text">共 {{ total }} 条</span>
        </div>
      </template>

      <el-table v-loading="loading" :data="users" border>
        <el-table-column prop="display_name" label="昵称" min-width="140" />
        <el-table-column prop="username" label="用户名" min-width="150" />
        <el-table-column prop="phone" label="历史手机号" min-width="150" />
        <el-table-column label="角色" min-width="120">
          <template #default="{ row }">
            <el-tag :type="roleTagType(row.role)">{{ roleLabel(row.role) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" min-width="180">
          <template #default="{ row }">
            <div class="status-cell">
              <el-tag :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
              <span v-if="row.status === 'disabled'" class="status-note">已禁用，无法登录</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="最近登录" min-width="170">
          <template #default="{ row }">
            <span class="datetime-cell">{{ formatLastLogin(row.last_login_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="260" fixed="right">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button link type="primary" @click="openRoleDialog(row)">修改角色</el-button>
              <el-button link type="warning" @click="openResetPasswordDialog(row)">重置密码</el-button>
              <el-button
                link
                :type="row.status === 'disabled' ? 'success' : 'danger'"
                @click="toggleUserStatus(row)"
              >
                {{ row.status === 'disabled' ? '启用' : '禁用' }}
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="createDialogVisible" title="创建用户" width="520px" destroy-on-close>
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-position="top">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="createForm.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="昵称" prop="display_name">
          <el-input v-model="createForm.display_name" placeholder="选填，默认等于用户名" />
        </el-form-item>
        <el-form-item label="初始密码" prop="password">
          <el-input v-model="createForm.password" type="password" show-password placeholder="请输入初始密码" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="createForm.role" placeholder="请选择角色">
            <el-option v-for="item in createRoleOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-alert
          title="密码为 6～64 个可打印 ASCII 字符；用户忘记密码时由超级管理员重置。"
          type="warning"
          :closable="false"
          show-icon
        />
      </el-form>
      <template #footer>
        <div class="dialog-actions">
          <el-button @click="createDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="submittingCreate" @click="submitCreateUser">创建</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog v-model="roleDialogVisible" title="修改角色" width="420px" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="目标用户">
          <el-input :model-value="selectedUserLabel" disabled />
        </el-form-item>
        <el-form-item label="新角色">
          <el-select v-model="roleForm.role" placeholder="请选择角色">
            <el-option v-for="item in roleOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-actions">
          <el-button @click="roleDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="submittingRole" @click="submitRoleChange">保存</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog v-model="resetPasswordDialogVisible" title="重置密码" width="460px" destroy-on-close>
      <el-form ref="resetPasswordFormRef" :model="resetPasswordForm" :rules="resetPasswordRules" label-position="top">
        <el-form-item label="目标用户">
          <el-input :model-value="selectedUserLabel" disabled />
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input
            v-model="resetPasswordForm.new_password"
            type="password"
            show-password
            placeholder="请输入新的临时密码"
          />
        </el-form-item>
        <el-alert
          title="当前不开放自助找回密码，请通过管理员重置并通知用户及时修改。"
          type="warning"
          :closable="false"
          show-icon
        />
      </el-form>
      <template #footer>
        <div class="dialog-actions">
          <el-button @click="resetPasswordDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="submittingResetPassword" @click="submitResetPassword">
            重置密码
          </el-button>
        </div>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import { API_V1_BASE_URL } from '../config/api'
import { readStringQuery, replaceQueryValues } from '../utils/urlQueryState'
import { formatDateTime } from '../utils/formatDateTime'

const loading = ref(false)
const users = ref([])
const total = ref(0)

const createDialogVisible = ref(false)
const roleDialogVisible = ref(false)
const resetPasswordDialogVisible = ref(false)
const submittingCreate = ref(false)
const submittingRole = ref(false)
const submittingResetPassword = ref(false)
const signupSettingLoading = ref(false)
const publicSignupEnabled = ref(false)

const createFormRef = ref(null)
const resetPasswordFormRef = ref(null)
const selectedUser = ref(null)

const filters = reactive({
  q: '',
  role: '',
  status: ''
})

const createForm = reactive({
  username: '',
  display_name: '',
  password: '',
  role: 'user'
})

const roleForm = reactive({
  role: 'user'
})

const resetPasswordForm = reactive({
  new_password: ''
})

const roleOptions = [
  { label: '普通用户', value: 'user' },
  { label: '管理员', value: 'admin' },
  { label: '超级管理员', value: 'super_admin' }
]
const createRoleOptions = roleOptions.filter((item) => item.value !== 'super_admin')

const statusOptions = [
  { label: '启用', value: 'active' },
  { label: '禁用', value: 'disabled' }
]

// #75：筛选条件与 ?user_q= / ?user_role= / ?user_status= 同步，挂载时恢复。
// 角色/状态只接受合法枚举值——URL 被手改成未知值时按未筛选处理，
// 避免把脏值原样发给后端或显示成裸枚举。重置按钮清空 filters 即自动清参数。
const route = useRoute()
const router = useRouter()

const applyFiltersFromRoute = () => {
  filters.q = readStringQuery(route, 'user_q')
  const queryRole = readStringQuery(route, 'user_role')
  filters.role = roleOptions.some((item) => item.value === queryRole) ? queryRole : ''
  const queryStatus = readStringQuery(route, 'user_status')
  filters.status = statusOptions.some((item) => item.value === queryStatus) ? queryStatus : ''
}

applyFiltersFromRoute()

watch(filters, () => {
  replaceQueryValues(router, route, {
    user_q: filters.q,
    user_role: filters.role,
    user_status: filters.status
  })
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
const createRules = {
  username: [{ validator: validateAccountName(true, '用户名'), trigger: 'blur' }],
  display_name: [{ validator: validateAccountName(false, '昵称'), trigger: 'blur' }],
  password: [{ validator: validatePassword, trigger: 'blur' }]
}

const resetPasswordRules = {
  new_password: [{ validator: validatePassword, trigger: 'blur' }]
}

const selectedUserLabel = computed(() => {
  if (!selectedUser.value) {
    return ''
  }
  return `${selectedUser.value.display_name} / ${selectedUser.value.username}`
})

const getErrorMessage = (error) => {
  const detail = error.response?.data?.detail
  if (detail && typeof detail === 'string') {
    return detail
  }
  return '操作失败，请稍后重试。'
}

const roleLabel = (role) => roleOptions.find((item) => item.value === role)?.label || role

const roleTagType = (role) => {
  if (role === 'super_admin') {
    return 'danger'
  }
  if (role === 'admin') {
    return 'warning'
  }
  return 'info'
}

const statusLabel = (status) => {
  if (status === 'active') {
    return '已启用'
  }
  if (status === 'disabled') {
    return '已禁用'
  }
  return status
}

const statusTagType = (status) => {
  if (status === 'active') {
    return 'success'
  }
  if (status === 'disabled') {
    return 'danger'
  }
  return 'warning'
}

// 时间格式统一走共享工具（#76）；「从未登录」作为空值占位文案保留。
const formatLastLogin = (value) => formatDateTime(value, '从未登录')

const buildQueryParams = () => {
  const params = { skip: 0, limit: 100 }
  if (filters.q) {
    params.q = filters.q.trim()
  }
  if (filters.role) {
    params.role = filters.role
  }
  if (filters.status) {
    params.status = filters.status
  }
  return params
}

const resetFilters = () => {
  filters.q = ''
  filters.role = ''
  filters.status = ''
  loadUsers()
}

const loadUsers = async () => {
  loading.value = true
  try {
    const response = await axios.get(`${API_V1_BASE_URL}/admin/users`, {
      params: buildQueryParams()
    })
    users.value = response.data?.items || []
    total.value = response.data?.total || 0
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

const loadPublicSignupSetting = async () => {
  signupSettingLoading.value = true
  try {
    const response = await axios.get(`${API_V1_BASE_URL}/admin/users/settings/public-signup`)
    publicSignupEnabled.value = Boolean(response.data?.public_signup_enabled)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    signupSettingLoading.value = false
  }
}

const updatePublicSignupSetting = async (enabled) => {
  if (enabled) {
    try {
      await ElMessageBox.confirm('开启后匿名访客可立即注册普通用户，确认开启吗？', '开启公开注册', { type: 'warning' })
    } catch {
      publicSignupEnabled.value = false
      return
    }
  }
  signupSettingLoading.value = true
  try {
    await axios.put(`${API_V1_BASE_URL}/admin/users/settings/public-signup`, { public_signup_enabled: enabled })
    ElMessage.success(enabled ? '公开注册已开启。' : '公开注册已关闭。')
  } catch (error) {
    publicSignupEnabled.value = !enabled
    ElMessage.error(getErrorMessage(error))
  } finally {
    signupSettingLoading.value = false
  }
}

const openCreateDialog = () => {
  createForm.username = ''
  createForm.display_name = ''
  createForm.password = ''
  createForm.role = 'user'
  createDialogVisible.value = true
}

const submitCreateUser = async () => {
  if (!createFormRef.value) {
    return
  }

  const valid = await createFormRef.value.validate().then(() => true).catch(() => false)
  if (!valid) {
    return
  }

  submittingCreate.value = true
  try {
    await axios.post(`${API_V1_BASE_URL}/admin/users`, createForm)
    ElMessage.success('用户创建成功。')
    createDialogVisible.value = false
    loadUsers()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    submittingCreate.value = false
  }
}

const openRoleDialog = (user) => {
  selectedUser.value = user
  roleForm.role = user.role
  roleDialogVisible.value = true
}

const submitRoleChange = async () => {
  if (!selectedUser.value) {
    return
  }

  submittingRole.value = true
  try {
    await axios.patch(`${API_V1_BASE_URL}/admin/users/${selectedUser.value.id}/role`, {
      role: roleForm.role
    })
    ElMessage.success('角色更新成功。')
    roleDialogVisible.value = false
    loadUsers()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    submittingRole.value = false
  }
}

const openResetPasswordDialog = (user) => {
  selectedUser.value = user
  resetPasswordForm.new_password = ''
  resetPasswordDialogVisible.value = true
}

const submitResetPassword = async () => {
  if (!resetPasswordFormRef.value || !selectedUser.value) {
    return
  }

  const valid = await resetPasswordFormRef.value.validate().then(() => true).catch(() => false)
  if (!valid) {
    return
  }

  submittingResetPassword.value = true
  try {
    await axios.post(`${API_V1_BASE_URL}/admin/users/${selectedUser.value.id}/reset-password`, resetPasswordForm)
    ElMessage.success('密码已重置。请提醒用户及时修改。')
    resetPasswordDialogVisible.value = false
    loadUsers()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    submittingResetPassword.value = false
  }
}

const toggleUserStatus = async (user) => {
  const nextStatus = user.status === 'disabled' ? 'active' : 'disabled'
  const actionLabel = nextStatus === 'disabled' ? '禁用' : '启用'

  try {
    await ElMessageBox.confirm(
      nextStatus === 'disabled'
        ? `确认禁用 ${user.display_name} 吗？禁用后该用户将无法登录。`
        : `确认启用 ${user.display_name} 吗？`,
      `${actionLabel}用户`,
      {
        type: nextStatus === 'disabled' ? 'warning' : 'info'
      }
    )
  } catch {
    return
  }

  try {
    await axios.patch(`${API_V1_BASE_URL}/admin/users/${user.id}/status`, {
      status: nextStatus
    })
    ElMessage.success(`${actionLabel}成功。`)
    loadUsers()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

onMounted(() => {
  loadUsers()
  loadPublicSignupSetting()
})
</script>

<style scoped lang="scss">
.user-management-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.panel-header,
.table-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.panel-header h2 {
  margin: 0 0 8px;
  font-size: 26px;
  color: #17323f;
}

.panel-header p {
  margin: 0;
  color: #5c7077;
  line-height: 1.7;
}

.panel-actions {
  display: flex;
  gap: 12px;
}

.panel-alert,
.filter-card,
.table-card {
  border-radius: 18px;
}

.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 0;
}

.status-cell {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.status-note {
  color: #60727a;
  font-size: 12px;
  line-height: 1.5;
}

/* 时间/计数列用等宽数字，行间纵向对齐（#76） */
.datetime-cell,
.count-text {
  font-variant-numeric: tabular-nums;
}

.row-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

@media (max-width: 900px) {
  .panel-header,
  .table-header {
    flex-direction: column;
  }

  .panel-actions {
    width: 100%;
  }
}
</style>
