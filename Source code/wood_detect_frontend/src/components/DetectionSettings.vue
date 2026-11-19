<template>
  <details class="settings-panel">
    <summary>推理设置 <span>当前：{{ requestedModeLabel(modelValue.modelMode) }}，阈值 {{ modelValue.confidenceThreshold }}</span></summary>
    <div class="settings-grid">
      <label class="field-label">
        <span>模型模式</span>
        <el-select :model-value="modelValue.modelMode" aria-label="模型模式" @update:model-value="update('modelMode', $event)">
          <el-option label="快速整图（512px）" value="FAST" />
          <el-option label="自适应（推荐）" value="STANDARD" />
          <el-option label="精细补检" value="ACCURATE" />
        </el-select>
      </label>

      <label class="field-label field-label--wide">
        <span>置信度阈值：{{ modelValue.confidenceThreshold }}</span>
        <el-slider
          :model-value="modelValue.confidenceThreshold"
          :min="0.05"
          :max="0.95"
          :step="0.05"
          show-input
          :show-input-controls="false"
          aria-label="置信度阈值"
          @update:model-value="update('confidenceThreshold', $event)"
        />
      </label>

      <label class="field-label">
        <span>推理精度</span>
        <el-select :model-value="modelValue.precision" aria-label="推理精度" @update:model-value="update('precision', $event)">
          <el-option label="自动选择" value="AUTO" />
          <el-option label="FP32（兼容优先）" value="FP32" />
          <el-option label="FP16（仅 CUDA）" value="FP16" />
        </el-select>
      </label>
    </div>
    <p class="settings-note">当前模型识别 10 类缺陷。自适应模式会根据图片与首轮结果放大局部，并增强对比度、复查裂纹；精细补检增加小图的细裂纹检查。所有结果遵守设置的置信度阈值，新增增强视图结果至少达到 35%，保留真实置信度。降低阈值可能增加误检。精细补检耗时更长，FP16 仅适用于 CUDA。</p>
  </details>
</template>

<script setup>
import { requestedModeLabel } from '../utils/detection'

const props = defineProps({
  modelValue: { type: Object, required: true }
})
const emit = defineEmits(['update:modelValue'])

function update(key, value) {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}
</script>
