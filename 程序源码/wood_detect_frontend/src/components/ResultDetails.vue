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

    <section v-if="result.qualityScore !== null && result.qualityScore !== undefined" class="quality-panel" :aria-labelledby="`quality-${result.recordId}`">
      <div class="quality-overview">
        <div>
          <p class="eyebrow">可解释质量评价</p>
          <h3 :id="`quality-${result.recordId}`">质量分 {{ formatQualityScore(result.qualityScore) }}</h3>
        </div>
        <strong class="quality-grade" :class="`grade-${String(result.qualityGrade || '').toLowerCase()}`">
          {{ qualityGradeLabel(result.qualityGrade) }}
        </strong>
      </div>
      <dl class="quality-metrics">
        <div><dt>缺陷覆盖率</dt><dd>{{ formatRatioPercent(result.defectAreaRatio) }}</dd></div>
        <div><dt>最大缺陷面积率</dt><dd>{{ formatRatioPercent(result.maxDefectAreaRatio) }}</dd></div>
        <div><dt>规则版本</dt><dd>{{ result.qualityRuleVersion || '—' }}</dd></div>
      </dl>
      <div class="quality-columns">
        <div>
          <h4>各类别数量</h4>
          <ul class="count-list">
            <li v-for="([className, count]) in Object.entries(result.defectCounts || {})" :key="className">
              <span>{{ classNameZh(className) }}</span><strong>{{ count }}</strong>
            </li>
            <li v-if="!Object.keys(result.defectCounts || {}).length"><span>未检测到缺陷</span><strong>0</strong></li>
          </ul>
        </div>
        <div>
          <h4>具体扣分原因</h4>
          <ul class="deduction-list">
            <li v-for="(item, index) in result.qualityDeductions || []" :key="`${item.type}-${index}`">
              <div><strong>{{ item.label }}</strong><span>{{ item.explanation }}</span></div>
              <b>-{{ formatQualityScore(item.points) }}</b>
            </li>
            <li v-if="!(result.qualityDeductions || []).length" class="no-deduction">无扣分，基础分保持 100 分</li>
          </ul>
        </div>
      </div>
      <p class="quality-disclaimer">{{ result.qualityDisclaimer }}</p>
    </section>

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
  formatQualityScore,
  formatRatioPercent,
  fullImageUrl,
  hasSuspectedAnomaly,
  reviewCandidateCount,
  requestedModeLabel,
  qualityGradeLabel
} from '../utils/detection'

defineProps({ result: { type: Object, required: true } })
</script>

<style scoped>
.quality-panel { margin-top: 20px; padding: 20px; border: 1px solid var(--color-border); border-radius: var(--radius-md); background: var(--color-surface-muted); }
.quality-overview { display: flex; align-items: center; justify-content: space-between; gap: 18px; }
.quality-overview h3 { margin: 2px 0 0; font-size: 22px; }
.quality-grade { display: grid; min-width: 64px; height: 44px; padding: 0 14px; place-items: center; border-radius: 999px; font-size: 18px; }
.grade-a { color: #176b45; background: #dff5e9; }
.grade-b { color: #245a82; background: #deeffa; }
.grade-c { color: #8a5a12; background: #fff0cf; }
.grade-d { color: #9a3030; background: #fde3e3; }
.quality-metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin: 18px 0; }
.quality-metrics div { padding: 12px; border-radius: 10px; background: var(--color-surface); }
.quality-metrics dt { color: var(--color-text-muted); font-size: 12px; }
.quality-metrics dd { margin: 5px 0 0; font-weight: 700; }
.quality-columns { display: grid; grid-template-columns: minmax(180px, .75fr) minmax(280px, 1.25fr); gap: 18px; }
.quality-columns h4 { margin: 0 0 10px; }
.count-list, .deduction-list { margin: 0; padding: 0; list-style: none; }
.count-list li, .deduction-list li { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 9px 0; border-bottom: 1px solid var(--color-border); }
.deduction-list li > div { display: grid; gap: 3px; }
.deduction-list span { color: var(--color-text-muted); font-size: 12px; }
.deduction-list b { color: #9a3030; white-space: nowrap; }
.no-deduction { color: var(--color-text-muted); }
.quality-disclaimer { margin: 16px 0 0; color: var(--color-text-muted); font-size: 12px; line-height: 1.6; }
@media (max-width: 700px) {
  .quality-metrics, .quality-columns { grid-template-columns: 1fr; }
  .quality-overview { align-items: flex-start; }
}
</style>
