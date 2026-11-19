import test from 'node:test'
import assert from 'node:assert/strict'
import { coverage, countClasses } from './boardMap.js'

test('覆盖率取视野并集，包括重复观测和部分重叠', () => {
  const a = {x:0, y:0, width:0.5, height:0.5}
  const b = {...a, x:0.25, y:0.25}
  assert.equal(coverage([a, b, a]), 0.4375)
  assert.equal(coverage([]), 0)
})

test('每张照片保留其观测类别', () => {
  assert.deepEqual(countClasses([{category:'split'}, {category:'dry_knot'}, {category:'split'}]),
    [['split', 2], ['dry_knot', 1]])
})

