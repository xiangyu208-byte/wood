<template>
  <div class="position-fields">
    <label>定位方式
      <select v-model="placement.mode">
        <option value="UNKNOWN">仅关联板号，位置待定</option>
        <option value="GRID">已知拍摄格位</option>
        <option value="OVERLAP" :disabled="!anchors.length">与基准局部照做纹理配准</option>
      </select>
    </label>
    <template v-if="placement.mode==='GRID'">
      <label>行（从上往下）<input v-model.number="placement.row" type="number" min="1" :max="view.board.rows"></label>
      <label>列（从左往右）<input v-model.number="placement.col" type="number" min="1" :max="view.board.cols"></label>
    </template>
    <label v-if="placement.mode==='OVERLAP'">重叠的基准照片
      <select v-model="placement.anchorId"><option :value="null">选择格位照片</option><option v-for="c in anchors" :key="c.recordId" :value="c.recordId">#{{ c.recordId }} {{ c.name }}</option></select>
    </label>
  </div>
  <p v-if="placement.mode==='GRID'" class="muted">板面正对镜头，图像左上与板面左上同向。整幅局部图应正好覆盖所选等分格。</p>
  <p v-if="placement.mode==='OVERLAP'" class="muted">选择同一板面的已知格位照片。保持倍率、分辨率及朝向，两张照片需有重叠木纹。</p>
</template>
<script setup>
import { computed } from 'vue'
const props = defineProps({view: {type:Object,required:true}, recordId:Number})
const placement = defineModel({type:Object,required:true})
const anchors = computed(() => props.view.captures.filter(c => c.area && !c.anchorId && c.recordId !== props.recordId))
</script>
<style scoped>
.position-fields {display:flex;gap:.9rem;flex-wrap:wrap;align-items:end}
label {display:grid;gap:.3rem;font-size:.88rem}
input,select {padding:.5rem;border:1px solid var(--color-border);border-radius:6px;background:var(--color-surface);color:inherit}
input {width:7rem}
</style>

