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
      <div><h4>原图标注</h4><p>选择类别后在图上拖动画框。选择已有标注可移动框，拖动四角可调整大小。</p></div>
    </div>
    <fieldset class="editor-tools" :disabled="Boolean(saving)">
      <label>缺陷类型
        <select v-model="currentClass" @change="changeClass">
          <option v-for="option in classOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
        </select>
      </label>
      <button type="button" :aria-pressed="tool === 'draw'" @click="startDrawing">画新框</button>
      <button type="button" :aria-pressed="tool === 'select'" @click="tool = 'select'">选择 / 调整</button>
      <button type="button" :disabled="!selected" @click="removeSelected">删除选中框</button>
    </fieldset>
    <div v-if="result.imageUrl" class="image-stage">
      <img :src="fullImageUrl(result.imageUrl)" :alt="result.imageName + ' 标注底图'" draggable="false"
           @load="imageReady = true" @error="imageReady = false" />
      <svg v-if="imageReady && result.imageWidth && result.imageHeight" ref="surface"
           :viewBox="'0 0 ' + result.imageWidth + ' ' + result.imageHeight" preserveAspectRatio="none"
           :class="{drawing: tool === 'draw'}" aria-label="缺陷标注画布"
           @pointerdown="pointerDown" @pointermove="pointerMove" @pointerup="pointerUp" @pointercancel="cancelGesture" @lostpointercapture="cancelGesture">
        <g v-for="(box,i) in annotations" :key="box.localId" :data-box="box.localId" :class="{chosen: selectedId === box.localId}">
          <rect :x="box.x1" :y="box.y1" :width="box.x2-box.x1" :height="box.y2-box.y1" class="outline"/>
          <text :x="box.x1+2" :y="Math.max(box.y1-3,labelSize)" :font-size="labelSize">{{ i+1 }} · {{ classNameZh(box.className) }}</text>
          <template v-if="tool === 'select' && selectedId === box.localId">
            <circle v-for="corner in corners" :key="corner.join('')" :data-corner="corner.join(',')" :cx="box[corner[0]]" :cy="box[corner[1]]" :r="handleSize" />
          </template>
        </g>
        <rect v-if="draft" class="outline draft" :x="draft.x1" :y="draft.y1" :width="draft.x2-draft.x1" :height="draft.y2-draft.y1"/>
      </svg>
    </div>
    <p v-if="!imageReady || !result.imageWidth || !result.imageHeight" class="muted">原图或尺寸尚未就绪。</p>
    <div class="box-list" aria-label="标注列表">
      <button v-for="(box,i) in annotations" :key="box.localId" type="button" :disabled="Boolean(saving)" :aria-pressed="box.localId === selectedId" @click="selectBox(box)">{{ i+1 }} · {{ classNameZh(box.className) }}</button>
      <span v-if="!annotations.length">当前没有标注框</span>
    </div>

    <label class="comment-field">
      <span>复核备注（可选）</span>
      <el-input v-model="comment" type="textarea" :rows="3" maxlength="1000" show-word-limit placeholder="记录误检、漏检或修正依据" />
    </label>

    <div class="review-actions">
      <el-button type="success" :loading="saving === 'CORRECT'" :disabled="Boolean(saving)" @click="saveReview('CORRECT')">确认模型结果正确</el-button>
      <el-button type="primary" :loading="saving === 'CORRECTED'" :disabled="Boolean(saving)" @click="saveReview('CORRECTED')">保存人工修正</el-button>
      <el-button type="danger" plain :loading="saving === 'INCORRECT'" :disabled="Boolean(saving)" @click="saveReview('INCORRECT')">标记结果错误</el-button>
    </div>
    <p class="review-note">“结果正确”会采用原始检测框；“保存人工修正”会采用图上的标注；“结果错误”会保存为空标签负样本。</p>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { submitReview } from '../api/detect'
import {
  fullImageUrl,
  classNameZh,
  formatConfidence,
  isReviewPending,
  reviewReasonLabel,
  reviewStatusMeta
} from '../utils/detection'

const props = defineProps({ result: { type: Object, required: true } })
const emit = defineEmits(['saved'])
const classNames = [
  'dry_knot', 'sound_knot', 'edge_knot', 'small_knot', 'split', 'wave',
  'decay', 'large_hole', 'bark_pocket', 'stain'
]
const classOptions = classNames.map(value => ({ value, label: classNameZh(value) }))
const annotations = ref([])
const comment = ref('')
const saving = ref('')
const surface = ref(null), imageReady = ref(false), tool = ref('draw')
const selectedId = ref(null), currentClass = ref('dry_knot'), draft = ref(null)
const selected = computed(() => annotations.value.find(box => box.localId === selectedId.value))
const corners = [['x1','y1'], ['x1','y2'], ['x2','y1'], ['x2','y2']]
const labelSize = computed(() => Math.max(10, props.result.imageWidth / 70))
const handleSize = computed(() => Math.max(3, props.result.imageWidth / 145))
let localSequence = 0, gesture = null

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
  selectedId.value = null; draft.value = null; gesture = null
  annotations.value = editableAnnotations(result)
  tool.value = annotations.value.length ? 'select' : 'draw'
  comment.value = result.reviewComment || ''
}, { immediate: true, deep: true })

function selectBox(box) {
  selectedId.value = box.localId; currentClass.value = box.className; tool.value = 'select'
}
function startDrawing() { tool.value = 'draw'; selectedId.value = null }
function changeClass() { if (selected.value && tool.value === 'select') selected.value.className = currentClass.value }
function removeSelected() {
  annotations.value = annotations.value.filter(box => box.localId !== selectedId.value)
  selectedId.value = null
}
function clamp(value, min, max) { return Math.max(min, Math.min(max, value)) }
function point(e) {
  const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(surface.value.getScreenCTM().inverse())
  return {x:clamp(Math.round(p.x),0,props.result.imageWidth), y:clamp(Math.round(p.y),0,props.result.imageHeight)}
}
function bounds(a,b) {
  return {x1: Math.min(a.x,b.x), y1: Math.min(a.y,b.y), x2: Math.max(a.x,b.x), y2: Math.max(a.y,b.y)}
}
function pointerDown(e) {
  if (saving.value || gesture || e.button !== 0) return
  const start = point(e)
  if (tool.value === 'draw') {
    gesture = {id:e.pointerId, start, mode:'draw'}; draft.value = bounds(start,start)
  } else {
    const id = Number(e.target.closest('[data-box]')?.dataset.box)
    const box = annotations.value.find(b => b.localId === id)
    if (!box) { selectedId.value = null; return }
    selectBox(box)
    gesture = {id:e.pointerId,start,mode:'adjust',original:{...box},corner:e.target.dataset.corner?.split(',')}
  }
  surface.value.setPointerCapture(e.pointerId)
  e.preventDefault()
}
function pointerMove(e) {
  if (!gesture || gesture.id !== e.pointerId) return
  const p = point(e), {start,original,corner} = gesture
  if (gesture.mode === 'draw') { draft.value = bounds(start,p); return }
  const box = selected.value
  if (corner) {
    box[corner[0]] = corner[0] === 'x1' ? Math.min(p.x,box.x2-1) : Math.max(p.x,box.x1+1)
    box[corner[1]] = corner[1] === 'y1' ? Math.min(p.y,box.y2-1) : Math.max(p.y,box.y1+1)
  } else {
    const dx = clamp(p.x-start.x,-original.x1,props.result.imageWidth-original.x2)
    const dy = clamp(p.y-start.y,-original.y1,props.result.imageHeight-original.y2)
    Object.assign(box,{x1:original.x1+dx,x2:original.x2+dx,y1:original.y1+dy,y2:original.y2+dy})
  }
}
function pointerUp(e) {
  if (!gesture || gesture.id !== e.pointerId) return
  pointerMove(e)
  const d = draft.value
  if (d && d.x2>d.x1 && d.y2>d.y1) {
    const box = {...d,localId:++localSequence,originalDetailId:null,className:currentClass.value}
    annotations.value.push(box); selectBox(box)
  }
  gesture = null; draft.value = null
}
function cancelGesture(e) {
  if (!gesture || gesture.id !== e.pointerId) return
  if (gesture.original && selected.value) Object.assign(selected.value, gesture.original)
  gesture = null; draft.value = null
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
.editor-tools,.box-list {display:flex; flex-wrap:wrap; align-items:center; gap:8px; margin:10px 0; padding:0; border:0}
.editor-tools select,.editor-tools button,.box-list button {border:1px solid var(--color-border); background:white; color:var(--color-text); border-radius:6px; padding:7px 10px; font:inherit}
button[aria-pressed=true] {background:#e3f2e9; border-color:#31765c}
.image-stage {position:relative; width:fit-content; max-width:100%; margin:10px auto; line-height:0; background:var(--color-surface-muted)}
.image-stage img {display:block; max-width:100%; max-height:75vh; width:auto; height:auto}
.image-stage svg {position:absolute; inset:0; width:100%; height:100%; touch-action:none; cursor:default; user-select:none}
.image-stage svg.drawing {cursor:crosshair}
.outline {fill:#12635522; stroke:#20deae; stroke-width:2; vector-effect:non-scaling-stroke}
.chosen .outline,.draft {fill:#edb94e30; stroke:#ffce62}
.image-stage circle {fill:white; stroke:#80520b; vector-effect:non-scaling-stroke; cursor:nwse-resize}
.image-stage text {fill:white; stroke:#191e1b; stroke-width:2.5px; paint-order:stroke; pointer-events:none}
.box-list {font-size:13px}
.comment-field { display: grid; gap: 7px; margin-top: 18px; font-size: 13px; font-weight: 650; }
.review-actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 16px; }
.review-note { margin: 10px 0 0; color: var(--color-text-muted); font-size: 12px; }
@media (max-width: 980px) {
  .review-context { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 600px) {
  .review-context { grid-template-columns: 1fr; }
  .annotation-heading { align-items: stretch; flex-direction: column; }
  .review-actions { align-items: stretch; flex-direction: column; }
}
</style>
