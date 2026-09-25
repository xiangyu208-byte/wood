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
  wave: '波纹'
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
  FIRST_PASS_CONFIDENT: '首轮结果稳定，保留整图推理'
}

export function statusMeta(status) {
  return STATUS_META[status] || { label: status || '未知状态', tone: 'neutral' }
}

export function classNameZh(className) {
  return CLASS_NAME_MAP[className] || className || '未知类别'
}

export function formatConfidence(value) {
  const number = Number(value)
  return Number.isFinite(number) ? `${(number * 100).toFixed(1)}%` : '—'
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
