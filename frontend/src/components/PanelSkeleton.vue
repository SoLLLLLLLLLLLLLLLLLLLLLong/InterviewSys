<template>
  <section class="panel-skeleton" :class="compact ? 'compact' : ''">
    <div class="skeleton skeleton-title"></div>
    <div class="skeleton skeleton-line"></div>
    <div class="skeleton skeleton-line short"></div>
    <div v-for="item in rows" :key="item" class="skeleton-message-row">
      <div class="skeleton skeleton-avatar"></div>
      <div class="skeleton-message-body">
        <div class="skeleton skeleton-bubble"></div>
        <div class="skeleton skeleton-bubble short"></div>
      </div>
    </div>
  </section>
</template>

<script setup>
defineProps({
  // rows 控制骨架屏里模拟多少条消息。
  // compact 用来控制是否采用更紧凑的占位布局。
  rows: {
    type: Number,
    default: 4,
  },
  compact: {
    type: Boolean,
    default: false,
  },
});
</script>
