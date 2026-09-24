import assert from 'node:assert/strict'
import test from 'node:test'
import { classNameZh, formatConfidence, isTaskActive, isTaskTerminal, statusMeta } from './detection.js'

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
  assert.equal(classNameZh('custom_class'), 'custom_class')
  assert.equal(formatConfidence(0.8764), '87.6%')
  assert.equal(formatConfidence(undefined), '—')
})
