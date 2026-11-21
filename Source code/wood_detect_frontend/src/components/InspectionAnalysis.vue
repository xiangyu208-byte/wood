<template>
  <section class="analysis">
    <div class="section-heading">
      <div><h3>大模型结果分析</h3><p>{{ materialBatch ? '板材批次 · ' + materialBatch : recordIds.length ? '所选图片 · ' + recordIds.length + ' 张' : '选择一个板材批次或勾选历史记录，即可查看图表并生成报告。' }}</p></div>
      <el-button :disabled="!available || loading" @click="opened ? close() : load(false)">{{ opened ? '收起分析' : '查看分析' }}</el-button>
    </div>
    <template v-if="opened">
      <p v-if="error" class="inline-error" role="alert">{{ error }} <el-button text @click="load(!facts ? false : failedReport)">重试</el-button></p>
      <p v-if="loading" role="status">{{ generating ? '大模型正在生成报告…' : '正在汇总图片…' }}</p>
      <template v-if="facts">
        <p>共 {{ facts.total }} 条记录，{{ facts.photos.length }} 张识别成功<span v-if="reviewedCount">，其中 {{ reviewedCount }} 张采用人工复核标注</span>。</p>
        <div v-if="facts.photos.length" class="charts">
          <section><h4>缺陷类型分布</h4>
            <p v-if="!categories.length">未发现缺陷</p>
            <div v-for="[name,count] in categories" :key="name" class="bar-row">
              <span>{{ classNameZh(name) }}</span><div class="track"><i :style="{width: (count / categories[0][1] * 100) + '%'}"></i></div><b>{{ count }} 个</b>
            </div>
          </section>
          <section><h4>逐图规则扣分</h4>
            <p class="muted">按扣分从高到低排列，质量分最低为 0 分。</p>
            <div v-for="p in pagePhotos" :key="p.id" class="photo-row">
              <router-link :to="'/history/' + p.id">#{{ p.id }} · {{ p.name }}</router-link>
              <div class="bar-row"><div class="track"><i :style="{width: ((p.deduction || 0) / maxDeduction * 100) + '%'}"></i></div><b>{{ p.deduction == null ? '未评分' : p.deduction + ' 分' }}</b></div>
              <small>{{ defectText(p.defects) }} · 质量分 {{ p.score ?? '—' }}</small>
              <details v-if="Object.keys(p.deductions).length"><summary>扣分明细</summary>
                <small v-for="[label,points] in Object.entries(p.deductions)" :key="label">{{ label }} · {{ points }} 分</small>
              </details>
            </div>
            <el-pagination v-if="sortedPhotos.length > 6" v-model:current-page="page" small layout="prev, pager, next" :page-size="6" :total="sortedPhotos.length"/>
          </section>
        </div>
        <div class="report"><h4>分析报告</h4>
          <p v-if="report" class="narrative">{{ report }}</p>
          <template v-else><p>按需将逐图评分和缺陷统计提交给大模型。相邻照片可能拍到同一处缺陷。</p>
            <el-button type="primary" :disabled="loading || !facts.photos.length" @click="load(true)">生成分析报告</el-button>
          </template>
        </div>
      </template>
    </template>
  </section>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import { request } from '../api/detect'
import { classNameZh } from '../utils/detection'
const props = defineProps({ materialBatch: { type: String, default: '' }, recordIds: { type: Array, default: () => [] }, revision: { type: [String, Number], default: '' } })
const opened = ref(false), loading = ref(false), generating = ref(false), failedReport = ref(false)
const facts = ref(null), report = ref(''), error = ref(''), page = ref(1)
let version = 0
const available = computed(() => Boolean(props.materialBatch || props.recordIds.length))
const categories = computed(() => Object.entries(facts.value?.defects || {}).sort((a,b) => b[1]-a[1]))
const sortedPhotos = computed(() => [...(facts.value?.photos || [])].sort((a,b) => (b.deduction ?? -1)-(a.deduction ?? -1)))
const reviewedCount = computed(() => sortedPhotos.value.filter(p => p.reviewStatus && p.reviewStatus !== 'UNREVIEWED').length)
const maxDeduction = computed(() => Math.max(1, sortedPhotos.value[0]?.deduction || 0))
const pagePhotos = computed(() => sortedPhotos.value.slice((page.value-1)*6, page.value*6))
function defectText(counts) { return Object.entries(counts).map(([k,v]) => classNameZh(k)+' × '+v).join('、') || '未发现缺陷' }
function close() {
  version++; opened.value = false; facts.value = null; report.value = ''; error.value = ''; loading.value = false; page.value = 1
}
watch(() => JSON.stringify([props.materialBatch, props.recordIds, props.revision]), close)
async function load(generate) {
  const current = ++version
  opened.value = true; loading.value = true; generating.value = generate; error.value = ''
  try {
    const scope = props.materialBatch ? {materialBatch: props.materialBatch} : {recordIds: props.recordIds}
    const {data} = await request.post('/inspection/'+(generate ? 'report' : 'statistics'), scope, {timeout:110000})
    if (current === version) { facts.value = data.facts; report.value = data.report || '' }
  } catch (e) { if (current === version) { error.value = e.message; failedReport.value = generate } }
  finally { if (current === version) loading.value = false }
}
</script>
<style scoped>
.analysis { margin:18px 0; padding:20px; border:1px solid var(--color-border); border-radius:var(--radius-md); background:var(--color-surface) }
h3,h4 { margin:0 0 6px } .section-heading p,small,.muted { margin:0; color:var(--color-text-muted); font-size:13px }
.charts { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(245px,100%),1fr)); gap:24px }
.charts section,.report { border-top:1px solid var(--color-border); padding-top:14px; min-width:0 }
.bar-row { display:flex; align-items:center; gap:8px; margin:8px 0; font-size:13px }
.bar-row b { min-width:42px; text-align:right } .track { flex:1; background:var(--color-surface-muted); height:9px; border-radius:5px; overflow:hidden }
.track i { display:block; height:100%; background:#36745e } .photo-row .track i { background:#ac6b38 }
.photo-row { margin:10px 0; overflow-wrap:anywhere } .photo-row a { color:var(--color-text) }
.photo-row details { margin-top:4px; font-size:12px } .photo-row summary { cursor:pointer } .photo-row details small { display:block }
.report { margin-top:18px } .narrative { white-space:pre-wrap; line-height:1.75 }
</style>
