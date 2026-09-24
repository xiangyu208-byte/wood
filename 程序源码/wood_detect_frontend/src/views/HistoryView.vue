<template>
  <div class="page-container">
    <el-card>
      <template #header>
        <span>历史记录</span>
      </template>

      <!-- 筛选区域 -->
      <el-form :inline="true" :model="queryForm" class="filter-form">
        <el-form-item label="批次号">
          <el-input
              v-model="queryForm.batchNo"
              placeholder="请输入批次号"
              clearable
          />
        </el-form-item>

        <el-form-item label="来源类型">
          <el-select v-model="queryForm.sourceType" placeholder="请选择来源" clearable style="width: 140px;">
            <el-option label="上传" value="UPLOAD" />
            <el-option label="摄像头" value="CAMERA" />
          </el-select>
        </el-form-item>

        <el-form-item label="图片名称">
          <el-input
              v-model="queryForm.imageName"
              placeholder="请输入图片名称"
              clearable
          />
        </el-form-item>

        <el-form-item label="状态">
          <el-select v-model="queryForm.status" placeholder="请选择状态" clearable style="width: 140px;">
            <el-option label="成功" value="SUCCESS" />
            <el-option label="失败" value="FAIL" />
            <el-option label="处理中" value="PROCESSING" />
          </el-select>
        </el-form-item>

        <el-form-item label="是否有缺陷">
          <el-select v-model="queryForm.hasDefect" placeholder="请选择" clearable style="width: 140px;">
            <el-option label="有缺陷" value="YES" />
            <el-option label="无缺陷" value="NO" />
          </el-select>
        </el-form-item>

        <el-form-item label="开始时间">
          <el-date-picker
              v-model="queryForm.startTime"
              type="datetime"
              placeholder="选择开始时间"
              value-format="YYYY-MM-DD HH:mm:ss"
              clearable
          />
        </el-form-item>

        <el-form-item label="结束时间">
          <el-date-picker
              v-model="queryForm.endTime"
              type="datetime"
              placeholder="选择结束时间"
              value-format="YYYY-MM-DD HH:mm:ss"
              clearable
          />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
          <el-button type="success" @click="handleExportCsv">导出 CSV</el-button>
          <el-button type="warning" @click="handleExportExcel">导出 Excel</el-button>
          <el-button type="info" @click="handleDownloadImagesZip">下载筛选结果图片</el-button>
          <el-button
              type="danger"
              :disabled="selectedIds.length === 0"
              @click="handleBatchDelete"
          >
            删除选中项
          </el-button>
          <el-button
              type="danger"
              plain
              @click="handleDeleteByCondition"
          >
            一键删除筛选结果
          </el-button>
        </el-form-item>
      </el-form>

      <!-- 表格区域 -->
      <el-table
          :data="historyList"
          border
          style="width: 100%; margin-top: 16px;"
          @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="55" />
        <el-table-column label="序号" width="80">
          <template #default="scope">
            {{ (page - 1) * size + scope.$index + 1 }}
          </template>
        </el-table-column>
        <el-table-column prop="recordId" label="记录ID" width="100" />
        <el-table-column prop="batchNo" label="批次号" width="220" />
        <el-table-column prop="sourceType" label="来源类型" width="120" />
        <el-table-column prop="imageName" label="图片名称" />
        <el-table-column prop="totalCount" label="缺陷数" width="100" />
        <el-table-column prop="status" label="状态" width="120" />
        <el-table-column prop="createTime" label="创建时间" width="200" />
        <el-table-column label="操作" width="220">
          <template #default="scope">
            <el-button type="primary" size="small" @click="goDetail(scope.row.recordId)">
              查看详情
            </el-button>

            <el-button
                type="danger"
                size="small"
                @click="handleDelete(scope.row.recordId)"
                style="margin-left: 8px;"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页区域 -->
      <div style="margin-top: 20px; text-align: right;">
        <el-pagination
            background
            layout="total, prev, pager, next"
            :current-page="page"
            :page-size="size"
            :total="total"
            @current-change="handlePageChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  getHistory,
  deleteRecord,
  batchDeleteRecords,
  deleteRecordsByCondition
} from '../api/detect'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()
const historyList = ref([])
const page = ref(1)
const size = ref(10)
const total = ref(0)
const selectedIds = ref([])

const queryForm = ref({
  imageName: '',
  status: '',
  batchNo: '',
  sourceType: '',
  hasDefect: '',
  startTime: '',
  endTime: ''
})

async function loadHistory() {
  try {
    const res = await getHistory({
      page: page.value,
      size: size.value,
      imageName: queryForm.value.imageName,
      status: queryForm.value.status,
      batchNo: queryForm.value.batchNo,
      sourceType: queryForm.value.sourceType,
      hasDefect: queryForm.value.hasDefect,
      startTime: queryForm.value.startTime,
      endTime: queryForm.value.endTime
    })

    const pageData = res.data.data
    historyList.value = pageData?.records || []
    total.value = pageData?.total || 0
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || '加载历史记录失败')
  }
}

function handlePageChange(newPage) {
  page.value = newPage
  loadHistory()
}

function handleSearch() {
  page.value = 1
  loadHistory()
}

function handleReset() {
  queryForm.value = {
    imageName: '',
    status: '',
    batchNo: '',
    sourceType: '',
    hasDefect: '',
    startTime: '',
    endTime: ''
  }
  page.value = 1
  loadHistory()
}
function handleSelectionChange(selection) {
  selectedIds.value = selection.map(item => item.recordId)
}

function goDetail(id) {
  router.push(`/history/${id}`)
}

async function handleDelete(id) {
  try {
    await ElMessageBox.confirm(
        '删除后将同时移除主记录、缺陷明细、原图和结果图，是否继续？',
        '删除确认',
        {
          confirmButtonText: '确定删除',
          cancelButtonText: '取消',
          type: 'warning'
        }
    )

    await deleteRecord(id)
    ElMessage.success('删除成功')
    loadHistory()
  } catch (error) {
    if (error === 'cancel') {
      return
    }
    ElMessage.error(error?.response?.data?.message || '删除失败')
  }
}

async function handleBatchDelete() {
  if (selectedIds.value.length === 0) {
    ElMessage.warning('请先选择要删除的记录')
    return
  }

  try {
    await ElMessageBox.confirm(
        `确定要删除选中的 ${selectedIds.value.length} 条记录吗？删除后将同时移除主记录、缺陷明细、原图和结果图。`,
        '批量删除确认',
        {
          confirmButtonText: '确定删除',
          cancelButtonText: '取消',
          type: 'warning'
        }
    )

    await batchDeleteRecords(selectedIds.value)
    ElMessage.success('批量删除成功')
    selectedIds.value = []
    loadHistory()
  } catch (error) {
    if (error === 'cancel') {
      return
    }
    ElMessage.error(error?.response?.data?.message || '批量删除失败')
  }
}

async function handleDeleteByCondition() {
  try {
    await ElMessageBox.confirm(
        '将删除当前筛选条件下的全部记录（不只当前页），并同时删除明细、原图和结果图，是否继续？',
        '一键删除确认',
        {
          confirmButtonText: '确定删除',
          cancelButtonText: '取消',
          type: 'warning'
        }
    )

    await deleteRecordsByCondition({
      imageName: queryForm.value.imageName,
      status: queryForm.value.status,
      batchNo: queryForm.value.batchNo,
      sourceType: queryForm.value.sourceType,
      hasDefect: queryForm.value.hasDefect,
      startTime: queryForm.value.startTime,
      endTime: queryForm.value.endTime
    })

    ElMessage.success('已删除当前筛选条件下的全部记录')
    selectedIds.value = []
    page.value = 1
    loadHistory()
  } catch (error) {
    if (error === 'cancel') {
      return
    }
    ElMessage.error(error?.response?.data?.message || '一键删除失败')
  }
}

function buildExportParams() {
  const params = new URLSearchParams()

  if (queryForm.value.imageName) {
    params.append('imageName', queryForm.value.imageName)
  }
  if (queryForm.value.status) {
    params.append('status', queryForm.value.status)
  }
  if (queryForm.value.batchNo) {
    params.append('batchNo', queryForm.value.batchNo)
  }
  if (queryForm.value.sourceType) {
    params.append('sourceType', queryForm.value.sourceType)
  }
  if (queryForm.value.hasDefect) {
    params.append('hasDefect', queryForm.value.hasDefect)
  }
  if (queryForm.value.startTime) {
    params.append('startTime', queryForm.value.startTime)
  }
  if (queryForm.value.endTime) {
    params.append('endTime', queryForm.value.endTime)
  }

  return params.toString()
}

function handleExportCsv() {
  const query = buildExportParams()
  const url = `/api/detect/export/csv${query ? '?' + query : ''}`
  window.open(url, '_blank')
}

function handleExportExcel() {
  const query = buildExportParams()
  const url = `/api/detect/export/excel${query ? '?' + query : ''}`
  window.open(url, '_blank')
}

function handleDownloadImagesZip() {
  const query = buildExportParams()
  const url = `/api/detect/export/images${query ? '?' + query : ''}`

  window.open(url, '_blank')
}

onMounted(() => {
  loadHistory()
})
</script>

<style scoped>
.page-container {
  padding: 20px;
}

:deep(.el-card) {
  background: rgba(255, 255, 255, 0.88);
  border: none;
  border-radius: 12px;
}

.filter-form {
  margin-bottom: 10px;
}
</style>
