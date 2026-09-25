<template>
  <div class="page">
    <header class="page-heading">
      <div>
        <p class="eyebrow">检测档案</p>
        <h1>历史记录</h1>
        <p>筛选、核验和导出检测记录。删除操作会同时清理原图、结果图和缺陷明细。</p>
      </div>
      <strong class="record-total">{{ total }} 条记录</strong>
    </header>

    <section class="surface" aria-labelledby="filter-title">
      <div class="section-heading">
        <h2 id="filter-title">筛选条件</h2>
        <el-button text @click="handleReset">清空筛选</el-button>
      </div>
      <el-form :model="queryForm" label-position="top" class="filter-grid" @submit.prevent="handleSearch">
        <el-form-item label="批次号"><el-input v-model="queryForm.batchNo" placeholder="输入批次号" clearable /></el-form-item>
        <el-form-item label="图片名称"><el-input v-model="queryForm.imageName" placeholder="输入文件名" clearable /></el-form-item>
        <el-form-item label="来源">
          <el-select v-model="queryForm.sourceType" placeholder="全部来源" clearable>
            <el-option label="上传" value="UPLOAD" /><el-option label="摄像头" value="CAMERA" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="queryForm.status" placeholder="全部状态" clearable>
            <el-option label="等待处理" value="PENDING" /><el-option label="处理中" value="PROCESSING" />
            <el-option label="识别成功" value="SUCCESS" /><el-option label="识别失败" value="FAIL" />
            <el-option label="已取消" value="CANCELLED" />
          </el-select>
        </el-form-item>
        <el-form-item label="缺陷情况">
          <el-select v-model="queryForm.hasDefect" placeholder="全部" clearable>
            <el-option label="有缺陷" value="YES" /><el-option label="无缺陷" value="NO" />
          </el-select>
        </el-form-item>
        <el-form-item label="开始时间"><el-date-picker v-model="queryForm.startTime" type="datetime" placeholder="选择开始时间" value-format="YYYY-MM-DD HH:mm:ss" clearable /></el-form-item>
        <el-form-item label="结束时间"><el-date-picker v-model="queryForm.endTime" type="datetime" placeholder="选择结束时间" value-format="YYYY-MM-DD HH:mm:ss" clearable /></el-form-item>
        <el-form-item class="filter-submit"><el-button native-type="submit" type="primary">查询记录</el-button></el-form-item>
      </el-form>
    </section>

    <section class="surface" aria-labelledby="records-title">
      <div class="section-heading records-heading">
        <div><p class="eyebrow">查询结果</p><h2 id="records-title">记录列表</h2></div>
        <div class="actions export-actions">
          <el-button @click="handleExportCsv">CSV</el-button>
          <el-button @click="handleExportExcel">Excel</el-button>
          <el-button @click="handleDownloadImagesZip">图片 ZIP</el-button>
          <el-button type="danger" plain :disabled="!selectedIds.length" @click="handleBatchDelete">删除选中</el-button>
        </div>
      </div>

      <StatePanel v-if="loading" tone="loading" title="正在加载记录" description="系统正在读取当前筛选条件下的检测记录。" />
      <StatePanel v-else-if="loadError" :tone="errorTone" title="记录加载失败" :description="loadError.message">
        <template #action><el-button type="primary" @click="loadHistory">重新加载</el-button></template>
      </StatePanel>
      <StatePanel v-else-if="!historyList.length" tone="empty" title="没有符合条件的记录" description="可以调整筛选条件，或前往在线识别创建第一条检测记录。">
        <template #action><el-button type="primary" @click="router.push('/detect')">开始识别</el-button></template>
      </StatePanel>

      <template v-else>
        <div class="desktop-records">
          <el-table :data="historyList" row-key="recordId" @selection-change="handleSelectionChange">
            <el-table-column type="selection" width="48" />
            <el-table-column label="图片" min-width="180">
              <template #default="{ row }"><strong class="file-name">{{ row.imageName }}</strong><small>#{{ row.recordId }}</small></template>
            </el-table-column>
            <el-table-column label="状态" width="126"><template #default="{ row }"><StatusBadge :status="row.status" /></template></el-table-column>
            <el-table-column prop="totalCount" label="缺陷数" width="86" />
            <el-table-column prop="sourceType" label="来源" width="90"><template #default="{ row }">{{ row.sourceType === 'CAMERA' ? '摄像头' : '上传' }}</template></el-table-column>
            <el-table-column label="推理策略" min-width="180"><template #default="{ row }"><span>{{ actualModeLabel(row.actualMode) }} · {{ formatDuration(row.inferenceDurationMs) }}</span></template></el-table-column>
            <el-table-column prop="createTime" label="创建时间" min-width="170" />
            <el-table-column label="操作" width="170" fixed="right">
              <template #default="{ row }">
                <el-button size="small" type="primary" plain @click="goDetail(row.recordId)">详情</el-button>
                <el-button size="small" type="danger" text @click="handleDelete(row.recordId)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <ul class="mobile-records" aria-label="历史记录列表">
          <li v-for="row in historyList" :key="row.recordId">
            <div class="mobile-record-head"><strong>{{ row.imageName }}</strong><StatusBadge :status="row.status" /></div>
            <dl><div><dt>缺陷数</dt><dd>{{ row.totalCount }}</dd></div><div><dt>推理策略</dt><dd>{{ actualModeLabel(row.actualMode) }}</dd></div><div><dt>推理耗时</dt><dd>{{ formatDuration(row.inferenceDurationMs) }}</dd></div><div><dt>来源</dt><dd>{{ row.sourceType === 'CAMERA' ? '摄像头' : '上传' }}</dd></div><div><dt>时间</dt><dd>{{ row.createTime }}</dd></div></dl>
            <p v-if="row.errorMessage" class="mobile-error">{{ row.errorMessage }}</p>
            <div class="actions"><el-button type="primary" plain @click="goDetail(row.recordId)">查看详情</el-button><el-button type="danger" text @click="handleDelete(row.recordId)">删除</el-button></div>
          </li>
        </ul>

        <div class="pagination-row">
          <el-pagination background layout="prev, pager, next" :current-page="page" :page-size="size" :total="total" @current-change="handlePageChange" />
        </div>
      </template>

      <div v-if="historyList.length" class="danger-zone">
        <div><strong>删除当前筛选结果</strong><p>将删除所有匹配记录，不限于当前页，此操作不可撤销。</p></div>
        <el-button type="danger" plain @click="handleDeleteByCondition">删除全部筛选结果</el-button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import StatePanel from '../components/StatePanel.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { batchDeleteRecords, deleteRecord, deleteRecordsByCondition, getHistory } from '../api/detect'
import { actualModeLabel, formatDuration } from '../utils/detection'

const router = useRouter()
const historyList = ref([])
const page = ref(1)
const size = ref(10)
const total = ref(0)
const selectedIds = ref([])
const loading = ref(false)
const loadError = ref(null)
const queryForm = ref(emptyQuery())
const errorTone = computed(() => ['offline', 'service'].includes(loadError.value?.kind) ? 'offline' : 'error')

function emptyQuery() {
  return { imageName: '', status: '', batchNo: '', sourceType: '', hasDefect: '', startTime: '', endTime: '' }
}

async function loadHistory() {
  loading.value = true
  loadError.value = null
  try {
    const payload = await getHistory({ page: page.value, size: size.value, ...queryForm.value })
    historyList.value = payload.data?.records || []
    total.value = payload.data?.total || 0
    selectedIds.value = []
  } catch (error) {
    loadError.value = error
  } finally {
    loading.value = false
  }
}

function handlePageChange(value) { page.value = value; loadHistory() }
function handleSearch() { page.value = 1; loadHistory() }
function handleReset() { queryForm.value = emptyQuery(); page.value = 1; loadHistory() }
function handleSelectionChange(rows) { selectedIds.value = rows.map(row => row.recordId) }
function goDetail(id) { router.push(`/history/${id}`) }
async function confirmDelete(message, action) {
  try {
    await ElMessageBox.confirm(message, '删除确认', { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' })
    await action()
    ElMessage.success('删除成功')
    await loadHistory()
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(error.message || '删除失败')
  }
}

function handleDelete(id) {
  return confirmDelete('将删除该记录的缺陷明细、原图和结果图，是否继续？', () => deleteRecord(id))
}

function handleBatchDelete() {
  return confirmDelete(`将删除选中的 ${selectedIds.value.length} 条记录及关联图片，是否继续？`, () => batchDeleteRecords(selectedIds.value))
}

function handleDeleteByCondition() {
  return confirmDelete(`将删除当前筛选条件下的全部 ${total.value} 条记录，不只当前页，是否继续？`, () => deleteRecordsByCondition(queryForm.value))
}

function buildExportParams() {
  const params = new URLSearchParams()
  Object.entries(queryForm.value).forEach(([key, value]) => { if (value) params.append(key, value) })
  return params.toString()
}

function openExport(path) {
  const query = buildExportParams()
  window.open(`/api/detect/export/${path}${query ? `?${query}` : ''}`, '_blank', 'noopener')
}

function handleExportCsv() { openExport('csv') }
function handleExportExcel() { openExport('excel') }
function handleDownloadImagesZip() { openExport('images') }

onMounted(loadHistory)
</script>

<style scoped>
.record-total { padding: 8px 12px; border-radius: 999px; background: var(--color-surface-muted); color: var(--color-text-muted); font-size: 13px; }
.filter-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 2px 16px; }
.filter-grid :deep(.el-form-item) { margin-bottom: 14px; }
.filter-grid :deep(.el-select), .filter-grid :deep(.el-date-editor) { width: 100%; }
.filter-submit { align-self: end; }
.filter-submit :deep(.el-form-item__content), .filter-submit .el-button { width: 100%; }
.records-heading { align-items: flex-start; }
.desktop-records small { display: block; margin-top: 3px; color: var(--color-text-muted); }
.file-name { display: block; overflow-wrap: anywhere; }
.mobile-records { display: none; margin: 0; padding: 0; list-style: none; }
.pagination-row { display: flex; justify-content: flex-end; margin-top: 20px; overflow-x: auto; }
.danger-zone { display: flex; align-items: center; justify-content: space-between; gap: 20px; margin-top: 28px; padding-top: 20px; border-top: 1px solid var(--color-border); }
.danger-zone p { margin: 4px 0 0; color: var(--color-text-muted); font-size: 13px; }

@media (max-width: 980px) { .filter-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 700px) {
  .filter-grid { grid-template-columns: 1fr; }
  .records-heading { flex-direction: column; }
  .export-actions { width: 100%; }
  .desktop-records { display: none; }
  .mobile-records { display: grid; gap: 12px; }
  .mobile-records li { padding: 16px; border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-surface); }
  .mobile-record-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
  .mobile-record-head strong { overflow-wrap: anywhere; }
  .mobile-records dl { display: grid; gap: 8px; margin: 14px 0; }
  .mobile-records dl div { display: grid; grid-template-columns: 72px 1fr; gap: 8px; }
  .mobile-records dt { color: var(--color-text-muted); }
  .mobile-records dd { margin: 0; }
  .mobile-error { color: var(--color-danger); font-size: 13px; }
  .danger-zone { align-items: flex-start; flex-direction: column; }
}
</style>
