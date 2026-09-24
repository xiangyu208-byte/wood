<template>
  <div class="page">
    <header class="page-heading">
      <div>
        <p class="eyebrow">批量检测</p>
        <h1>上传木材图片</h1>
        <p>一次选择最多 20 张图片。任务进入后台后可查看逐张状态，也可以安全取消或重试失败项目。</p>
      </div>
      <StatusBadge v-if="task" :status="task.status" />
    </header>

    <section class="surface" aria-labelledby="upload-title">
      <div class="section-heading">
        <h2 id="upload-title">选择待识别图片</h2>
        <span class="muted">{{ selectedFiles.length }}/20 张</span>
      </div>

      <el-upload
        v-model:file-list="uploadFiles"
        drag
        multiple
        :auto-upload="false"
        :limit="20"
        accept=".jpg,.jpeg,.png"
        :disabled="isActive"
        aria-label="选择木材图片"
      >
        <div class="upload-callout">
          <strong>拖放图片到这里，或点击选择</strong>
          <span>支持 JPG、JPEG、PNG；系统会校验真实图片内容和尺寸</span>
        </div>
      </el-upload>

      <DetectionSettings v-model="settings" />

      <div class="upload-actions actions">
        <el-button type="primary" :loading="phase === 'submitting'" :disabled="!selectedFiles.length || isActive" @click="submitBatch">
          开始批量识别
        </el-button>
        <el-button v-if="canCancel" type="danger" plain :loading="cancelling" @click="handleCancel">取消任务</el-button>
        <el-button v-if="task" plain :disabled="isActive" @click="resetTask">新建任务</el-button>
      </div>
    </section>

    <section v-if="task" class="surface" aria-labelledby="progress-title">
      <div class="section-heading">
        <div>
          <p class="eyebrow">{{ task.batchNo }}</p>
          <h2 id="progress-title">批量任务进度</h2>
        </div>
        <strong>{{ task.processedCount }}/{{ task.totalCount }}</strong>
      </div>

      <el-progress :percentage="progressPercentage" :status="progressStatus" :stroke-width="12" />
      <div class="task-counts" aria-label="任务统计">
        <span>成功 <strong>{{ task.successCount }}</strong></span>
        <span>失败 <strong>{{ task.failCount }}</strong></span>
        <span>取消 <strong>{{ task.cancelledCount || 0 }}</strong></span>
      </div>

      <p v-if="pollError" class="inline-error" role="alert">{{ pollError.message }}</p>
      <div v-if="pollError" class="actions">
        <el-button type="primary" @click="resumePolling">重新连接</el-button>
      </div>

      <ol class="task-list" aria-label="逐张处理状态">
        <li v-for="(item, index) in task.items || []" :key="item.recordId">
          <div class="task-index">{{ index + 1 }}</div>
          <div class="task-info">
            <strong>{{ item.imageName }}</strong>
            <span v-if="item.errorMessage">{{ item.errorMessage }}</span>
            <span v-else>记录 #{{ item.recordId }}</span>
          </div>
          <StatusBadge :status="item.status" />
          <el-button
            v-if="['FAIL', 'CANCELLED'].includes(item.status) && selectedFiles[index]"
            size="small"
            plain
            :loading="singleRetrying.has(item.recordId)"
            @click="retrySingle(item, index)"
          >
            单张重新识别
          </el-button>
        </li>
      </ol>

      <div v-if="canRetryBatch" class="actions task-actions">
        <el-button type="primary" :loading="retrying" @click="handleRetryBatch">重试失败与已取消项目</el-button>
      </div>
    </section>

    <section v-if="phase === 'error' && !task" class="surface">
      <StatePanel :tone="errorTone" title="任务没有创建成功" :description="lastError.message">
        <template #action><el-button type="primary" @click="submitBatch">重新提交</el-button></template>
      </StatePanel>
    </section>

    <section v-if="completedResults.length" class="surface" aria-labelledby="results-title">
      <div class="section-heading">
        <div>
          <p class="eyebrow">可核验结果</p>
          <h2 id="results-title">识别详情</h2>
        </div>
        <span class="muted">{{ completedResults.length }} 张成功图片</span>
      </div>
      <ResultDetails v-for="item in completedResults" :key="item.recordId" :result="item" />
    </section>

    <section v-if="!task && phase === 'idle'" class="surface">
      <StatePanel tone="empty" title="等待开始识别" description="选择图片后提交任务，这里会显示总进度、每张图片的状态和失败原因。" />
    </section>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { ElMessage } from 'element-plus'
import DetectionSettings from '../components/DetectionSettings.vue'
import ResultDetails from '../components/ResultDetails.vue'
import StatePanel from '../components/StatePanel.vue'
import StatusBadge from '../components/StatusBadge.vue'
import {
  batchUploadDetectAsync,
  cancelBatch,
  getBatchStatus,
  getDetail,
  retryBatch,
  uploadDetect
} from '../api/detect'
import { isTaskActive, isTaskTerminal } from '../utils/detection'

const uploadFiles = ref([])
const settings = ref({ modelMode: 'STANDARD', confidenceThreshold: 0.25, precision: 'AUTO' })
const task = ref(null)
const completedResults = ref([])
const phase = ref('idle')
const lastError = ref(null)
const pollError = ref(null)
const cancelling = ref(false)
const retrying = ref(false)
const singleRetrying = ref(new Set())
let pollTimer = null

const selectedFiles = computed(() => uploadFiles.value.map(item => item.raw).filter(Boolean))
const hasActiveItems = computed(() => (task.value?.items || []).some(item => isTaskActive(item.status)))
const isActive = computed(() => task.value && (isTaskActive(task.value.status) || hasActiveItems.value))
const canCancel = computed(() => task.value && isTaskActive(task.value.status))
const progressPercentage = computed(() => {
  if (!task.value?.totalCount) return 0
  return Math.round((task.value.processedCount / task.value.totalCount) * 100)
})
const progressStatus = computed(() => task.value?.status === 'SUCCESS' ? 'success' : task.value?.status === 'FAIL' ? 'exception' : '')
const canRetryBatch = computed(() => task.value && !isActive.value && !hasActiveItems.value
  && (task.value.failCount > 0 || task.value.cancelledCount > 0))
const errorTone = computed(() => ['offline', 'service'].includes(lastError.value?.kind) ? 'offline' : 'error')

async function submitBatch() {
  if (!selectedFiles.value.length) {
    ElMessage.warning('请先选择图片')
    return
  }
  stopPolling()
  phase.value = 'submitting'
  lastError.value = null
  pollError.value = null
  completedResults.value = []
  try {
    const payload = await batchUploadDetectAsync(selectedFiles.value, settings.value)
    task.value = payload.data
    phase.value = 'polling'
    schedulePoll(250)
  } catch (error) {
    lastError.value = error
    phase.value = 'error'
  }
}

async function pollTask() {
  if (!task.value?.batchNo) return
  try {
    const payload = await getBatchStatus(task.value.batchNo)
    task.value = payload.data
    pollError.value = null
    if (isTaskTerminal(task.value.status) && !hasActiveItems.value) {
      phase.value = 'complete'
      await hydrateCompletedResults()
      announceCompletion()
      return
    }
    schedulePoll(1100)
  } catch (error) {
    pollError.value = error
    phase.value = 'poll-error'
  }
}

function schedulePoll(delay) {
  stopPolling()
  pollTimer = window.setTimeout(pollTask, delay)
}

function stopPolling() {
  if (pollTimer) window.clearTimeout(pollTimer)
  pollTimer = null
}

function resumePolling() {
  pollError.value = null
  phase.value = 'polling'
  schedulePoll(0)
}

async function handleCancel() {
  cancelling.value = true
  try {
    const payload = await cancelBatch(task.value.batchNo)
    task.value = payload.data
    if (hasActiveItems.value) {
      phase.value = 'polling'
      schedulePoll(600)
    } else {
      phase.value = 'complete'
      stopPolling()
      await hydrateCompletedResults()
    }
    ElMessage.info('任务已取消，正在处理的单张图片可能已完成')
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    cancelling.value = false
  }
}

async function handleRetryBatch() {
  retrying.value = true
  pollError.value = null
  try {
    const payload = await retryBatch(task.value.batchNo)
    task.value = payload.data
    phase.value = 'polling'
    completedResults.value = completedResults.value.filter(item => item.status === 'SUCCESS')
    schedulePoll(300)
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    retrying.value = false
  }
}

async function retrySingle(item, index) {
  const file = selectedFiles.value[index]
  if (!file) return
  singleRetrying.value = new Set(singleRetrying.value).add(item.recordId)
  try {
    const payload = await uploadDetect(file, settings.value)
    completedResults.value = [payload.data, ...completedResults.value.filter(result => result.recordId !== payload.data.recordId)]
    ElMessage.success(`${item.imageName} 已重新识别`)
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    const next = new Set(singleRetrying.value)
    next.delete(item.recordId)
    singleRetrying.value = next
  }
}

async function hydrateCompletedResults() {
  const successful = (task.value?.items || []).filter(item => item.status === 'SUCCESS')
  const results = await Promise.allSettled(successful.map(item => getDetail(item.recordId)))
  completedResults.value = results
    .filter(result => result.status === 'fulfilled')
    .map(result => result.value.data)
}

function announceCompletion() {
  if (task.value.status === 'SUCCESS') ElMessage.success('批量识别完成')
  else if (task.value.status === 'CANCELLED') ElMessage.info('批量任务已取消')
  else ElMessage.warning('任务已结束，请查看失败原因并按需重试')
}

function resetTask() {
  stopPolling()
  task.value = null
  completedResults.value = []
  uploadFiles.value = []
  phase.value = 'idle'
  lastError.value = null
  pollError.value = null
}

onBeforeUnmount(stopPolling)
</script>

<style scoped>
.upload-callout { display: grid; gap: 6px; padding: 18px; }
.upload-callout strong { font-size: 16px; }
.upload-callout span { color: var(--color-text-muted); font-size: 13px; }
.upload-actions { margin-top: 18px; }
.task-counts { display: flex; flex-wrap: wrap; gap: 18px; margin: 14px 0 0; color: var(--color-text-muted); font-size: 13px; }
.task-counts strong { color: var(--color-text); }
.task-list { display: grid; gap: 0; margin: 20px 0 0; padding: 0; list-style: none; border: 1px solid var(--color-border); border-radius: var(--radius-md); overflow: hidden; }
.task-list li { display: grid; grid-template-columns: 32px minmax(0, 1fr) auto auto; align-items: center; gap: 12px; min-height: 64px; padding: 10px 14px; background: var(--color-surface); }
.task-list li + li { border-top: 1px solid var(--color-border); }
.task-index { display: grid; width: 28px; height: 28px; place-items: center; border-radius: 50%; background: var(--color-surface-muted); color: var(--color-text-muted); font-size: 12px; font-weight: 700; }
.task-info { min-width: 0; }
.task-info strong, .task-info span { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.task-info span { margin-top: 3px; color: var(--color-text-muted); font-size: 12px; }
.task-actions { margin-top: 16px; }
:deep(.el-upload-dragger) { min-height: 132px; display: grid; place-items: center; border-color: var(--color-border); border-radius: var(--radius-md); background: var(--color-surface-muted); }
:deep(.el-upload-dragger:hover) { border-color: var(--color-primary); }

@media (max-width: 700px) {
  .task-list li { grid-template-columns: 32px minmax(0, 1fr) auto; }
  .task-list .el-button { grid-column: 2 / -1; justify-self: start; }
}

@media (max-width: 430px) {
  .task-list li { grid-template-columns: 28px minmax(0, 1fr); }
  .task-list .status-badge, .task-list .el-button { grid-column: 2; justify-self: start; }
}
</style>
