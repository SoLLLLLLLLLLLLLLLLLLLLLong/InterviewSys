<template>
  <section class="landing-shell">
    <div class="landing-hero">
      <div class="landing-copy">
        <div class="entry-eyebrow">智能面试辅导场景的前后端完整 Web 系统</div>
        <h1>今天想从哪个方向开始准备？</h1>
        <p>你可以先做一次技术问答热身，也可以直接进入模拟面试，或者回看已有的面试报告继续复盘。</p>
        <div class="landing-actions">
          <button class="primary-button compact-button" @click="emit('open-mode', 'qa')">进入技术问答</button>
          <button class="ghost-button compact-button" @click="emit('open-mode', 'interview')">进入模拟面试</button>
        </div>
      </div>
      <div class="landing-summary-card">
        <div class="summary-stat">
          <strong>{{ auth.user?.display_name || "候选人" }}</strong>
          <span>欢迎回来，继续你的面试训练。</span>
        </div>
        <div class="summary-grid">
          <article>
            <strong>{{ historyCount }}</strong>
            <span>历史报告</span>
          </article>
          <article>
            <strong>{{ projectCount }}</strong>
            <span>项目空间</span>
          </article>
          <article>
            <strong>{{ conversationCount }}</strong>
            <span>会话总数</span>
          </article>
        </div>
      </div>
    </div>

    <div class="landing-mode-grid">
      <button class="landing-mode-card" @click="emit('open-mode', 'qa')">
        <strong>技术问答</strong>
        <span>适合快速提问某个知识点、八股题或面试概念。</span>
      </button>
      <button class="landing-mode-card" @click="emit('open-mode', 'interview')">
        <strong>模拟面试</strong>
        <span>按岗位开始一轮面试，也支持上传简历定制提问。</span>
      </button>
      <button class="landing-mode-card" @click="emit('open-mode', 'history')">
        <strong>历史复盘</strong>
        <span>查看分数、报告和完整问答记录，再恢复继续练习。</span>
      </button>
    </div>

    <div class="landing-guide-grid">
      <article class="landing-guide-card">
        <h3>推荐起步问题</h3>
        <button class="recommend-chip" @click="emit('quick-question', '请解释一下 Redis 的持久化机制')">Redis 持久化机制</button>
        <button class="recommend-chip" @click="emit('quick-question', '请讲一下 HTTP 和 HTTPS 的区别')">HTTP 和 HTTPS 的区别</button>
        <button class="recommend-chip" @click="emit('quick-question', '请解释一下 Vue3 的响应式原理')">Vue3 响应式原理</button>
      </article>

      <article class="landing-guide-card">
        <h3>推荐岗位方向</h3>
        <div class="landing-role-list">
          <button v-for="role in roleOptions.slice(0, 6)" :key="role" class="recommend-chip" @click="emit('open-role', role)">
            {{ role }}
          </button>
        </div>
      </article>

      <article class="landing-guide-card">
        <h3>下一步建议</h3>
        <p>先选一个项目空间，再为不同岗位或不同面试主题创建独立会话，会更方便长期整理。</p>
      </article>
    </div>
  </section>
</template>

<script setup>
// 首页落地页的作用不是承载复杂逻辑，而是给用户一个清晰起点。
// 它更偏产品引导层。
defineProps({
  auth: {
    type: Object,
    required: true,
  },
  historyCount: {
    type: Number,
    default: 0,
  },
  projectCount: {
    type: Number,
    default: 0,
  },
  conversationCount: {
    type: Number,
    default: 0,
  },
  roleOptions: {
    type: Array,
    default: () => [],
  },
});

const emit = defineEmits(["open-mode", "quick-question", "open-role"]);
</script>
