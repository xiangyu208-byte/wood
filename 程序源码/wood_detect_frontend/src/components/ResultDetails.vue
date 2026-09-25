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
    <p v-if="hasSuspectedAnomaly(result.details)" class="inline-warning" role="status">
      检测到训练类别之外的明显暗部或空洞，已作为“疑似异常”补充标记。候选强度不是模型置信度，请结合原图人工复核。
    </p>

    <dl class="summary-grid">
      <div><dt>缺陷数量</dt><dd>{{ result.totalCount ?? 0 }}</dd></div>
      <div><dt>复核候选</dt><dd>{{ reviewCandidateCount(result.details) }}</dd></div>
      <div><dt>请求模式</dt><dd>{{ requestedModeLabel(result.modelMode) }}</dd></div>
      <div><dt>实际模式</dt><dd>{{ actualModeLabel(result.actualMode) }}</dd></div>
      <div><dt>选择依据</dt><dd>{{ decisionReasonLabel(result.decisionReason) }}</dd></div>
      <div><dt>推理耗时</dt><dd>{{ formatDuration(result.inferenceDurationMs) }}</dd></div>
      <div><dt>推理区域</dt><dd>{{ result.tileCount ?? '—' }}</dd></div>
      <div><dt>图片尺寸</dt><dd>{{ formatImageSize(result.imageWidth, result.imageHeight) }}</dd></div>
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
        <thead><tr><th>类别</th><th>置信度 / 候选强度</th><th>坐标范围</th></tr></thead>
        <tbody>
          <tr v-for="(detail, index) in result.details || []" :key="`${detail.className}-${index}`">
            <td><strong>{{ classNameZh(detail.className) }}</strong><small>{{ detail.className }}</small></td>
            <td>{{ detailScoreLabel(detail) }}</td>
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
import {
  actualModeLabel,
  classNameZh,
  decisionReasonLabel,
  detailScoreLabel,
  formatDuration,
  formatImageSize,
  fullImageUrl,
  hasSuspectedAnomaly,
  reviewCandidateCount,
  requestedModeLabel
} from '../utils/detection'

defineProps({ result: { type: Object, required: true } })
</script>
