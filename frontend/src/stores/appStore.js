import { defineStore } from "pinia";
import {
  DEFAULT_AUTH,
  DEFAULT_HISTORY_DETAIL,
  DEFAULT_LANGSMITH,
  DEFAULT_LOGIN_FORM,
  DEFAULT_META,
  DEFAULT_REGISTER_FORM,
  DEFAULT_WEATHER,
  DEFAULT_WORKSPACE,
  MESSAGE_STATUS,
  MODES,
  THEME_MODES,
} from "../constants/app.js";
import { cloneValue } from "../utils/clone.js";

export const useAppStore = defineStore("app", {
  // Pinia store 负责统一存前端全局状态。
  //
  // 你可以把这里理解成“页面内存里的总仓库”：
  // - state：原始状态
  // - getters：派生状态，思想上类似 computed
  // - actions：更新状态的方法
  state: () => ({
    // bootstrapping 表示首屏初始化是否完成。
    // App.vue 会根据这个状态决定展示骨架屏、登录页还是工作台。
    bootstrapping: true,

    // 登录状态。
    auth: { ...DEFAULT_AUTH },

    // 当前会话完整状态。
    // 问答历史、面试历史、简历、分数、报告等都放这里。
    candidate: null,

    // weather：右上角天气卡片数据。
    // meta：后端下发的页面文案、岗位选项等配置。
    // 这类数据放在后端返回，可以避免前端写死业务文案和岗位配置。
    weather: { ...DEFAULT_WEATHER },
    meta: { ...DEFAULT_META },

    langsmith: { ...DEFAULT_LANGSMITH },
    langsmithStatus: "",

    // 历史记录和工作区是“产品化”的核心状态：
    // - historyRecords：历史面试报告列表。
    // - workspace：项目空间、会话列表、当前激活项目和会话。
    historyRecords: [],
    selectedHistoryRecord: DEFAULT_HISTORY_DETAIL,
    workspace: { ...DEFAULT_WORKSPACE },

    authMode: "login",
    loginForm: { ...DEFAULT_LOGIN_FORM },
    registerForm: { ...DEFAULT_REGISTER_FORM },

    // mode 控制工作台当前展示哪个业务模块。
    // Vue Router 负责 URL，mode 负责页面内部真正展示问答/面试/历史。
    mode: MODES.QA,
    selectedRole: "通用技术岗位",
    knowledgeFiles: [],
    resumeFile: null,
    qaInput: "",
    interviewInput: "",
    // loadingAction 用字符串标识当前正在执行的动作。
    // 好处：页面可以根据不同动作展示不同按钮 loading，而不是只有一个 boolean。
    loadingAction: "",
    // progressMessage 用于更细的加载反馈，例如“正在分析简历”“正在生成报告”。
    progressMessage: "",

    // typingState 用来记录当前是否处于流式回复中，
    // 以及这条流式请求的 AbortController。
    typingState: null,
    stopRequested: false,
    errorMessage: "",
    // 当前一次流式/Agent 执行的运行信息。
    // currentRunId 对应后端 Redis/RunStore 里的 run_id；
    // agentEvents 用于前端实时展示 Router/Evaluation/Tool 等节点事件；
    // currentCitations 用于展示 RAG 引用证据。
    currentRunId: "",
    agentEvents: [],
    currentCitations: [],

    // 主题模式保存到 localStorage，页面刷新后还能记住。
    themeMode:
      (typeof window !== "undefined" && window.localStorage.getItem("interview-theme-mode")) || THEME_MODES.SERIOUS,
  }),
  getters: {
    // getters 可以理解成基于 state 推导出来的“好用结果”。
    isTyping: (state) => Boolean(state.typingState),

    activeModeMeta(state) {
      if (state.mode === MODES.QA) {
        return state.meta.qa;
      }
      if (state.mode === MODES.INTERVIEW) {
        return state.meta.interview;
      }
      return state.meta.history;
    },

    // 统一抽象出“当前聊天历史”，让展示组件少关心业务分支。
    currentHistory(state) {
      if (state.mode === MODES.QA) {
        return state.candidate?.qa_history || [];
      }
      if (state.mode === MODES.INTERVIEW) {
        return state.candidate?.interview_history || [];
      }
      return [];
    },

    showQaWelcome(state) {
      return state.mode === MODES.QA && (state.candidate?.qa_history || []).length === 0;
    },

    showInterviewWelcome(state) {
      return (
        state.mode === MODES.INTERVIEW &&
        (state.candidate?.interview_history || []).length === 0 &&
        !state.candidate?.interview_started
      );
    },

    activeProject(state) {
      return (state.workspace.projects || []).find((item) => item.id === state.workspace.active_project_id) || null;
    },

    activeConversation() {
      // 注意这里使用 function/getter 形式而不是箭头函数，
      // 因为需要通过 this 访问另一个 getter activeProject。
      return this.activeProject?.conversations?.find((item) => item.id === this.workspace.active_conversation_id) || null;
    },

    canResumeCurrentReply() {
      // “继续生成”的判断依据：最后一条消息是被中断的 assistant 消息。
      const history = this.currentHistory;
      return Boolean(history.length && history[history.length - 1]?.status === MESSAGE_STATUS.INTERRUPTED);
    },

    canRetryCurrentReply() {
      // “重试”需要满足：历史里有用户消息，并且最后一条 assistant 不是生成中。
      const history = this.currentHistory;
      if (!history.length) {
        return false;
      }
      const lastAssistant = history[history.length - 1];
      const hasLastUser = [...history].reverse().some((item) => item.role === "user");
      return Boolean(hasLastUser && lastAssistant?.role === "assistant" && lastAssistant.status !== MESSAGE_STATUS.GENERATING);
    },
  },
  actions: {
    // 统一的同步写状态方法。
    // 好处是页面层不直接乱改深层对象，后面排查和扩展会更清晰。
    setLoadingAction(action) {
      this.loadingAction = action;
    },
    setErrorMessage(message) {
      this.errorMessage = message;
    },
    setProgressMessage(message) {
      this.progressMessage = message;
    },
    setWorkspace(payload) {
      this.workspace = payload || { ...DEFAULT_WORKSPACE };
    },
    setMode(mode) {
      this.mode = mode;
    },
    setAuthMode(mode) {
      this.authMode = mode;
    },
    setLoginForm(payload) {
      this.loginForm = payload;
    },
    setRegisterForm(payload) {
      this.registerForm = payload;
    },
    setSelectedRole(role) {
      this.selectedRole = role;
    },
    setRoleOptions(roleOptions) {
      const nextOptions = Array.isArray(roleOptions) ? roleOptions.filter(Boolean) : [];
      this.meta = {
        ...this.meta,
        role_options: nextOptions,
      };
      if (nextOptions.length && !nextOptions.includes(this.selectedRole)) {
        this.selectedRole = nextOptions[0];
      }
    },
    setKnowledgeFiles(files) {
      this.knowledgeFiles = files;
    },
    setResumeFile(file) {
      this.resumeFile = file;
    },
    setQaInput(value) {
      this.qaInput = value;
    },
    setInterviewInput(value) {
      this.interviewInput = value;
    },
    setLangsmith(payload) {
      this.langsmith = payload;
    },
    setSelectedHistoryRecord(record) {
      this.selectedHistoryRecord = record;
    },
    setTypingState(payload) {
      this.typingState = payload;
    },
    setStopRequested(value) {
      this.stopRequested = value;
    },
    beginAgentRun(runId) {
      this.currentRunId = runId || "";
      this.agentEvents = [];
      this.currentCitations = [];
    },
    recordAgentEvent(event) {
      // 后端流式事件可能因为恢复/重连被重复发送。
      // 这里根据 run_id + sequence + type + node 做一个轻量去重。
      if (!event?.type) return;
      if (event.run_id && this.currentRunId && event.run_id !== this.currentRunId) return;
      if (event.run_id && !this.currentRunId) this.currentRunId = event.run_id;
      const key = `${event.run_id || ""}:${event.sequence || ""}:${event.type}:${event.node || ""}`;
      if (!this.agentEvents.some((item) => item.__key === key)) {
        this.agentEvents = [...this.agentEvents, { ...event, __key: key }].slice(-100);
      }
    },
    setCurrentCitations(citations) {
      this.currentCitations = Array.isArray(citations) ? citations : [];
    },
    setThemeMode(mode) {
      this.themeMode = mode;
      if (typeof window !== "undefined") {
        // 主题模式属于纯前端偏好，适合存在 localStorage。
        // 注意：这和登录 token 不一样，token 不应该放 localStorage。
        window.localStorage.setItem("interview-theme-mode", mode);
      }
    },

    // bootstrap 完成后，后端会返回一大包初始化数据。
    // 这里统一把它灌进前端 store。
    applyBootstrapPayload(data) {
      /*
       * /api/bootstrap 的作用：
       * ---------------------------------------------------------------------
       * 首屏只请求一次，就拿到登录态、当前会话、工作区、天气、页面配置等。
       * 这比前端进入页面后同时打很多接口更稳定，也更容易做错误兜底。
       */
      this.auth = data.auth || { ...DEFAULT_AUTH };
      this.candidate = data.candidate || null;
      this.weather = data.weather || { ...DEFAULT_WEATHER };
      this.meta = data.meta || { ...DEFAULT_META };
      this.langsmith = {
        enabled: Boolean(data.langsmith?.enabled),
        api_key: data.langsmith?.api_key || "",
        project: data.langsmith?.project || "interview-coach-debug",
      };
      this.langsmithStatus = data.langsmith?.enabled
        ? `LangSmith 调试已开启，当前项目：${data.langsmith.project || "interview-coach-debug"}`
        : "LangSmith 调试当前未开启。";
      this.historyRecords = data.history_records || [];
      this.workspace = data.workspace || { ...DEFAULT_WORKSPACE };
      this.selectedRole = data.candidate?.interview_state?.target_role || data.meta?.role_options?.[0] || "通用技术岗位";
      if (!this.auth.authenticated) {
        this.mode = MODES.QA;
      } else if (data.candidate?.conversation_preferred_mode) {
        this.mode = data.candidate.conversation_preferred_mode;
      }
    },

    resetAfterLogout() {
      // 退出登录后要清空用户相关状态，避免 A 用户数据残留到 B 用户页面。
      this.auth = { ...DEFAULT_AUTH };
      this.candidate = null;
      this.historyRecords = [];
      this.selectedHistoryRecord = DEFAULT_HISTORY_DETAIL;
      this.workspace = { ...DEFAULT_WORKSPACE };
      this.mode = MODES.QA;
      this.loginForm = { ...DEFAULT_LOGIN_FORM };
      this.registerForm = { ...DEFAULT_REGISTER_FORM };
      this.errorMessage = "";
      this.progressMessage = "";
      this.loadingAction = "";
      this.typingState = null;
      this.stopRequested = false;
      this.currentRunId = "";
      this.agentEvents = [];
      this.currentCitations = [];
    },

    resetLoginForm() {
      this.loginForm = { ...DEFAULT_LOGIN_FORM };
    },

    resetRegisterForm() {
      this.registerForm = { ...DEFAULT_REGISTER_FORM };
    },

    // 流式渲染时，前端会不断改写最后一条 assistant 消息。
    updateHistoryMessage(historyKey, messageIndex, content, status) {
      /*
       * 为什么这里要 clone 后再赋值？
       * ---------------------------------------------------------------------
       * candidate 是一个较深的对象，里面包含 qa_history/interview_history。
       * clone 后整体替换 candidate，可以确保 Vue/Pinia 更稳定地感知变化。
       */
      if (!this.candidate) {
        return;
      }
      const nextCandidate = cloneValue(this.candidate);
      const history = nextCandidate[historyKey];
      if (!history?.[messageIndex]) {
        return;
      }
      history[messageIndex].content = content;
      history[messageIndex].status = status;
      this.candidate = nextCandidate;
    },
  },
});
