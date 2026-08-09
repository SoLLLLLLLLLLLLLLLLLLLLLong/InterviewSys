<template>
  <section class="interview-page-shell">
    <section v-if="showSetupPanel" class="interview-setup-shell">
      <div class="interview-setup-card">
        <div class="interview-setup-copy">
          <span class="setup-eyebrow">模拟面试配置</span>
          <h2>先确定本轮面试设置</h2>
          <p>先选岗位，可选上传简历，再选择主题模式。点击开始后，页面会切换成专注的面试工作台。</p>
        </div>

        <div class="config-grid">
          <div class="config-item">
            <label>目标岗位</label>
            <select class="text-input" :value="selectedRole" @change="emit('update:selectedRole', $event.target.value)">
              <option v-for="role in roleOptions" :key="role" :value="role">{{ role }}</option>
            </select>
          </div>

          <div class="config-item">
            <label>上传简历（可选）</label>
            <input
              class="file-input"
              type="file"
              accept=".pdf,.docx,.txt,.md"
              @change="emit('resume-file-change', $event.target.files?.[0] || null)"
            />
            <div class="config-file-meta">
              <span v-if="resumeFile">待上传：{{ resumeFile.name }}</span>
              <span v-else-if="candidate && candidate.resume_filename">当前简历：{{ candidate.resume_filename }}</span>
              <span v-else>未选择简历，本轮将按岗位通用能力进行面试。</span>
            </div>
            <div v-if="candidate && candidate.resume_filename" class="config-actions">
              <button class="text-button" :disabled="loadingAction === 'resume-clear'" @click="emit('clear-resume')">清除当前简历</button>
            </div>
          </div>
        </div>

        <div class="config-item interview-theme-picker">
          <label>主题模式</label>
          <div class="theme-mode-list interview-theme-list">
            <button
              v-for="item in themeCards"
              :key="item.value"
              :class="['theme-mode-card', themeMode === item.value ? 'active' : '']"
              :data-theme="item.value"
              @click="emit('update:themeMode', item.value)"
            >
              <strong>{{ item.title }}</strong>
              <span>{{ item.subtitle }}</span>
            </button>
          </div>
        </div>

        <label class="digital-toggle-card">
          <input v-model="digitalEnabled" type="checkbox" />
          <span>
            <strong>开启数字面试官</strong>
            <small>支持面试官形象、语音播报和语音输入。</small>
          </span>
        </label>

        <div class="setup-info-banner">
          {{
            candidate && candidate.resume_filename
              ? "检测到当前会话已有简历，开始后会优先结合简历经历和岗位要求提问。"
              : "如果不上传简历，系统会按岗位通用能力推进本轮面试。"
          }}
        </div>

        <div class="interview-setup-actions">
          <button
            class="primary-button interview-start-button"
            :disabled="loadingAction === 'interview-start' || loadingAction === 'resume' || isTyping"
            @click="handleStartInterview"
          >
            {{ hasInterviewSession ? "开始 / 重置面试" : "开始本轮面试" }}
          </button>
          <button class="ghost-button" @click="handleCancelSetup">
            {{ hasInterviewSession ? "返回当前面试" : "取消" }}
          </button>
        </div>
      </div>
    </section>

    <template v-else>
      <section class="interview-session-bar">
        <div class="interview-session-meta">
          <span class="session-chip role">岗位：{{ currentRoleLabel }}</span>
          <span class="session-chip resume">{{ hasResume ? "简历：已上传" : "简历：未上传" }}</span>
          <span v-if="interviewPlan.length" class="session-chip plan">计划：{{ interviewPlan.length }} 个维度</span>
          <span v-if="configuredQuestionCount" class="session-chip plan">题量：{{ configuredQuestionCount }} 题</span>
          <span v-if="candidate && candidate.interview_score" class="session-chip score">得分：{{ candidate.interview_score }} / 100</span>
        </div>

        <div class="interview-session-actions">
          <label class="digital-session-toggle">
            <input v-model="digitalEnabled" type="checkbox" />
            <span>数字面试官</span>
          </label>
          <button class="text-button" @click="showSetupPanel = true">重新配置</button>
          <button
            v-if="candidate && !candidate.interview_finished"
            class="ghost-button interview-end-button"
            :disabled="loadingAction === 'interview-end'"
            @click="emit('end-interview')"
          >
            {{ loadingAction === "interview-end" ? "结束中..." : "结束本次面试" }}
          </button>
        </div>
      </section>

      <section class="interview-stage-shell">
        <AgentExecutionPanel :events="agentEvents" :running="isTyping" :citations="currentCitations" />
        <section v-if="interviewPlan.length" class="interview-plan-strip">
          <span>本轮面试计划</span>
          <div>
            <i v-for="item in interviewPlan" :key="item.name || item.focus">{{ item.name || item.focus }}</i>
          </div>
        </section>
        <div :class="['interview-live-layout', digitalEnabled ? 'with-digital' : '']">
          <div class="interview-chat-stage">
            <WelcomePanel v-if="showWelcome" :title="meta.empty_title || '欢迎开始模拟面试'" :lines="meta.empty_description || []" />
            <template v-else>
              <!--
                数字面试官开启后，AI 的文字回复不再用普通 assistant 气泡展示，
                而是由 DigitalInterviewer 占据原本“AI 左侧回复区”的位置。
                用户气泡仍然保留，这样面试记录的问答关系不会丢。
              -->
              <DigitalInterviewer
                v-if="digitalEnabled"
                v-model:enabled="digitalEnabled"
                class="digital-interviewer-row"
                :speaking="isTyping"
                :latest-text="latestAssistantText"
                :agent-events="agentEvents"
                :interview-plan="interviewPlan"
                @voice-input="handleVoiceInput"
              />
              <ChatHistory
                :messages="displayHistory"
                :can-resume="canResume"
                :can-retry="canRetry"
                @resume-last="emit('resume-last')"
                @retry-last="emit('retry-last')"
              />
            </template>
          </div>
        </div>

        <div v-if="candidate && candidate.interview_finished" class="interview-report-stage">
          <section class="report-panel">
            <div class="score-card">本次模拟面试得分：{{ candidate.interview_score }} / 100</div>
            <div class="report-action-row">
              <div class="report-action-left">
                <button class="primary-button report-button" :disabled="loadingAction === 'report'" @click="emit('generate-report')">
                  {{ loadingAction === "report" ? "生成中..." : "生成面试报告" }}
                </button>
                <button
                  v-if="candidate.interview_report"
                  class="ghost-button report-view-button"
                  type="button"
                  @click="showReportDialog = true"
                >
                  查看面试报告
                </button>
              </div>
              <a
                v-if="candidate.interview_report_file"
                class="text-button report-download-link"
                href="/api/interview/report/download"
                download
              >
                下载最新报告
              </a>
            </div>
            <div v-if="candidate.interview_report_file" class="report-file-meta">
              <div>报告文件：{{ candidate.interview_report_file }}</div>
            </div>
          </section>
        </div>

        <footer v-else class="chat-input-shell interview-input-shell">
          <form class="chat-form" @submit.prevent="isTyping ? emit('stop') : emit('send')">
            <input
              :value="inputValue"
              class="chat-input"
              :disabled="!candidate || !candidate.interview_started || isTyping"
              placeholder="请输入你的回答"
              @input="emit('update:inputValue', $event.target.value)"
            />
            <button
              :class="['send-button', isTyping ? 'stop-mode' : '']"
              type="submit"
              :disabled="!candidate || !candidate.interview_started"
            >
              {{ isTyping ? "停止" : "发送" }}
            </button>
          </form>
        </footer>
      </section>
    </template>

    <div v-if="showReportDialog" class="report-dialog-backdrop" @click.self="showReportDialog = false">
      <section class="report-dialog">
        <header class="report-dialog-header">
          <a class="primary-button report-download-dialog-button" href="/api/interview/report/download" download>下载面试报告</a>
          <button class="sidebar-icon-button" type="button" title="关闭" @click="showReportDialog = false">×</button>
        </header>
        <article class="report-dialog-content">{{ candidate?.interview_report }}</article>
      </section>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { THEME_LABELS, THEME_MODES } from "../constants/app.js";
import ChatHistory from "./ChatHistory.vue";
import WelcomePanel from "./WelcomePanel.vue";
import AgentExecutionPanel from "./AgentExecutionPanel.vue";
import DigitalInterviewer from "./DigitalInterviewer.vue";

const props = defineProps({
  candidate: { type: Object, default: null },
  roleOptions: { type: Array, default: () => [] },
  selectedRole: { type: String, default: "" },
  themeMode: { type: String, default: THEME_MODES.SERIOUS },
  resumeFile: { type: [Object, null], default: null },
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

const emit = defineEmits([
  "update:selectedRole",
  "update:themeMode",
  "resume-file-change",
  "clear-resume",
  "start-interview",
  "end-interview",
  "generate-report",
  "cancel-setup",
  "send",
  "update:inputValue",
  "stop",
  "resume-last",
  "retry-last",
]);

// 纯页面展示状态和后端业务状态要分开理解。
// showSetupPanel 只是 UI 状态，不等于真正的 interview_state。
const showSetupPanel = ref(!(props.candidate && props.candidate.interview_started));
const showReportDialog = ref(false);
const digitalEnabled = ref(false);

const hasInterviewSession = computed(() => Boolean(props.candidate && props.candidate.interview_started));
const hasResume = computed(() => Boolean(props.resumeFile || props.candidate?.resume_filename || props.candidate?.resume_text));
const currentRoleLabel = computed(() => props.candidate?.interview_state?.target_role || props.selectedRole || "未设置岗位");
const interviewPlan = computed(() => props.candidate?.interview_state?.multi_agent?.interview_plan || []);
const configuredQuestionCount = computed(() => Number(props.candidate?.interview_state?.configured_question_count || 0));
const themeCards = computed(() => [
  { value: THEME_MODES.SERIOUS, ...THEME_LABELS[THEME_MODES.SERIOUS] },
  { value: THEME_MODES.LIGHT, ...THEME_LABELS[THEME_MODES.LIGHT] },
  { value: THEME_MODES.SPRINT, ...THEME_LABELS[THEME_MODES.SPRINT] },
]);
const latestAssistantText = computed(() => {
  const latest = [...props.history].reverse().find((message) => message.role === "assistant" && message.content);
  return String(latest?.content || "");
});
const displayHistory = computed(() => {
  if (!digitalEnabled.value) {
    return props.history;
  }
  // 数字人模式下隐藏 assistant 气泡，避免“数字人 + AI 文本气泡”重复出现。
  return props.history.filter((message) => message.role !== "assistant");
});

// watch 适合做“状态变化 -> 触发副作用”的逻辑。
watch(
  () => props.candidate?.interview_started,
  (nextValue) => {
    showSetupPanel.value = !nextValue;
  },
  { immediate: true },
);

watch(
  () => props.candidate?.interview_report,
  (reportText) => {
    if (!reportText) {
      showReportDialog.value = false;
    }
  },
);

function handleCancelSetup() {
  if (hasInterviewSession.value) {
    showSetupPanel.value = false;
    return;
  }
  emit("cancel-setup");
}

function handleStartInterview() {
  // 点击开始后先切到面试工作台，避免后端已经创建面试但 UI 还停留在配置面板。
  // 后续真正的面试状态仍然以后端 /api/interview/start 返回的 candidate 为准。
  showSetupPanel.value = false;
  emit("start-interview");
}

function handleVoiceInput(transcript) {
  emit("update:inputValue", transcript);
}
</script>
