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
