<template>
  <details class="settings-panel">
    <summary>推理设置 <span>当前：{{ modeLabel }}，阈值 {{ modelValue.confidenceThreshold }}</span></summary>
    <div class="settings-grid">
      <label class="field-label">
        <span>模型模式</span>
        <el-select :model-value="modelValue.modelMode" aria-label="模型模式" @update:model-value="update('modelMode', $event)">
          <el-option label="快速（512px）" value="FAST" />
          <el-option label="标准（640px）" value="STANDARD" />
          <el-option label="精确（960px）" value="ACCURATE" />
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
    <p class="settings-note">精确模式能保留更多小目标细节，但耗时更长。FP16 仅适用于 CUDA 推理服务。</p>
  </details>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: Object, required: true }
})
const emit = defineEmits(['update:modelValue'])

const modeLabel = computed(() => ({ FAST: '快速', STANDARD: '标准', ACCURATE: '精确' }[props.modelValue.modelMode]))

function update(key, value) {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}
</script>
