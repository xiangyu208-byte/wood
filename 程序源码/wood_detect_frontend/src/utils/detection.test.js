import assert from 'node:assert/strict'
import test from 'node:test'
import {
  actualModeLabel,
  classNameZh,
  decisionReasonLabel,
  detailScoreLabel,
  formatConfidence,
  formatDuration,
  formatImageSize,
  isTaskActive,
  isTaskTerminal,
  hasSuspectedAnomaly,
  requestedModeLabel,
  reviewCandidateCount,
  statusMeta
} from './detection.js'

test('业务状态映射为明确的中文语义', () => {
  assert.equal(statusMeta('SUCCESS').label, '识别成功')
  assert.equal(statusMeta('FAIL').label, '识别失败')
  assert.equal(statusMeta('PROCESSING').tone, 'warning')
  assert.equal(statusMeta('CANCELLED').label, '已取消')
})

test('任务活动态和终态不会混淆', () => {
  assert.equal(isTaskActive('PENDING'), true)
  assert.equal(isTaskActive('PROCESSING'), true)
  assert.equal(isTaskTerminal('PARTIAL_FAIL'), true)
  assert.equal(isTaskTerminal('CANCELLED'), true)
  assert.equal(isTaskTerminal('PROCESSING'), false)
})

test('缺陷类别和置信度按用户可读格式展示', () => {
  assert.equal(classNameZh('dry_knot'), '干节')
  assert.equal(classNameZh('split'), '裂纹')
  assert.equal(classNameZh('suspected_anomaly'), '疑似异常（需复核）')
  assert.equal(classNameZh('custom_class'), 'custom_class')
  assert.equal(formatConfidence(0.8764), '87.6%')
  assert.equal(formatConfidence(undefined), '—')
  assert.equal(detailScoreLabel({ className: 'suspected_anomaly', confidence: 0.65 }), '候选强度 65.0%')
  assert.equal(hasSuspectedAnomaly([{ className: 'split' }, { className: 'suspected_anomaly' }]), true)
  assert.equal(reviewCandidateCount([{ className: 'split' }, { className: 'suspected_anomaly' }]), 1)
})

test('自适应推理元数据按用户可读格式展示', () => {
  assert.equal(requestedModeLabel('STANDARD'), '自适应')
  assert.equal(actualModeLabel('ADAPTIVE_TILED'), '自适应切片')
  assert.equal(decisionReasonLabel('HIGH_RESOLUTION'), '图片分辨率较高，自动启用切片')
  assert.equal(decisionReasonLabel('EDGE_ONLY_FIRST_PASS'), '首轮结果仅位于图片边缘，自动复查整幅图片')
  assert.equal(formatDuration(842), '842 ms')
  assert.equal(formatDuration(1842), '1.84 秒')
  assert.equal(formatDuration(null), '—')
  assert.equal(formatImageSize(3840, 2160), '3840 × 2160')
})
