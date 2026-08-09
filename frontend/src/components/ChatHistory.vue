<template>
  <div ref="historyShellRef" class="chat-history-shell" @scroll="handleScroll">
    <div class="chat-history">
      <button v-if="hasMoreMessages" class="text-button load-more-button" @click="showMoreMessages">加载更早消息</button>

      <!--
        v-for 渲染聊天列表时必须提供 key。
        key 的作用是帮助 Vue 在 diff 时识别每条消息，避免 DOM 复用错乱。
        这里没有稳定 message.id，所以用“全局下标 + role + 内容片段”做近似 key。
      -->
      <div
        v-for="(message, index) in visibleMessages"
        :key="`${startIndex + index}-${message.role}-${String(message.content || '').slice(0, 12)}`"
        :class="['chat-row', message.role === 'user' ? 'user' : 'assistant']"
      >
        <div class="avatar">{{ message.role === "user" ? "🧑" : "🤖" }}</div>
        <div class="bubble">
          <div class="bubble-content">{{ message.content }}</div>
          <div v-if="message.status === 'interrupted'" class="bubble-status interrupted">已中断，可继续生成或重试</div>
          <div v-else-if="message.status === 'generating'" class="bubble-status">生成中...</div>
          <div
            v-if="message.role === 'assistant' && startIndex + index === messages.length - 1 && (canResume || canRetry)"
            class="bubble-action-row"
          >
            <button v-if="canResume" class="bubble-action-icon" title="继续生成" @click="emit('resume-last')">↻</button>
            <button v-if="canRetry" class="bubble-action-icon" title="重试本轮回答" @click="emit('retry-last')">⟳</button>
          </div>
        </div>
      </div>

      <div ref="bottomAnchorRef" class="history-bottom-anchor"></div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { debounce, throttle } from "../utils/timing.js";

const props = defineProps({
  // 父组件传完整消息数组进来，当前组件自己决定先展示多少条。
  messages: {
    type: Array,
    default: () => [],
  },
  canResume: {
    type: Boolean,
    default: false,
  },
  canRetry: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["resume-last", "retry-last"]);

// 这是一个很适合学习 Vue 3 基础的组件：
// - ref：局部响应式状态
// - computed：派生状态
// - watch：监听状态变化
// - onMounted/onBeforeUnmount：生命周期
// 长列表优化：
// 不一次性渲染所有历史消息，先展示最近 80 条，需要时再加载更早消息。
// 如果以后消息量更大，可以进一步替换为真正的虚拟列表。
const INITIAL_VISIBLE_COUNT = 80;
const LOAD_MORE_STEP = 60;
const AUTO_SCROLL_THRESHOLD = 120;

const historyShellRef = ref(null);
const bottomAnchorRef = ref(null);
const visibleCount = ref(INITIAL_VISIBLE_COUNT);
const shouldStickToBottom = ref(true);

const visibleMessages = computed(() => props.messages.slice(-visibleCount.value));
const hasMoreMessages = computed(() => props.messages.length > visibleCount.value);
const startIndex = computed(() => Math.max(0, props.messages.length - visibleCount.value));

function updateStickState() {
  const shell = historyShellRef.value;
  if (!shell) return;
  const distanceToBottom = shell.scrollHeight - shell.scrollTop - shell.clientHeight;
  shouldStickToBottom.value = distanceToBottom <= AUTO_SCROLL_THRESHOLD;
}

// throttle：高频触发时限制执行频率，适合 scroll / resize 这类事件。
const throttledScroll = throttle(updateStickState, 100);

// debounce：等连续触发停下来后再执行，适合输入框、窗口变化等场景。
const debouncedResize = debounce(() => {
  if (shouldStickToBottom.value) {
    scrollToBottom("auto");
  }
}, 120);

function handleScroll() {
  throttledScroll();
}

function showMoreMessages() {
  visibleCount.value += LOAD_MORE_STEP;
}

function scrollToBottom(behavior = "smooth") {
  // nextTick：等 DOM 更新完再滚动，否则锚点可能还没渲染出来。
  nextTick(() => {
    bottomAnchorRef.value?.scrollIntoView({ behavior, block: "end" });
  });
}

watch(
  () => props.messages.length,
  (nextLength, previousLength) => {
    if (nextLength <= previousLength) return;
    if (shouldStickToBottom.value) {
      scrollToBottom(previousLength === 0 ? "auto" : "smooth");
    }
  },
);

watch(
  () => props.messages,
  () => {
    if (props.messages.length <= INITIAL_VISIBLE_COUNT) {
      visibleCount.value = INITIAL_VISIBLE_COUNT;
    }
  },
  { deep: true },
);

onMounted(() => {
  scrollToBottom("auto");
  window.addEventListener("resize", debouncedResize);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", debouncedResize);
});
</script>
