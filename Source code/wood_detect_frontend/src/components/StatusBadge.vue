<template>
  <span class="status-badge" :class="`status-badge--${meta.tone}`" role="status">
    <span class="status-dot" aria-hidden="true"></span>
    {{ meta.label }}
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { statusMeta } from '../utils/detection'

const props = defineProps({
  status: { type: String, default: '' }
})

const meta = computed(() => statusMeta(props.status))
</script>
