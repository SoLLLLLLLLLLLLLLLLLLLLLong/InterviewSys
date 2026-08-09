<template>
  <QaPanel
    :history="history"
    :meta="meta"
    :show-welcome="showWelcome"
    :input-value="inputValue"
    :is-typing="isTyping"
    :loading-action="loadingAction"
    :can-resume="canResume"
    :can-retry="canRetry"
    :agent-events="agentEvents"
    :current-citations="currentCitations"
    @clear-history="emit('clear-history')"
    @send="emit('send')"
    @update:inputValue="emit('update:inputValue', $event)"
    @stop="emit('stop')"
    @resume-last="emit('resume-last')"
    @retry-last="emit('retry-last')"
  />
</template>

<script setup>
import QaPanel from "../components/QaPanel.vue";

defineProps({
  history: { type: Array, default: () => [] },
  meta: { type: Object, default: () => ({}) },
  showWelcome: { type: Boolean, default: false },
  inputValue: { type: String, default: "" },
  isTyping: { type: Boolean, default: false },
  loadingAction: { type: String, default: "" },
  canResume: { type: Boolean, default: false },
  canRetry: { type: Boolean, default: false },
  agentEvents: { type: Array, default: () => [] },
  currentCitations: { type: Array, default: () => [] },
});

// View 层本身不写具体业务逻辑，主要承接页面结构和事件透传。
const emit = defineEmits(["clear-history", "send", "update:inputValue", "stop", "resume-last", "retry-last"]);
</script>
