<template>
  <section class="feedback-inbox-panel">
    <div class="panel-header">
      <div>
        <h2>反馈中心</h2>
        <p>使用中遇到的问题、想要的功能都可以随时提一句。处理结果和处理说明会同步显示在这里。</p>
      </div>
      <div class="panel-actions">
        <el-button @click="loadList">刷新</el-button>
        <el-button type="primary" @click="openCreateDialog">提交反馈</el-button>
      </div>
    </div>

    <el-alert
      title="反馈仅提交者本人和管理员可见。管理员会定期整理，可采纳的项会转入修复流程。"
      type="info"
      :closable="false"
      show-icon
      class="panel-alert"
    />

    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" :model="filters" class="filters">
        <el-form-item label="类型">
          <el-select v-model="filters.category" clearable placeholder="全部类型">
            <el-option v-for="item in categoryOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" clearable placeholder="全部状态">
            <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="adminMode" label="关键字">
          <el-input
            v-model="filters.q"
            clearable
            placeholder="内容 / 昵称 / 手机号"
            @keyup.enter="loadList"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadList">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="table-header">
          <span>{{ adminMode ? '全部反馈' : '我的反馈' }}</span>
          <span class="count-text">共 {{ total }} 条</span>
        </div>
      </template>

      <el-empty
        v-if="!loading && items.length === 0"
        description="还没有反馈记录，遇到问题或想法随时提交"
      >
        <el-button type="primary" @click="openCreateDialog">提交第一条反馈</el-button>
      </el-empty>

      <el-table v-else v-loading="loading" :data="items" border>
        <el-table-column label="类型" min-width="90">
          <template #default="{ row }">
            <el-tag :type="categoryTagType(row.category)">{{ categoryLabel(row.category) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="content" label="内容" min-width="220" show-overflow-tooltip />
        <el-table-column label="状态" min-width="110">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="处理说明" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <span>{{ row.review_note || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column v-if="adminMode" label="提交者" min-width="150">
          <template #default="{ row }">
            <span>{{ row.submitter_display_name || '-' }} / {{ row.submitter_phone || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="截图" min-width="110">
          <template #default="{ row }">
            <el-button
              v-if="row.screenshots.length > 0"
              link
              type="primary"
              @click="openPreviewDialog(row)"
            >
              查看截图（{{ row.screenshots.length }}）
            </el-button>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="提交时间" min-width="170">
          <template #default="{ row }">
            <span class="datetime-cell">{{ formatDateTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="170" fixed="right">
          <template #default="{ row }">
            <div class="row-actions">
              <template v-if="canEditRow(row)">
                <el-button link type="primary" @click="openEditDialog(row)">编辑</el-button>
                <el-button link type="danger" @click="withdrawFeedback(row)">撤回</el-button>
              </template>
              <span v-else-if="!adminMode && row.status !== 'pending'" class="locked-note">已锁定</span>
              <el-button v-if="adminMode" link type="warning" @click="openReviewDialog(row)">
                处理
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="createDialogVisible" title="提交反馈" width="520px" destroy-on-close>
      <el-form ref="createFormRef" :model="createForm" :rules="contentRules" label-position="top">
        <el-form-item label="类型">
          <el-radio-group v-model="createForm.category">
            <el-radio-button value="bug">问题</el-radio-button>
            <el-radio-button value="feature">需求</el-radio-button>
            <el-radio-button value="suggestion">建议</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="描述" prop="content">
          <el-input
            v-model="createForm.content"
            type="textarea"
            :rows="5"
            :maxlength="500"
            show-word-limit
            placeholder="用一句话描述你遇到的问题或想要的功能…"
          />
        </el-form-item>
        <el-form-item label="截图（可选，最多 5 张）">
          <el-upload
            v-model:file-list="createFileList"
            action="#"
            :auto-upload="false"
            multiple
            :limit="FEEDBACK_MAX_SCREENSHOTS"
            accept=".jpg,.jpeg,.png"
            :on-exceed="handleExceed"
          >
            <el-button>添加截图</el-button>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-actions">
          <el-button @click="createDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="submittingCreate" @click="submitCreate">提交</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog
      v-model="editDialogVisible"
      title="编辑反馈"
      width="520px"
      destroy-on-close
      @closed="revokeEditShotUrls"
    >
      <el-form ref="editFormRef" :model="editForm" :rules="contentRules" label-position="top">
        <el-form-item label="类型">
          <el-radio-group v-model="editForm.category">
            <el-radio-button value="bug">问题</el-radio-button>
            <el-radio-button value="feature">需求</el-radio-button>
            <el-radio-button value="suggestion">建议</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="描述" prop="content">
          <el-input
            v-model="editForm.content"
            type="textarea"
            :rows="5"
            :maxlength="500"
            show-word-limit
            placeholder="用一句话描述你遇到的问题或想要的功能…"
          />
        </el-form-item>
        <el-form-item v-if="editExistingShots.length > 0" label="已有截图">
          <div class="existing-shots">
            <div v-for="shot in editExistingShots" :key="shot.id" class="existing-shot">
              <img :src="shot.objectUrl" alt="已上传截图预览" class="existing-shot-thumb" />
              <el-checkbox
                :model-value="editRemoveIds.includes(shot.id)"
                @change="(checked) => toggleRemoveShot(shot.id, checked)"
              >
                移除
              </el-checkbox>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="追加截图（可选）">
          <el-upload
            v-model:file-list="editFileList"
            action="#"
            :auto-upload="false"
            multiple
            :limit="editUploadLimit"
            accept=".jpg,.jpeg,.png"
            :on-exceed="handleExceed"
          >
            <el-button>添加截图</el-button>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-actions">
          <el-button @click="editDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="submittingUpdate" @click="submitUpdate">保存</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog v-model="reviewDialogVisible" title="处理反馈" width="520px" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="状态">
          <el-radio-group v-model="reviewForm.status">
            <el-radio-button value="pending">待处理</el-radio-button>
            <el-radio-button value="adopted">已采纳</el-radio-button>
            <el-radio-button value="rejected">已拒绝</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="处理说明（提交者可见）">
          <el-input
            v-model="reviewForm.review_note"
            type="textarea"
            :rows="4"
            :maxlength="500"
            show-word-limit
            placeholder="例如：下个迭代排期 / 与某需求重复，已合并跟踪…"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-actions">
          <el-button @click="reviewDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="submittingReview" @click="submitReview">保存</el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog
      v-model="previewDialogVisible"
      title="截图预览"
      width="640px"
      destroy-on-close
      @closed="revokePreviewUrls"
    >
      <div v-loading="previewLoading" class="preview-grid">
        <img
          v-for="image in previewImages"
          :key="image.id"
          :src="image.objectUrl"
          alt="反馈截图"
          class="preview-image"
        />
      </div>
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
import { authState, isAdminUser } from '../utils/auth'

// 与后端 constants.MAX_FEEDBACK_SCREENSHOTS 保持一致。
const FEEDBACK_MAX_SCREENSHOTS = 5

const loading = ref(false)
const items = ref([])
const total = ref(0)

const createDialogVisible = ref(false)
const editDialogVisible = ref(false)
const reviewDialogVisible = ref(false)
const previewDialogVisible = ref(false)
const submittingCreate = ref(false)
const submittingUpdate = ref(false)
const submittingReview = ref(false)
const previewLoading = ref(false)

const createFormRef = ref(null)
const editFormRef = ref(null)

const filters = reactive({
  q: '',
  category: '',
  status: ''
})

const createForm = reactive({
  content: '',
  category: 'bug'
})
const createFileList = ref([])

const editTarget = ref(null)
const editForm = reactive({
  content: '',
  category: 'bug'
})
const editFileList = ref([])
const editExistingShots = ref([])
const editRemoveIds = ref([])

const reviewTarget = ref(null)
const reviewForm = reactive({
  status: 'pending',
  review_note: ''
})

const previewImages = ref([])

const categoryOptions = [
  { label: '问题', value: 'bug' },
  { label: '需求', value: 'feature' },
  { label: '建议', value: 'suggestion' }
]

const statusOptions = [
  { label: '待处理', value: 'pending' },
  { label: '已采纳', value: 'adopted' },
  { label: '已拒绝', value: 'rejected' }
]

const contentRules = {
  content: [{ required: true, message: '请输入反馈内容', trigger: 'blur' }]
}

// #98：筛选条件与 ?feedback_category= / ?feedback_status= / ?feedback_q= 同步，
// 挂载时恢复；类型/状态只接受合法枚举值——URL 被手改成未知值时按未筛选处理，
// 避免把脏值原样发给后端或显示成裸枚举。
const route = useRoute()
const router = useRouter()

const applyFiltersFromRoute = () => {
  const queryCategory = readStringQuery(route, 'feedback_category')
  filters.category = categoryOptions.some((item) => item.value === queryCategory) ? queryCategory : ''
  const queryStatus = readStringQuery(route, 'feedback_status')
  filters.status = statusOptions.some((item) => item.value === queryStatus) ? queryStatus : ''
  filters.q = readStringQuery(route, 'feedback_q')
}

applyFiltersFromRoute()

watch(filters, () => {
  replaceQueryValues(router, route, {
    feedback_category: filters.category,
    feedback_status: filters.status,
    feedback_q: filters.q
  })
})

const currentUser = computed(() => authState.currentUser)
const adminMode = computed(() => isAdminUser(currentUser.value))
const currentUserId = computed(() => currentUser.value?.id ?? null)

// 管理员列表行带 user_id，可用于识别自己的行；普通用户的「我的反馈」
// 全部是自己的行（接口按登录用户过滤），因此视为可编辑。
const canEditRow = (row) => {
  if (row.status !== 'pending') {
    return false
  }
  return row.user_id == null || row.user_id === currentUserId.value
}

const getErrorMessage = (error) => {
  const detail = error.response?.data?.detail
  if (detail && typeof detail === 'string') {
    return detail
  }
  return '操作失败，请稍后重试。'
}

const categoryLabel = (category) =>
  categoryOptions.find((item) => item.value === category)?.label || category

const categoryTagType = (category) => {
  if (category === 'bug') {
    return 'danger'
  }
  if (category === 'feature') {
    return 'primary'
  }
  return 'info'
}

const statusLabel = (status) =>
  statusOptions.find((item) => item.value === status)?.label || status

const statusTagType = (status) => {
  if (status === 'adopted') {
    return 'success'
  }
  if (status === 'rejected') {
    return 'danger'
  }
  return 'warning'
}

const buildQueryParams = () => {
  const params = { skip: 0, limit: 100 }
  if (filters.category) {
    params.category = filters.category
  }
  if (filters.status) {
    params.status = filters.status
  }
  if (adminMode.value && filters.q) {
    params.q = filters.q.trim()
  }
  return params
}

const loadList = async () => {
  loading.value = true
  try {
    // 管理员看全部反馈（含提交者归属），普通用户只看自己提交的。
    const endpoint = adminMode.value ? '/admin/feedback' : '/feedback'
    const response = await axios.get(`${API_V1_BASE_URL}${endpoint}`, {
      params: buildQueryParams()
    })
    items.value = response.data?.items || []
    total.value = response.data?.total || 0
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

const resetFilters = () => {
  filters.q = ''
  filters.category = ''
  filters.status = ''
  loadList()
}

const handleExceed = () => {
  ElMessage.warning(`最多上传 ${FEEDBACK_MAX_SCREENSHOTS} 张截图。`)
}

const openCreateDialog = () => {
  createForm.content = ''
  createForm.category = 'bug'
  createFileList.value = []
  createDialogVisible.value = true
}

const appendScreenshots = (formData, fileList, fieldName) => {
  for (const item of fileList || []) {
    if (item.raw) {
      formData.append(fieldName, item.raw)
    }
  }
}

const submitCreate = async () => {
  if (!createFormRef.value) {
    return
  }

  const valid = await createFormRef.value.validate().then(() => true).catch(() => false)
  if (!valid) {
    return
  }

  submittingCreate.value = true
  try {
    const formData = new FormData()
    formData.append('content', createForm.content.trim())
    formData.append('category', createForm.category)
    appendScreenshots(formData, createFileList.value, 'screenshots')
    await axios.post(`${API_V1_BASE_URL}/feedback`, formData)
    ElMessage.success('反馈已提交，感谢你的输入。')
    createDialogVisible.value = false
    loadList()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    submittingCreate.value = false
  }
}

const fetchShotObjectUrl = async (shot) => {
  const response = await axios.get(shot.url, { responseType: 'blob' })
  return URL.createObjectURL(response.data)
}

const openEditDialog = async (row) => {
  editTarget.value = row
  editForm.content = row.content
  editForm.category = row.category
  editFileList.value = []
  editRemoveIds.value = []
  editExistingShots.value = []
  editDialogVisible.value = true

  // 缩略图走认证通道拉取 blob；失败时该张不展示，不阻塞编辑。
  for (const shot of row.screenshots || []) {
    try {
      editExistingShots.value.push({ id: shot.id, objectUrl: await fetchShotObjectUrl(shot) })
    } catch {
      ElMessage.warning('部分截图加载失败，仍可继续编辑。')
    }
  }
}

const editUploadLimit = computed(() =>
  Math.max(0, FEEDBACK_MAX_SCREENSHOTS - (editExistingShots.value.length - editRemoveIds.value.length))
)

const toggleRemoveShot = (shotId, checked) => {
  if (checked) {
    if (!editRemoveIds.value.includes(shotId)) {
      editRemoveIds.value.push(shotId)
    }
    return
  }
  editRemoveIds.value = editRemoveIds.value.filter((id) => id !== shotId)
}

const revokeObjectUrls = (images) => {
  for (const image of images) {
    URL.revokeObjectURL(image.objectUrl)
  }
}

const submitUpdate = async () => {
  if (!editFormRef.value || !editTarget.value) {
    return
  }

  const valid = await editFormRef.value.validate().then(() => true).catch(() => false)
  if (!valid) {
    return
  }

  submittingUpdate.value = true
  try {
    const formData = new FormData()
    formData.append('content', editForm.content.trim())
    formData.append('category', editForm.category)
    if (editRemoveIds.value.length > 0) {
      formData.append('remove_screenshot_ids', editRemoveIds.value.join(','))
    }
    appendScreenshots(formData, editFileList.value, 'new_screenshots')
    await axios.patch(`${API_V1_BASE_URL}/feedback/${editTarget.value.id}`, formData)
    ElMessage.success('反馈已更新。')
    editDialogVisible.value = false
    loadList()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    submittingUpdate.value = false
  }
}

const withdrawFeedback = async (row) => {
  try {
    await ElMessageBox.confirm(
      '撤回后这条反馈及其截图将被删除，无法恢复。确认撤回吗？',
      '撤回反馈',
      { type: 'warning' }
    )
  } catch {
    return
  }

  try {
    await axios.delete(`${API_V1_BASE_URL}/feedback/${row.id}`)
    ElMessage.success('反馈已撤回。')
    loadList()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

const openReviewDialog = (row) => {
  reviewTarget.value = row
  reviewForm.status = row.status
  reviewForm.review_note = row.review_note || ''
  reviewDialogVisible.value = true
}

const submitReview = async () => {
  if (!reviewTarget.value) {
    return
  }

  submittingReview.value = true
  try {
    await axios.patch(
      `${API_V1_BASE_URL}/admin/feedback/${reviewTarget.value.id}/status`,
      {
        status: reviewForm.status,
        review_note: reviewForm.review_note.trim() || null
      }
    )
    ElMessage.success('处理结果已保存。')
    reviewDialogVisible.value = false
    loadList()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    submittingReview.value = false
  }
}

const openPreviewDialog = async (row) => {
  previewDialogVisible.value = true
  previewLoading.value = true
  try {
    const images = []
    for (const shot of row.screenshots || []) {
      images.push({ id: shot.id, objectUrl: await fetchShotObjectUrl(shot) })
    }
    previewImages.value = images
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
    previewDialogVisible.value = false
  } finally {
    previewLoading.value = false
  }
}

const revokePreviewUrls = () => {
  revokeObjectUrls(previewImages.value)
  previewImages.value = []
}

const revokeEditShotUrls = () => {
  revokeObjectUrls(editExistingShots.value)
  editExistingShots.value = []
  editRemoveIds.value = []
}

onMounted(() => {
  loadList()
})
</script>

<style scoped lang="scss">
.feedback-inbox-panel {
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

.locked-note {
  color: #8a9aa1;
  font-size: 12px;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.existing-shots {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.existing-shot {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.existing-shot-thumb {
  width: 96px;
  height: 96px;
  object-fit: cover;
  border-radius: 8px;
  border: 1px solid #d9e2e6;
}

.preview-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  min-height: 120px;
}

.preview-image {
  max-width: 100%;
  height: auto;
  border-radius: 10px;
  border: 1px solid #d9e2e6;
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
