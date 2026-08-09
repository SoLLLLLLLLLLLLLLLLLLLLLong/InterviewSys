<template>
  <header class="mode-header-shell">
    <div class="mode-header">
      <div class="mode-header-copy">
        <!-- meta 来自后端返回的页面文案配置。
             这样问答模式、面试模式、历史模式可以共享同一个顶部头部组件。 -->
        <h1>{{ meta.title || "智能面试辅导系统" }}</h1>
        <p>{{ meta.caption || "" }}</p>
        <div v-if="progressMessage" class="progress-banner">{{ progressMessage }}</div>
      </div>
      <div class="weather-cloud">
        <!-- 天气信息通常在 bootstrap 阶段由后端一起返回。 -->
        <p class="weather-city">📍 当前城市：{{ weather.city }}</p>
        <p class="weather-text">{{ weather.text }}</p>
      </div>
    </div>
  </header>
</template>

<script setup>
defineProps({
  // 顶部头部主要展示三类信息：
  // 1. 当前模式标题
  // 2. 当前模式说明
  // 3. 当前更细粒度的进度提示
  meta: {
    type: Object,
    default: () => ({}),
  },
  weather: {
    type: Object,
    default: () => ({
      city: "未知城市",
      text: "天气获取中...",
    }),
  },
  // progressMessage 在流式过程中很常见，
  // 比如“正在分析简历”“正在生成报告”。
  progressMessage: {
    type: String,
    default: "",
  },
});
</script>
