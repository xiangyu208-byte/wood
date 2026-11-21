<template>
  <div class="batch-actions">
    <div class="selection" aria-live="polite">
      <strong>已选 {{ selectedIds.length }} 张照片</strong>
      <el-button v-if="selectedIds.length" text @click="$emit('clear')">清除选择</el-button>
    </div>
    <div class="actions">
      <el-button plain @click="open('new')">新建批次</el-button>
      <el-button plain :disabled="!selectedIds.length" @click="open('assign')">归入已有批次</el-button>
      <el-button plain @click="open('merge')">合并批次</el-button>
    </div>
  </div>
  <el-dialog v-model="visible" :title="titles[mode]" width="min(92vw, 470px)"
             :close-on-click-modal="false" :close-on-press-escape="!saving" :show-close="!saving" append-to-body>
    <form class="batch-form" @submit.prevent="save">
      <label v-if="mode === 'new'">新批次编号
        <el-input v-model="target" maxlength="64" placeholder="例如 MC-001" :disabled="saving" />
      </label>
      <template v-else>
        <label>{{ mode === 'merge' ? '保留的批次' : '目标批次' }}
          <select v-model="target" :disabled="loading || saving">
            <option value="" disabled>请选择批次</option>
            <option v-for="code in codes" :key="code" :value="code">{{ code }}</option>
          </select>
        </label>
        <fieldset v-if="mode === 'merge' && codes.length > 1" :disabled="!target || loading || saving">
          <legend>要并入的批次</legend>
          <label v-for="code in sourceOptions" :key="code"><input v-model="sources" type="checkbox" :value="code"> {{ code }}</label>
        </fieldset>
        <p v-if="loading">正在读取批次…</p>
        <p v-else-if="!error && codes.length < (mode === 'merge' ? 2 : 1)">{{ mode === 'merge' ? '至少需要两个批次才能合并。' : '还没有可选批次，请先新建批次。' }}</p>
      </template>
      <p v-if="mode === 'merge'">所选来源批次中的全部照片将归入保留的批次。后续使用原编号采集的照片也会归入该批次。</p>
      <p v-else>{{ selectedIds.length ? '将勾选的 ' + selectedIds.length + ' 张照片归入' + (mode === 'new' ? '新批次' : '目标批次') + '。' : '建立空批次后，可以继续添加照片。' }}</p>
      <p v-if="error" class="inline-error" role="alert">{{ error }}
        <el-button v-if="mode !== 'new'" text :disabled="saving" @click="loadCodes">刷新批次</el-button>
      </p>
      <div class="dialog-actions">
        <el-button :disabled="saving" @click="visible = false">取消</el-button>
        <el-button type="primary" native-type="submit" :disabled="!ready" :loading="saving">{{ submitLabel }}</el-button>
      </div>
    </form>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ElDialog, ElMessage } from 'element-plus'
import { request } from '../api/detect'

const props = defineProps({ selectedIds: { type: Array, required: true }, currentBatch: { type: String, default: '' } })
const emit = defineEmits(['changed', 'clear'])
const titles = { new: '新建批次', assign: '归入已有批次', merge: '合并批次' }
const visible = ref(false), mode = ref('new'), target = ref(''), sources = ref([]), codes = ref([])
const error = ref(''), loading = ref(false), saving = ref(false)
let requestId = 0
const sourceOptions = computed(() => codes.value.filter(code => code !== target.value))
const ready = computed(() => !loading.value && !saving.value && target.value.trim() &&
  (mode.value === 'new' || (codes.value.includes(target.value) &&
    (mode.value === 'merge' ? sources.value.length > 0 : props.selectedIds.length > 0))))
const submitLabel = computed(() => mode.value === 'merge' ? '确认合并' : mode.value === 'assign' ? '确认归入' :
  props.selectedIds.length ? '新建并归入' : '建立批次')
watch(target, code => { sources.value = sources.value.filter(item => item !== code) })

function open(nextMode) {
  requestId++
  mode.value = nextMode; target.value = ''; sources.value = []; codes.value = []
  error.value = ''; loading.value = false; visible.value = true
  if (nextMode !== 'new') loadCodes()
}

async function loadCodes() {
  const id = ++requestId
  loading.value = true; error.value = ''
  try {
    const { data } = await request.get('/inspection/batches')
    if (id !== requestId) return
    codes.value = data
    target.value = [target.value, props.currentBatch].find(code => data.includes(code)) || ''
    sources.value = sources.value.filter(code => data.includes(code) && code !== target.value)
  } catch (e) { if (id === requestId) error.value = e.message }
  finally { if (id === requestId) loading.value = false }
}

async function save() {
  if (!ready.value) return
  saving.value = true; error.value = ''
  try {
    const code = target.value.trim()
    let destination, message
    if (mode.value === 'merge') {
      const { data } = await request.post('/inspection/batches/merge', {targetCode: code, sourceCodes: sources.value})
      destination = data.code
      message = '已合并 ' + sources.value.length + ' 个来源批次，移入 ' + data.photoCount + ' 张照片'
    } else if (mode.value === 'new' && !props.selectedIds.length) {
      const { data } = await request.post('/inspection/batches', {code})
      destination = data; message = '已建立批次 ' + data
    } else {
      const { data } = await request.post('/inspection/batches/assign', {
        code, createNew: mode.value === 'new', recordIds: props.selectedIds
      })
      destination = data.code; message = '已将 ' + data.photoCount + ' 张照片归入 ' + data.code
    }
    visible.value = false
    ElMessage.success(message)
    emit('changed', destination)
  } catch (e) { error.value = e.message }
  finally { saving.value = false }
}
</script>

<style scoped>
.batch-actions, .selection, .dialog-actions { display:flex; align-items:center; flex-wrap:wrap; gap:10px }
.batch-actions { justify-content:space-between; padding:12px 0; margin-bottom:12px; border-block:1px solid var(--color-border) }
.selection, .batch-form { font-size:14px }
.batch-form { display:grid; gap:16px; }
.batch-form > label { display:grid; gap:8px; font-weight:650; }
.batch-form select { width:100%; background:white; color:var(--color-text); border:1px solid var(--color-border); border-radius:6px; padding:9px; }
.batch-form fieldset { max-height:200px; overflow:auto; border:1px solid var(--color-border); border-radius:6px; }
.batch-form fieldset label { display:block; padding:5px; overflow-wrap:anywhere; }
.batch-form p { margin:0; line-height:1.6; }
.dialog-actions { justify-content:flex-end; }
.batch-actions .el-button + .el-button, .dialog-actions .el-button + .el-button { margin-left:0 }
</style>
