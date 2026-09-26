<template>
  <div class="page">
    <header class="page-heading">
      <div>
        <p class="eyebrow">检测档案</p>
        <h1>记录详情</h1>
        <p>核验原图、检测结果、模型参数与缺陷置信度。</p>
      </div>
      <div class="actions">
        <StatusBadge v-if="detailData" :status="detailData.status" />
        <el-button @click="router.push('/history')">返回历史记录</el-button>
      </div>
    </header>

    <section class="surface">
      <StatePanel v-if="loading" tone="loading" title="正在加载记录" description="正在读取检测图片和缺陷明细。" />
      <StatePanel v-else-if="loadError" :tone="errorTone" title="记录加载失败" :description="loadError.message">
        <template #action><el-button type="primary" @click="loadDetail">重新加载</el-button></template>
      </StatePanel>
      <template v-else-if="detailData">
        <ResultDetails :result="detailData" />
        <ReviewEditor v-if="detailData.status === 'SUCCESS'" :result="detailData" @saved="handleReviewSaved" />
        <div v-if="canRetry" class="retry-row">
          <div><strong>这条记录未成功完成</strong><p>可重新执行当前批次中的失败和已取消项目。</p></div>
          <el-button type="primary" :loading="retrying" @click="handleRetry">重试所在批次</el-button>
        </div>
      </template>
    </section>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import ResultDetails from '../components/ResultDetails.vue'
import ReviewEditor from '../components/ReviewEditor.vue'
import StatePanel from '../components/StatePanel.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { getDetail, retryBatch } from '../api/detect'

const route = useRoute()
const router = useRouter()
const detailData = ref(null)
const loading = ref(true)
const loadError = ref(null)
const retrying = ref(false)
let refreshTimer = null

const errorTone = computed(() => ['offline', 'service'].includes(loadError.value?.kind) ? 'offline' : 'error')
const canRetry = computed(() => detailData.value?.batchNo && ['FAIL', 'CANCELLED'].includes(detailData.value.status))

function handleReviewSaved(updated) {
  detailData.value = updated
}

async function loadDetail(silent = false) {
  if (!silent) loading.value = true
  loadError.value = null
  try {
    const payload = await getDetail(route.params.id)
    detailData.value = payload.data
    if (silent && ['PENDING', 'PROCESSING'].includes(payload.data.status)) {
      refreshTimer = window.setTimeout(() => loadDetail(true), 1200)
    }
  } catch (error) {
    loadError.value = error
  } finally {
    loading.value = false
  }
}

async function handleRetry() {
  retrying.value = true
  try {
    await retryBatch(detailData.value.batchNo)
    ElMessage.success('失败项目已重新进入队列')
    await loadDetail(true)
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    retrying.value = false
  }
}

onMounted(loadDetail)
onBeforeUnmount(() => { if (refreshTimer) window.clearTimeout(refreshTimer) })
</script>

<style scoped>
.retry-row { display: flex; align-items: center; justify-content: space-between; gap: 20px; margin-top: 24px; padding-top: 20px; border-top: 1px solid var(--color-border); }
.retry-row p { margin: 4px 0 0; color: var(--color-text-muted); font-size: 13px; }
@media (max-width: 600px) { .retry-row { align-items: stretch; flex-direction: column; } }
</style>
