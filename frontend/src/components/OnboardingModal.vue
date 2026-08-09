<template>
  <div class="guide-backdrop">
    <div class="guide-modal">
      <div class="guide-eyebrow">首次进入引导</div>
      <h2>先帮你快速熟悉这个面试工作台</h2>
      <p class="guide-copy">你可以先选一个起点，也可以直接跳过，稍后再自己探索。</p>

      <div class="guide-steps">
        <button class="guide-step-card" @click="emit('choose', 'qa')">
          <strong>技术问答</strong>
          <span>先试一个技术问题，快速体验知识问答。</span>
        </button>
        <button class="guide-step-card" @click="emit('choose', 'interview')">
          <strong>模拟面试</strong>
          <span>按岗位开始一轮模拟面试，也可以上传简历。</span>
        </button>
        <button class="guide-step-card" @click="emit('choose', 'history')">
          <strong>历史复盘</strong>
          <span>查看已经生成的报告、面试记录和恢复入口。</span>
        </button>
      </div>

      <div class="guide-actions">
        <button class="ghost-button compact-button" @click="emit('skip')">先跳过</button>
      </div>
    </div>
  </div>
</template>

<script setup>
// 新手引导层只负责把用户意图抛给上层。
// 是否真正标记 onboarding 完成，交给更上层的业务编排去决定。
const emit = defineEmits(["choose", "skip"]);
</script>
