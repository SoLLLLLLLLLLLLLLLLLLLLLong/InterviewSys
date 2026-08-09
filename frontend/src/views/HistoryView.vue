<template>
  <HistoryPanel
    :records="records"
    :selected-record="selectedRecord"
    :loading-action="loadingAction"
    @refresh-history="emit('refresh-history')"
    @open-record="emit('open-record', $event)"
    @restore-record="emit('restore-record', $event)"
  />
</template>

<script setup>
import HistoryPanel from "../components/HistoryPanel.vue";

defineProps({
  records: { type: Array, default: () => [] },
  selectedRecord: { type: Object, default: null },
  loadingAction: { type: String, default: "" },
});

// 当前 view 自己不写业务逻辑，主要负责把事件继续往上透传。
const emit = defineEmits(["refresh-history", "open-record", "restore-record"]);
</script>
