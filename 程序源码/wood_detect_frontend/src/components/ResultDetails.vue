<template>
  <section class="result-details" :aria-labelledby="`result-${result.recordId}`">
    <header class="section-heading result-heading">
      <div>
        <p class="eyebrow">记录 #{{ result.recordId }}</p>
        <h2 :id="`result-${result.recordId}`">{{ result.imageName }}</h2>
      </div>
      <StatusBadge :status="result.status" />
    </header>

    <p v-if="result.errorMessage" class="inline-error" role="alert">{{ result.errorMessage }}</p>

    <dl class="summary-grid">
      <div><dt>缺陷数量</dt><dd>{{ result.totalCount ?? 0 }}</dd></div>
      <div><dt>模型模式</dt><dd>{{ modeLabel(result.modelMode) }}</dd></div>
      <div><dt>置信度阈值</dt><dd>{{ result.confidenceThreshold ?? '—' }}</dd></div>
      <div><dt>推理精度</dt><dd>{{ result.inferencePrecision || '—' }}</dd></div>
      <div><dt>检测时间</dt><dd>{{ result.createTime || '—' }}</dd></div>
    </dl>

    <div v-if="result.status === 'SUCCESS'" class="image-compare">
      <figure>
        <figcaption>原图</figcaption>
        <img :src="fullImageUrl(result.imageUrl)" :alt="`${result.imageName} 原图`" loading="lazy" />
      </figure>
      <figure>
        <figcaption>识别结果图</figcaption>
        <img :src="fullImageUrl(result.resultImageUrl)" :alt="`${result.imageName} 识别结果图`" loading="lazy" />
      </figure>
    </div>

    <div v-if="result.status === 'SUCCESS'" class="detail-table-wrap">
      <table class="detail-table">
        <caption>缺陷明细</caption>
        <thead><tr><th>类别</th><th>置信度</th><th>坐标范围</th></tr></thead>
        <tbody>
          <tr v-for="(detail, index) in result.details || []" :key="`${detail.className}-${index}`">
            <td><strong>{{ classNameZh(detail.className) }}</strong><small>{{ detail.className }}</small></td>
            <td>{{ formatConfidence(detail.confidence) }}</td>
            <td>{{ detail.x1 }}, {{ detail.y1 }} → {{ detail.x2 }}, {{ detail.y2 }}</td>
          </tr>
          <tr v-if="!(result.details || []).length"><td colspan="3" class="table-empty">未检测到缺陷</td></tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup>
import StatusBadge from './StatusBadge.vue'
import { classNameZh, formatConfidence, fullImageUrl } from '../utils/detection'

defineProps({ result: { type: Object, required: true } })

function modeLabel(mode) {
  return ({ FAST: '快速', STANDARD: '标准', ACCURATE: '精确' }[mode]) || mode || '—'
}
</script>
