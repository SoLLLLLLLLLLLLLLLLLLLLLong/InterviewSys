<template>
  <div class="welcome-panel">
    <h2>{{ title }}</h2>
    <p v-for="line in lines" :key="line">{{ line }}</p>
  </div>
</template>

<script setup>
// 一个可配置的空状态组件。
// title 和 lines 都由父组件传入，所以不同页面可以复用它来展示自己的引导文案。
defineProps({
  title: {
    type: String,
    default: "",
  },
  lines: {
    type: Array,
    default: () => [],
  },
});
</script>
