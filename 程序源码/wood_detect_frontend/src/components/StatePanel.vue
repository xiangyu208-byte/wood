<template>
  <div class="state-panel" :class="`state-panel--${tone}`" :aria-busy="tone === 'loading'">
    <div class="state-symbol" aria-hidden="true">{{ symbol }}</div>
    <div>
      <h2>{{ title }}</h2>
      <p>{{ description }}</p>
      <div v-if="$slots.action" class="state-action">
        <slot name="action" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  tone: { type: String, default: 'empty' },
  title: { type: String, required: true },
  description: { type: String, required: true }
})

const symbol = computed(() => ({
  loading: '···',
  error: '!',
  offline: '×',
  empty: '○'
}[props.tone] || '○'))
</script>
