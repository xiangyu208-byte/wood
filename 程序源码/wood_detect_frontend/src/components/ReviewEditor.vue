<template>
  <section class="review-editor" :aria-labelledby="`review-${result.recordId}`">
    <div class="section-heading review-heading">
      <div>
        <p class="eyebrow">主动学习闭环</p>
        <h3 :id="`review-${result.recordId}`">人工复核</h3>
        <p>保留原始模型结果，在下方确认、修正或补充最终标注框。</p>
      </div>
      <span class="review-status" :class="`tone-${reviewStatusMeta(result.reviewStatus).tone}`">
        {{ reviewStatusMeta(result.reviewStatus).label }}
      </span>
    </div>

    <div class="review-context">
      <div><span>模型版本</span><strong>{{ result.modelVersion || 'unknown' }}</strong></div>
      <div><span>最低置信度</span><strong>{{ formatConfidence(result.minConfidence) }}</strong></div>
      <div><span>自动入队</span><strong>{{ result.reviewNeeded ? reviewReasonLabel(result.reviewReason) : '否' }}</strong></div>
      <div><span>复核时间</span><strong>{{ result.reviewedAt || '—' }}</strong></div>
    </div>

    <p v-if="isReviewPending(result)" class="review-alert" role="status">
      此记录已自动进入待复核队列：{{ reviewReasonLabel(result.reviewReason) }}。
    </p>

    <div class="annotation-heading">
      <div><h4>最终标注框</h4><p>修改类别或坐标、删除误检框，也可以补充漏检目标。</p></div>
      <el-button @click="addAnnotation">补充漏检框</el-button>
    </div>

    <div v-if="annotations.length" class="annotation-list">
      <div v-for="(item, index) in annotations" :key="item.localId" class="annotation-row">
        <span class="annotation-index">{{ index + 1 }}</span>
        <el-select v-model="item.className" aria-label="缺陷类别">
          <el-option v-for="option in classOptions" :key="option.value" :label="option.label" :value="option.value" />
        </el-select>
        <div class="coordinate-grid">
          <label>X1<el-input-number v-model="item.x1" :min="0" :max="result.imageWidth || 10000" controls-position="right" /></label>
          <label>Y1<el-input-number v-model="item.y1" :min="0" :max="result.imageHeight || 10000" controls-position="right" /></label>
          <label>X2<el-input-number v-model="item.x2" :min="0" :max="result.imageWidth || 10000" controls-position="right" /></label>
          <label>Y2<el-input-number v-model="item.y2" :min="0" :max="result.imageHeight || 10000" controls-position="right" /></label>
        </div>
        <span class="annotation-source">{{ annotationSourceLabel(item.sourceType) }}</span>
        <el-button type="danger" text :aria-label="`删除第 ${index + 1} 个标注框`" @click="removeAnnotation(index)">删除</el-button>
      </div>
    </div>
    <p v-else class="annotation-empty">当前最终标注为空；可补充漏检框，或将整条检测标记为错误。</p>

    <label class="comment-field">
      <span>复核备注（可选）</span>
      <el-input v-model="comment" type="textarea" :rows="3" maxlength="1000" show-word-limit placeholder="记录误检、漏检或修正依据" />
    </label>

    <div class="review-actions">
      <el-button type="success" :loading="saving === 'CORRECT'" :disabled="Boolean(saving)" @click="saveReview('CORRECT')">确认模型结果正确</el-button>
      <el-button type="primary" :loading="saving === 'CORRECTED'" :disabled="Boolean(saving)" @click="saveReview('CORRECTED')">保存人工修正</el-button>
      <el-button type="danger" plain :loading="saving === 'INCORRECT'" :disabled="Boolean(saving)" @click="saveReview('INCORRECT')">标记结果错误</el-button>
    </div>
    <p class="review-note">“结果正确”会采用原始六类模型框；“保存人工修正”会采用当前表格；“结果错误”会保存为空标签负样本。</p>
  </section>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { submitReview } from '../api/detect'
import {
  annotationSourceLabel,
  classNameZh,
  formatConfidence,
  isReviewPending,
  reviewReasonLabel,
  reviewStatusMeta
} from '../utils/detection'

const props = defineProps({ result: { type: Object, required: true } })
const emit = defineEmits(['saved'])
const classNames = ['dry_knot', 'sound_knot', 'edge_knot', 'small_knot', 'split', 'wave']
const classOptions = classNames.map(value => ({ value, label: classNameZh(value) }))
const annotations = ref([])
const comment = ref('')
const saving = ref('')
let localSequence = 0

function editableAnnotations(result) {
  const reviewed = result.reviewStatus && result.reviewStatus !== 'UNREVIEWED'
    ? result.reviewAnnotations || []
    : (result.details || []).filter(item => classNames.includes(item.className))
  return reviewed.map(item => ({
    localId: ++localSequence,
    originalDetailId: item.originalDetailId ?? item.detailId ?? null,
    className: item.className,
    x1: item.x1,
    y1: item.y1,
    x2: item.x2,
    y2: item.y2,
    sourceType: item.sourceType || 'MODEL_CONFIRMED'
  }))
}

watch(() => props.result, result => {
  annotations.value = editableAnnotations(result)
  comment.value = result.reviewComment || ''
}, { immediate: true, deep: true })

function addAnnotation() {
  annotations.value.push({
    localId: ++localSequence,
    originalDetailId: null,
    className: 'dry_knot',
    x1: 0,
    y1: 0,
    x2: Math.min(100, props.result.imageWidth || 100),
    y2: Math.min(100, props.result.imageHeight || 100),
    sourceType: 'HUMAN_ADDED'
  })
}

function removeAnnotation(index) {
  annotations.value.splice(index, 1)
}

async function saveReview(reviewStatus) {
  saving.value = reviewStatus
  try {
    const payload = await submitReview(props.result.recordId, {
      reviewStatus,
      comment: comment.value,
      annotations: reviewStatus === 'CORRECTED'
        ? annotations.value.map(({ originalDetailId, className, x1, y1, x2, y2 }) => ({ originalDetailId, className, x1, y1, x2, y2 }))
        : []
    })
    emit('saved', payload.data)
    ElMessage.success('人工复核已保存')
  } catch (error) {
    ElMessage.error(error.message || '保存人工复核失败')
  } finally {
    saving.value = ''
  }
}
</script>

<style scoped>
.review-editor { margin-top: 24px; padding-top: 24px; border-top: 1px solid var(--color-border); }
.review-heading { align-items: flex-start; }
.review-heading h3 { margin: 2px 0 4px; }
.review-heading p:last-child { margin: 0; color: var(--color-text-muted); font-size: 13px; }
.review-status { padding: 7px 11px; border-radius: 999px; font-size: 12px; font-weight: 750; white-space: nowrap; }
.tone-neutral { background: var(--color-surface-muted); color: var(--color-text-muted); }
.tone-success { background: #dff5e9; color: #176b45; }
.tone-warning { background: #fff0cf; color: #8a5a12; }
.tone-danger { background: #fde3e3; color: #9a3030; }
.review-context { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin: 18px 0; }
.review-context div { display: grid; gap: 4px; padding: 12px; border-radius: 10px; background: var(--color-surface-muted); }
.review-context span { color: var(--color-text-muted); font-size: 12px; }
.review-context strong { overflow-wrap: anywhere; font-size: 13px; }
.review-alert { padding: 12px 14px; border-left: 3px solid #b97a14; background: #fff8e8; color: #79500f; }
.annotation-heading { display: flex; align-items: end; justify-content: space-between; gap: 18px; margin: 22px 0 10px; }
.annotation-heading h4, .annotation-heading p { margin: 0; }
.annotation-heading p { margin-top: 4px; color: var(--color-text-muted); font-size: 12px; }
.annotation-list { display: grid; gap: 8px; }
.annotation-row { display: grid; grid-template-columns: 28px minmax(130px, .75fr) minmax(360px, 2fr) minmax(100px, .65fr) auto; align-items: center; gap: 10px; padding: 10px; border: 1px solid var(--color-border); border-radius: 10px; }
.annotation-index { display: grid; width: 26px; height: 26px; place-items: center; border-radius: 50%; background: var(--color-surface-muted); font-size: 12px; font-weight: 700; }
.coordinate-grid { display: grid; grid-template-columns: repeat(4, minmax(75px, 1fr)); gap: 6px; }
.coordinate-grid label { display: grid; gap: 3px; color: var(--color-text-muted); font-size: 11px; }
.coordinate-grid :deep(.el-input-number) { width: 100%; }
.annotation-source { color: var(--color-text-muted); font-size: 12px; }
.annotation-empty { padding: 18px; border: 1px dashed var(--color-border); border-radius: 10px; color: var(--color-text-muted); text-align: center; }
.comment-field { display: grid; gap: 7px; margin-top: 18px; font-size: 13px; font-weight: 650; }
.review-actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 16px; }
.review-note { margin: 10px 0 0; color: var(--color-text-muted); font-size: 12px; }
@media (max-width: 980px) {
  .review-context { grid-template-columns: repeat(2, 1fr); }
  .annotation-row { grid-template-columns: 28px 1fr auto; }
  .coordinate-grid { grid-column: 2 / -1; }
  .annotation-source { grid-column: 2; }
}
@media (max-width: 600px) {
  .review-context { grid-template-columns: 1fr; }
  .annotation-heading { align-items: stretch; flex-direction: column; }
  .coordinate-grid { grid-template-columns: repeat(2, 1fr); }
  .review-actions { align-items: stretch; flex-direction: column; }
}
</style>
