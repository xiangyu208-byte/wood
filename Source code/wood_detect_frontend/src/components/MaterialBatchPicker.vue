<template>
  <div class="batch-picker">
    <label>
      <span>板材批次</span>
      <select :value="modelValue" :disabled="disabled || creating" @change="$emit('update:modelValue', $event.target.value)">
        <option value="">{{ emptyLabel }}</option>
        <option v-for="code in codes" :key="code" :value="code">{{ code }}</option>
      </select>
    </label>
    <el-button v-if="allowCreate" plain :disabled="disabled || creating" @click="create">新建批次</el-button>
    <button v-if="error" type="button" class="link" @click="load">{{ error }} · 重试</button>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import { request } from '../api/detect'

defineProps({
  modelValue: { type: String, default: '' }, disabled: Boolean,
  emptyLabel: { type: String, default: '不分批次' }, allowCreate: { type: Boolean, default: true }
})
const emit = defineEmits(['update:modelValue'])
const codes = ref([]), error = ref(''), creating = ref(false)
async function load() {
  try { codes.value = (await request.get('/inspection/batches')).data; error.value = '' }
  catch (e) { error.value = e.message }
}
async function create() {
  creating.value = true
  try {
    const { value } = await ElMessageBox.prompt('给这组板材设置一个编号。后续上传或采集可以继续使用这个编号。', '新建板材批次', {
      inputPlaceholder: '例如 MC-001', inputPattern: /^[\p{L}\p{N}][\p{L}\p{N} _.\-]{0,63}$/u,
      inputErrorMessage: '请输入 1–64 位编号，以文字或数字开头', confirmButtonText: '建立批次', cancelButtonText: '取消'
    })
    const { data } = await request.post('/inspection/batches', { code: value.trim() })
    codes.value = [data, ...codes.value.filter(code => code !== data)]
    emit('update:modelValue', data)
  } catch (e) { if (e?.message) ElMessage.error(e.message) }
  finally { creating.value = false }
}
onMounted(load)
</script>

<style scoped>
.batch-picker, .batch-picker label { display:flex; align-items:center; flex-wrap:wrap; gap:10px }
.batch-picker { margin:14px 0 }
.batch-picker label span { font-size:14px; font-weight:650 }
select { min-width:145px; max-width:100%; padding:7px 10px; color:var(--color-text); background:var(--color-surface); border:1px solid var(--color-border); border-radius:6px; font:inherit }
.link { border:0; background:none; color:var(--color-danger); cursor:pointer }
</style>
