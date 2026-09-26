export const STATUS_META = {
  PENDING: { label: '等待处理', tone: 'neutral' },
  PROCESSING: { label: '处理中', tone: 'warning' },
  SUCCESS: { label: '识别成功', tone: 'success' },
  FAIL: { label: '识别失败', tone: 'danger' },
  PARTIAL_FAIL: { label: '部分失败', tone: 'warning' },
  CANCELLED: { label: '已取消', tone: 'neutral' }
}

export const CLASS_NAME_MAP = {
  dry_knot: '干节',
  sound_knot: '健全节',
  edge_knot: '边节',
  small_knot: '小节',
  split: '裂纹',
  wave: '波纹',
  suspected_anomaly: '疑似异常（需复核）'
}

export const REQUESTED_MODE_LABELS = {
  FAST: '快速整图',
  STANDARD: '自适应',
  ACCURATE: '精细切片'
}

export const ACTUAL_MODE_LABELS = {
  FAST_WHOLE: '快速整图',
  STANDARD_WHOLE: '标准整图',
  ADAPTIVE_TILED: '自适应切片',
  TILED_ACCURATE: '精细切片'
}

export const DECISION_REASON_LABELS = {
  REQUESTED_FAST: '按设置执行快速整图',
  REQUESTED_ACCURATE: '按设置执行重叠切片',
  HIGH_RESOLUTION: '图片分辨率较高，自动启用切片',
  NO_FIRST_PASS_DETECTION: '首轮未检出目标，自动复查局部',
  LOW_FIRST_PASS_CONFIDENCE: '首轮置信度较低，自动复查局部',
  SMALL_FIRST_PASS_TARGET: '首轮发现小目标，自动复查局部',
  EDGE_ONLY_FIRST_PASS: '首轮结果仅位于图片边缘，自动复查整幅图片',
  FIRST_PASS_CONFIDENT: '首轮结果稳定，保留整图推理'
}

export const REVIEW_STATUS_META = {
  UNREVIEWED: { label: '未复核', tone: 'neutral' },
  CORRECT: { label: '结果正确', tone: 'success' },
  INCORRECT: { label: '结果错误', tone: 'danger' },
  CORRECTED: { label: '已人工修正', tone: 'warning' }
}

export const REVIEW_REASON_LABELS = {
  LOW_CONFIDENCE: '存在低置信度检测',
  SUSPECTED_ANOMALY: '存在疑似异常复核候选'
}

export const ANNOTATION_SOURCE_LABELS = {
  MODEL_CONFIRMED: '模型框已确认',
  HUMAN_CORRECTED: '人工修正',
  HUMAN_ADDED: '人工补充'
}

export function statusMeta(status) {
  return STATUS_META[status] || { label: status || '未知状态', tone: 'neutral' }
}

export function classNameZh(className) {
  return CLASS_NAME_MAP[className] || className || '未知类别'
}

export function formatConfidence(value) {
  if (value === null || value === undefined || value === '') return '—'
  const number = Number(value)
  return Number.isFinite(number) ? `${(number * 100).toFixed(1)}%` : '—'
}

export function detailScoreLabel(detail) {
  const score = formatConfidence(detail?.confidence)
  return detail?.className === 'suspected_anomaly' ? `候选强度 ${score}` : score
}

export function hasSuspectedAnomaly(details = []) {
  return details.some(detail => detail.className === 'suspected_anomaly')
}

export function reviewCandidateCount(details = []) {
  return details.filter(detail => detail.className === 'suspected_anomaly').length
}

export function requestedModeLabel(mode) {
  return REQUESTED_MODE_LABELS[mode] || mode || '—'
}

export function actualModeLabel(mode) {
  return ACTUAL_MODE_LABELS[mode] || mode || '等待推理'
}

export function decisionReasonLabel(reason) {
  return DECISION_REASON_LABELS[reason] || reason || '—'
}

export function formatDuration(milliseconds) {
  if (milliseconds === null || milliseconds === undefined || milliseconds === '') return '—'
  const value = Number(milliseconds)
  if (!Number.isFinite(value)) return '—'
  return value < 1000 ? `${Math.round(value)} ms` : `${(value / 1000).toFixed(2)} 秒`
}

export function formatImageSize(width, height) {
  return width && height ? `${width} × ${height}` : '—'
}

export function formatQualityScore(score) {
  if (score === null || score === undefined || score === '') return '—'
  const value = Number(score)
  return Number.isFinite(value) ? value.toFixed(2) : '—'
}

export function formatRatioPercent(ratio) {
  if (ratio === null || ratio === undefined || ratio === '') return '—'
  const value = Number(ratio)
  return Number.isFinite(value) ? `${(value * 100).toFixed(2)}%` : '—'
}

export function qualityGradeLabel(grade) {
  return grade ? `${grade} 级` : '未评分'
}

export function reviewStatusMeta(status) {
  return REVIEW_STATUS_META[status] || { label: status || '未复核', tone: 'neutral' }
}

export function reviewReasonLabel(reason) {
  return REVIEW_REASON_LABELS[reason] || reason || '常规抽检'
}

export function annotationSourceLabel(source) {
  return ANNOTATION_SOURCE_LABELS[source] || source || '—'
}

export function isReviewPending(result) {
  return Boolean(result?.reviewNeeded) && (!result?.reviewStatus || result.reviewStatus === 'UNREVIEWED')
}

export function formatMetricChange(value, suffix = '') {
  if (value === null || value === undefined || value === '') return '—'
  const number = Number(value)
  if (!Number.isFinite(number)) return '—'
  return `${number > 0 ? '+' : ''}${number.toFixed(2)}${suffix}`
}

export function fullImageUrl(url) {
  if (!url) return ''
  return new URL(url, window.location.origin).toString()
}

export function isTaskActive(status) {
  return status === 'PENDING' || status === 'PROCESSING'
}

export function isTaskTerminal(status) {
  return ['SUCCESS', 'FAIL', 'PARTIAL_FAIL', 'CANCELLED'].includes(status)
}
