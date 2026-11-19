<template>
  <details class="visual-review" @toggle="checkConfig">
    <summary>DeepSeek 图像交叉复核</summary>
    <p>将该张原图和 YOLO 框发送给 DeepSeek，检查疑似漏检、类别和框位。</p>
    <el-button :disabled="!enabled" :loading="busy" @click="review">发送并复核</el-button>
    <span v-if="enabled===false">服务端需配置 DEEPSEEK_API_KEY</span>
    <p role="alert" v-if="error">{{ error }}</p>
    <article v-if="answer"><strong>{{ answer.model }} · 辅助意见</strong><p>{{ answer.text }}</p>
      <router-link :to="'/history/'+recordId">查看原图并完成人工复核</router-link></article>
  </details>
</template>
<script setup>
import { ref } from 'vue'
import { reviewImage, aiConfig } from '../api/boards'
const props=defineProps({recordId:{type:Number,required:true}})
const busy=ref(false), enabled=ref(null), answer=ref(null), error=ref('')
async function checkConfig(event) {
  if (!event.target.open) return
  try { enabled.value=(await aiConfig()).data.configured; error.value='' }
  catch(e) {error.value=e.message}
}
async function review() {
  busy.value=true; error.value=''; answer.value=null
  try {answer.value=(await reviewImage(props.recordId)).data}
  catch(e) {error.value=e.message}
  finally {busy.value=false}
}
</script>
<style scoped>
.visual-review {padding:.9rem 0}.visual-review summary {cursor:pointer;font-weight:650}.visual-review article p {white-space:pre-wrap}.visual-review span {margin-left:.5rem}
</style>

