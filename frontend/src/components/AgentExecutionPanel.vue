<template>
  <!-- Agent 执行过程面板：把后端流式返回的 run_started/node_started/tool_called 等事件可视化。 -->
  <aside v-if="events.length" class="agent-execution-panel">
    <button class="agent-execution-heading" type="button" @click="expanded = !expanded">
      <span><i :class="['run-pulse', running ? 'running' : '']"></i>Agent 执行过程</span>
      <small>{{ running ? "执行中" : `${events.length} 个事件` }} · {{ expanded ? "收起" : "展开" }}</small>
    </button>
    <!-- v-for 渲染事件列表；key 用于帮助 Vue 稳定复用 DOM。 -->
    <ol v-show="expanded" class="agent-step-list">
      <li v-for="event in visibleEvents" :key="event.__key || `${event.run_id}-${event.sequence}-${event.type}`">
        <span :class="['agent-step-dot', `event-${event.type}`]"></span>
        <div><strong>{{ nodeLabel(event.node, event.type) }}</strong><p>{{ event.content || event.detail || event.type }}</p></div>
        <time>{{ formatTime(event.timestamp) }}</time>
      </li>
    </ol>
    <!-- 引用证据：RAG 检索到的文档来源，方便回答溯源。 -->
    <div v-if="citations.length" v-show="expanded" class="citation-strip">
      <strong>本轮引用</strong>
      <span v-for="item in citations" :key="item.id || item.chunk_id">{{ item.source }} · {{ item.id || item.chunk_id }}</span>
    </div>
  </aside>
</template>

<script setup>
import { computed, ref } from "vue";

const props = defineProps({ events: { type: Array, default: () => [] }, running: { type: Boolean, default: false }, citations: { type: Array, default: () => [] } });

// expanded 是本组件自己的 UI 状态，只控制面板展开/收起。
const expanded = ref(true);

// token 事件很多，全部展示会刷屏，所以这里只展示非 token 的最近 12 个关键事件。
const visibleEvents = computed(() => props.events.filter((event) => event.type !== "token").slice(-12));

// 后端传的是节点英文名，前端用映射表转成更适合用户看的中文。
const labels = { workflow: "工作流", router: "Router Agent", resume_analyst: "Resume Analyst", planner: "Interview Planner", knowledge_retrieval: "知识库检索", evidence_judge: "Evidence Judge", evaluation_agent: "Evaluation Agent", state_machine: "面试状态机", interview_agent: "Interview Agent", report_agent: "Report Agent" };

function nodeLabel(node, type) { return labels[node] || ({ run_started: "任务启动", run_finished: "任务完成", run_error: "任务失败" }[type] || node || type); }

// 时间格式化只负责展示，不改变后端原始时间数据。
function formatTime(value) { return value ? new Date(value).toLocaleTimeString("zh-CN", { hour12: false }) : ""; }
</script>
