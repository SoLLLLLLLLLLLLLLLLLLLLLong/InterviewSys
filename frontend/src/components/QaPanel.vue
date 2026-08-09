<template>
  <!-- 问答主面板：上面是聊天内容，下面是固定输入区。 -->
  <div class="qa-workspace">
    <section class="conversation-shell">
      <!-- 空状态：没有历史消息时展示引导文案。 -->
      <WelcomePanel
        v-if="showWelcome && !history.length"
        :title="meta.empty_title || '欢迎使用问答模式'"
        :lines="meta.empty_description || []"
      />
      <!-- 有历史消息后展示聊天气泡列表。 -->
      <ChatHistory
        v-else
        :messages="history"
        :can-resume="canResume"
        :can-retry="canRetry"
        @resume-last="emit('resume-last')"
        @retry-last="emit('retry-last')"
      />
    </section>

    <!-- 输入区固定在底部，避免聊天内容很多时按钮被挤走。 -->
    <footer class="chat-input-shell">
      <div class="toolbar-row qa-input-toolbar">
        <button class="ghost-button compact-button" :disabled="loadingAction === 'qa-clear'" @click="emit('clear-history')">
          {{ loadingAction === "qa-clear" ? "清空中..." : "清空问答历史" }}
        </button>
        <div v-if="isTyping" class="qa-inline-status">
          <i class="run-pulse running"></i>
          <span>正在组织回答...</span>
        </div>
      </div>
      <!-- 生成中时不额外占一行，而是把原来的发送按钮切换成“停止”。 -->
      <form class="chat-form" @submit.prevent="isTyping ? emit('stop') : emit('send')">
        <!--
          :value + @input 是“单向传值 + 事件回传”的写法。
          这里不用 v-model，是因为 inputValue 来自父组件/Pinia，子组件只负责通知父组件更新。
        -->
        <input
          :value="inputValue"
          class="chat-input"
          :disabled="isTyping"
          placeholder="请输入你想咨询的问题"
          @input="emit('update:inputValue', $event.target.value)"
        />
        <button :class="['send-button', isTyping ? 'stop-mode' : '']" type="submit">
          {{ isTyping ? "停止" : "发送" }}
        </button>
      </form>
    </footer>
  </div>
</template>

<script setup>
import ChatHistory from "./ChatHistory.vue";
import WelcomePanel from "./WelcomePanel.vue";

defineProps({
  // 父组件传入的聊天历史，格式通常是 [{ role: "user"|"assistant", content: "...", status: "done" }]。
  history: {
    type: Array,
    default: () => [],
  },
  meta: {
    type: Object,
    default: () => ({}),
  },
  showWelcome: {
    type: Boolean,
    default: false,
  },
  inputValue: {
    type: String,
    default: "",
  },
  isTyping: {
    type: Boolean,
    default: false,
  },
  loadingAction: {
    type: String,
    default: "",
  },
  canResume: {
    type: Boolean,
    default: false,
  },
  canRetry: {
    type: Boolean,
    default: false,
  },
  // Agent 执行事件和引用证据目前主要用于面试模式，保留在问答组件中是为了后续扩展。
  agentEvents: { type: Array, default: () => [] },
  currentCitations: { type: Array, default: () => [] },
});

// 这个组件本身不直接请求后端。
// 它更像纯视图层，所有接口请求和状态更新都在 composable 里统一处理。
const emit = defineEmits(["clear-history", "send", "update:inputValue", "stop", "resume-last", "retry-last"]);
</script>
