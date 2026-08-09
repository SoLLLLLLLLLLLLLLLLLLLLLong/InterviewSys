import { onBeforeUnmount } from "vue";
import { storeToRefs } from "pinia";
import { apiDelete, apiFormPost, apiGet, apiPatch, apiPost, apiStreamPost } from "../api/client.js";
import {
  ERROR_MESSAGES,
  LOADING_ACTIONS,
  MESSAGE_STATUS,
  MODES,
  STREAM_ACTIONS,
  UI_TEXT,
} from "../constants/app.js";
import { useAppStore } from "../stores/appStore.js";
import { cloneValue } from "../utils/clone.js";
import { debounce } from "../utils/timing.js";

export function useInterviewApp() {
  // 这是前端最核心的业务编排层。
  //
  // 你可以把它理解成：
  // - store 负责“存状态”
  // - api/client 负责“发请求”
  // - 当前这个 composable 负责“把页面动作串成完整业务流程”
  //
  // 例如“发送一条问答消息”，不是简单调一个接口，而是：
  // 1. 读取输入框
  // 2. 做乐观更新
  // 3. 发起流式请求
  // 4. 持续更新消息
  // 5. 处理停止、重试、报错
  const appStore = useAppStore();
  const {
    bootstrapping,
    auth,
    candidate,
    weather,
    meta,
    langsmith,
    langsmithStatus,
    historyRecords,
    selectedHistoryRecord,
    workspace,
    authMode,
    loginForm,
    registerForm,
    mode,
    selectedRole,
    knowledgeFiles,
    resumeFile,
    qaInput,
    interviewInput,
    loadingAction,
    progressMessage,
    typingState,
    stopRequested,
    errorMessage,
    themeMode,
    isTyping,
    activeModeMeta,
    currentHistory,
    showQaWelcome,
    showInterviewWelcome,
    activeProject,
    activeConversation,
    canResumeCurrentReply,
    canRetryCurrentReply,
    currentRunId,
  } = storeToRefs(appStore);

  // 历史记录列表切换时不需要每次都立刻请求，先做一次轻量防抖。
  const debouncedHistoryLoader = debounce(() => {
    loadHistoryRecordsImmediate();
  }, 260);

  onBeforeUnmount(() => {
    // 页面销毁前，如果还在流式回复，就主动中断。
    typingState.value?.controller?.abort();
  });

  async function bootstrap() {
    /*
     * 首屏初始化入口：
     * -----------------------------------------------------------------------
     * 前端页面刚打开时，并不知道用户是否登录、当前会话是谁、岗位选项有哪些。
     * 所以先调用 /api/bootstrap，让后端一次性返回首屏需要的大部分状态。
     *
     * 前端拿到数据后调用 applyBootstrapPayload 写入 Pinia，
     * 页面会基于 Pinia 状态自动切换到登录页、工作台或后台。
     */
    bootstrapping.value = true;
    appStore.setErrorMessage("");
    try {
      // 前后端同时启动时，FastAPI 可能仍在加载 Python 依赖。
      // 首屏对网络错误做有限重试，避免只因后端慢几秒就直接显示失败页。
      let data = null;
      let lastError = null;
      for (let attempt = 0; attempt < 15; attempt += 1) {
        try {
          data = await apiGet("/api/bootstrap");
          break;
        } catch (error) {
          lastError = error;
          await new Promise((resolve) => setTimeout(resolve, 1000));
        }
      }
      if (!data) {
        throw lastError || new Error("后端服务尚未启动。");
      }
      appStore.applyBootstrapPayload(data);
      await refreshRoleOptions({ silent: true });
      const pendingRunId = data.candidate?.pending_run_id;
      if (pendingRunId) {
        // 如果上一次面试流式生成时用户断线/刷新，
        // 后端可能已经凭 run_id 在 Redis/RunStore 中保存了最终结果。
        // 这里尝试恢复，避免一刷新就丢失模型回答。
        const recovered = await recoverCompletedInterviewRun(pendingRunId);
        if (recovered?.candidate) {
          candidate.value = recovered.candidate;
          appStore.setCurrentCitations(recovered.evidence || []);
        }
      }
    } catch (error) {
      appStore.setErrorMessage(normalizeErrorMessage(error, ERROR_MESSAGES.BOOTSTRAP));
    } finally {
      bootstrapping.value = false;
    }
  }

  async function refreshBootstrapData() {
    try {
      const data = await apiGet("/api/bootstrap");
      appStore.applyBootstrapPayload(data);
      return data;
    } catch (error) {
      appStore.setErrorMessage(normalizeErrorMessage(error, ERROR_MESSAGES.BOOTSTRAP));
      return null;
    }
  }

  async function refreshRoleOptions(options = {}) {
    const silent = Boolean(options.silent);
    try {
      const data = await apiGet("/api/roles");
      appStore.setRoleOptions(data.role_options || []);
      return data.role_options || [];
    } catch (error) {
      if (!silent) {
        appStore.setErrorMessage(normalizeErrorMessage(error, "刷新岗位配置失败。"));
      }
      return meta.value.role_options || [];
    }
  }

  function syncAppPayload(data, options = {}) {
    // 后端很多接口都会返回“最新的全局状态”。
    // 所以前端通常不是只改一个字段，而是把整包 payload 再同步回 store。
    appStore.applyBootstrapPayload(data);
    if (options.mode) {
      appStore.setMode(options.mode);
    }
  }

  async function login() {
    // 登录成功后，后端通过 Set-Cookie 写入 HttpOnly Session Cookie。
    // 前端不保存 token，只同步后端返回的用户和工作区状态。
    appStore.setLoadingAction(LOADING_ACTIONS.LOGIN);
    appStore.setErrorMessage("");
    try {
      const data = await apiPost("/api/auth/login", loginForm.value);
      syncAppPayload(data);
      await refreshRoleOptions({ silent: true });
      appStore.setMode(MODES.QA);
      appStore.resetLoginForm();
    } catch (error) {
      appStore.setErrorMessage(normalizeErrorMessage(error, ERROR_MESSAGES.LOGIN));
    } finally {
      appStore.setLoadingAction("");
    }
  }

  async function register() {
    // 注册后直接进入登录态：后端创建用户、创建 session、返回首屏 payload。
    appStore.setLoadingAction(LOADING_ACTIONS.REGISTER);
    appStore.setErrorMessage("");
    try {
      const data = await apiPost("/api/auth/register", registerForm.value);
      syncAppPayload(data);
      await refreshRoleOptions({ silent: true });
      appStore.setMode(MODES.QA);
      appStore.resetRegisterForm();
    } catch (error) {
      appStore.setErrorMessage(normalizeErrorMessage(error, ERROR_MESSAGES.REGISTER));
    } finally {
      appStore.setLoadingAction("");
    }
  }

  async function logout() {
    // 退出登录需要两步：
    // 1. 后端删除 session 并清 Cookie
    // 2. 前端清空 Pinia 中的用户、会话和历史状态
    appStore.setLoadingAction(LOADING_ACTIONS.LOGOUT);
    appStore.setErrorMessage("");
    try {
      await apiPost("/api/auth/logout", {});
      appStore.resetAfterLogout();
    } catch (error) {
      appStore.setErrorMessage(normalizeErrorMessage(error, ERROR_MESSAGES.LOGOUT));
    } finally {
      appStore.setLoadingAction("");
    }
  }

  async function importKnowledge() {
    // 典型文件上传链路：File[] -> FormData -> POST -> 后端解析入库
    appStore.setLoadingAction(LOADING_ACTIONS.KNOWLEDGE);
    appStore.setErrorMessage("");
    try {
      const formData = new FormData();
      knowledgeFiles.value.forEach((file) => formData.append("files", file));
      const result = await apiFormPost("/api/knowledge/import", formData);
      const namesText = result.names?.length ? `（${result.names.join("、")}）` : "";
      window.alert(result.message || `已导入 ${result.count || 0} 个文档${namesText}`);
      appStore.setKnowledgeFiles([]);
    } catch (error) {
      appStore.setErrorMessage(normalizeErrorMessage(error, ERROR_MESSAGES.KNOWLEDGE_IMPORT));
    } finally {
      appStore.setLoadingAction("");
    }
  }

  async function saveLangSmith() {
    appStore.setLoadingAction(LOADING_ACTIONS.LANGSMITH);
    appStore.setErrorMessage("");
    try {
      const result = await apiPost("/api/langsmith/config", langsmith.value);
      appStore.setLangsmith({
        ...langsmith.value,
        enabled: result.enabled,
        project: result.project,
      });
      langsmithStatus.value = result.status_message;
    } catch (error) {
      appStore.setErrorMessage(normalizeErrorMessage(error, ERROR_MESSAGES.LANGSMITH_SAVE));
    } finally {
      appStore.setLoadingAction("");
    }
  }

  async function uploadResume(options = {}) {
    if (!resumeFile.value || !candidate.value) {
      return;
    }
    appStore.setLoadingAction(LOADING_ACTIONS.RESUME);
    appStore.setProgressMessage("正在分析简历...");
    appStore.setErrorMessage("");
    try {
      const formData = new FormData();
      // 字段名 file 要和 FastAPI 接口参数名保持一致。
      // 后端通过 UploadFile 接收这个文件，再解析简历文本。
      formData.append("file", resumeFile.value);
      const result = await apiFormPost("/api/resume/upload", formData);
      candidate.value = result.candidate;
      appStore.setResumeFile(null);
      return result.candidate;
    } catch (error) {
      if (!options.silent) {
        appStore.setErrorMessage(normalizeErrorMessage(error, ERROR_MESSAGES.RESUME_UPLOAD));
      }
      throw error;
    } finally {
      appStore.setLoadingAction("");
      appStore.setProgressMessage("");
    }
  }

  async function clearResume() {
    if (!candidate.value) {
      return;
    }
    appStore.setLoadingAction(LOADING_ACTIONS.RESUME_CLEAR);
    appStore.setErrorMessage("");
    try {
      const result = await apiPost("/api/resume/clear", {});
      candidate.value = result.candidate;
      appStore.setResumeFile(null);
    } catch (error) {
      appStore.setErrorMessage(normalizeErrorMessage(error, ERROR_MESSAGES.RESUME_CLEAR));
    } finally {
      appStore.setLoadingAction("");
    }
  }

  async function clearQaHistory() {
    if (!candidate.value) {
      return;
    }
    appStore.setLoadingAction(LOADING_ACTIONS.QA_CLEAR);
    appStore.setErrorMessage("");
    try {
      const result = await apiPost("/api/qa/clear", {});
      candidate.value = result.candidate;
    } catch (error) {
      appStore.setErrorMessage(normalizeErrorMessage(error, ERROR_MESSAGES.QA_CLEAR));
    } finally {
      appStore.setLoadingAction("");
    }
  }

  async function ensureCandidateReady() {
    // 页面刷新或切会话后，前端可能已经登录，但当前候选人状态还没同步回来。
    if (candidate.value || !auth.value.authenticated) {
      return candidate.value;
    }
    try {
      const data = await apiPost("/api/candidate/load", {});
      syncAppPayload(data);
      return candidate.value;
    } catch (error) {
      appStore.setErrorMessage(normalizeErrorMessage(error, "初始化当前会话状态失败。"));
      return null;
    }
  }

  async function startInterview() {
    await ensureCandidateReady();
    if (!candidate.value || isTyping.value) {
      return;
    }
    await refreshRoleOptions({ silent: true });
    appStore.setLoadingAction(LOADING_ACTIONS.INTERVIEW_START);
    appStore.setErrorMessage("");
    appStore.setProgressMessage(
      resumeFile.value || candidate.value.resume_text ? "正在分析简历..." : "正在生成首个问题..."
    );
    try {
      // 先在前端乐观清空上一轮结果，避免新一轮首题还没返回时，
      // 页面继续展示上一轮的得分、报告和“已结束”状态。
      const optimistic = cloneValue(candidate.value);
      optimistic.interview_history = [];
      optimistic.interview_questions = [];
      optimistic.interview_report = "";
      optimistic.interview_report_file = "";
      optimistic.latest_report_record_id = null;
      optimistic.interview_score = 0;
      optimistic.interview_finished = false;
      optimistic.interview_started = false;
      candidate.value = optimistic;

      if (resumeFile.value) {
        await uploadResume({ silent: true });
        const afterResumeUpload = cloneValue(candidate.value);
        afterResumeUpload.interview_history = [];
        afterResumeUpload.interview_questions = [];
        afterResumeUpload.interview_report = "";
        afterResumeUpload.interview_report_file = "";
        afterResumeUpload.latest_report_record_id = null;
        afterResumeUpload.interview_score = 0;
        afterResumeUpload.interview_finished = false;
        afterResumeUpload.interview_started = false;
        candidate.value = afterResumeUpload;
        appStore.setLoadingAction(LOADING_ACTIONS.INTERVIEW_START);
        appStore.setProgressMessage("正在生成首个问题...");
      }
      // 开始面试不是只生成一句话：
      // 后端会初始化 interview_state、结合后台岗位模板/题库、生成首个问题。
      const result = await apiPost("/api/interview/start", { role: selectedRole.value });
      candidate.value = result.candidate;
    } catch (error) {
      appStore.setErrorMessage(normalizeErrorMessage(error, ERROR_MESSAGES.INTERVIEW_START));
    } finally {
      appStore.setLoadingAction("");
      appStore.setProgressMessage("");
    }
  }

  async function endInterview() {
    if (!candidate.value) {
      return;
    }
    appStore.setLoadingAction(LOADING_ACTIONS.INTERVIEW_END);
    appStore.setErrorMessage("");
    try {
      const result = await apiPost("/api/interview/end", {});
      candidate.value = result.candidate;
    } catch (error) {
      appStore.setErrorMessage(normalizeErrorMessage(error, ERROR_MESSAGES.INTERVIEW_END));
    } finally {
      appStore.setLoadingAction("");
    }
  }

  async function generateReport() {
    if (!candidate.value) {
      return;
    }
    appStore.setLoadingAction(LOADING_ACTIONS.REPORT);
    appStore.setErrorMessage("");
    appStore.setProgressMessage("正在整理面试记录...");
    const timer = window.setTimeout(() => {
      appStore.setProgressMessage("正在生成报告...");
    }, 700);
    try {
      const result = await apiPost("/api/interview/report", {});
      candidate.value = result.candidate;
      await loadHistoryRecordsImmediate();
      appStore.setMode(MODES.INTERVIEW);
    } catch (error) {
      appStore.setErrorMessage(normalizeErrorMessage(error, ERROR_MESSAGES.REPORT));
    } finally {
      window.clearTimeout(timer);
      appStore.setLoadingAction("");
      appStore.setProgressMessage("");
    }
  }

  async function loadHistoryRecordsImmediate() {
    if (!auth.value.authenticated) {
      return;
    }
    appStore.setLoadingAction(LOADING_ACTIONS.HISTORY);
    appStore.setErrorMessage("");
    try {
      const result = await apiGet("/api/history/interviews");
      historyRecords.value = result.records || [];
    } catch (error) {
      appStore.setErrorMessage(normalizeErrorMessage(error, ERROR_MESSAGES.HISTORY_LIST));
    } finally {
      appStore.setLoadingAction("");
    }
  }

  async function completeOnboarding(completed = true) {
    appStore.setLoadingAction(LOADING_ACTIONS.WORKSPACE);
    try {
      const data = await apiPost("/api/workspace/onboarding", { completed });
      syncAppPayload(data);
    } catch (error) {
      appStore.setErrorMessage(normalizeErrorMessage(error, "更新新手引导状态失败。"));
    } finally {
      appStore.setLoadingAction("");
    }
  }

  async function createProject(name) {
    appStore.setLoadingAction(LOADING_ACTIONS.WORKSPACE);
    appStore.setErrorMessage("");
    try {
      const data = await apiPost("/api/workspace/projects", { name });
      syncAppPayload(data);
    } catch (error) {
      appStore.setErrorMessage(normalizeErrorMessage(error, "创建项目失败。"));
      throw error;
    } finally {
      appStore.setLoadingAction("");
    }
  }

  async function renameProject(projectId, name) {
    appStore.setLoadingAction(LOADING_ACTIONS.WORKSPACE);
    try {
      const data = await apiPatch(`/api/workspace/projects/${projectId}`, { name });
      syncAppPayload(data);
    } catch (error) {
      appStore.setErrorMessage(normalizeErrorMessage(error, "重命名项目失败。"));
      throw error;
    } finally {
      appStore.setLoadingAction("");
    }
  }

  async function activateProject(projectId) {
    appStore.setLoadingAction(LOADING_ACTIONS.WORKSPACE);
    try {
      const data = await apiPost(`/api/workspace/projects/${projectId}/activate`, {});
      syncAppPayload(data);
    } catch (error) {
      appStore.setErrorMessage(normalizeErrorMessage(error, "切换项目失败。"));
      throw error;
    } finally {
      appStore.setLoadingAction("");
    }
  }

  async function togglePinProject(projectId) {
    appStore.setLoadingAction(LOADING_ACTIONS.WORKSPACE);
    try {
      const data = await apiPost(`/api/workspace/projects/${projectId}/pin`, {});
      syncAppPayload(data);
    } catch (error) {
      appStore.setErrorMessage(normalizeErrorMessage(error, "更新项目置顶状态失败。"));
      throw error;
    } finally {
      appStore.setLoadingAction("");
    }
  }

  async function deleteProject(projectId) {
    appStore.setLoadingAction(LOADING_ACTIONS.WORKSPACE);
    try {
      const data = await apiDelete(`/api/workspace/projects/${projectId}`);
      syncAppPayload(data);
    } catch (error) {
      appStore.setErrorMessage(normalizeErrorMessage(error, "删除项目失败。"));
      throw error;
    } finally {
      appStore.setLoadingAction("");
    }
  }

  async function createConversation(projectId, name) {
    // 会话属于工作区状态，最终以后端返回为准。
    // 前端不自己拼接 conversations，避免排序、置顶、激活状态和后端不一致。
    appStore.setLoadingAction(LOADING_ACTIONS.WORKSPACE);
    try {
      const data = await apiPost(`/api/workspace/projects/${projectId}/conversations`, { name });
      syncAppPayload(data);
    } catch (error) {
      appStore.setErrorMessage(normalizeErrorMessage(error, "创建会话失败。"));
      throw error;
    } finally {
      appStore.setLoadingAction("");
    }
  }

  async function renameConversation(conversationId, name) {
    appStore.setLoadingAction(LOADING_ACTIONS.WORKSPACE);
    try {
      const data = await apiPatch(`/api/workspace/conversations/${conversationId}`, { name });
      syncAppPayload(data);
    } catch (error) {
      appStore.setErrorMessage(normalizeErrorMessage(error, "重命名会话失败。"));
      throw error;
    } finally {
      appStore.setLoadingAction("");
    }
  }

  async function activateConversation(conversationId) {
    // 切换会话会影响右侧聊天历史、简历、报告和当前模式。
    // 所以接口返回后要 syncAppPayload，而不是只改一个 active_conversation_id。
    appStore.setLoadingAction(LOADING_ACTIONS.WORKSPACE);
    try {
      const data = await apiPost(`/api/workspace/conversations/${conversationId}/activate`, {});
      syncAppPayload(data);
    } catch (error) {
      appStore.setErrorMessage(normalizeErrorMessage(error, "切换会话失败。"));
      throw error;
    } finally {
      appStore.setLoadingAction("");
    }
  }

  async function togglePinConversation(conversationId) {
    appStore.setLoadingAction(LOADING_ACTIONS.WORKSPACE);
    try {
      const data = await apiPost(`/api/workspace/conversations/${conversationId}/pin`, {});
      syncAppPayload(data);
    } catch (error) {
      appStore.setErrorMessage(normalizeErrorMessage(error, "更新会话置顶状态失败。"));
      throw error;
    } finally {
      appStore.setLoadingAction("");
    }
  }

  async function updateConversationMode(conversationId, preferredMode) {
    try {
      const data = await apiPost(`/api/workspace/conversations/${conversationId}/mode`, { preferred_mode: preferredMode });
      syncAppPayload(data, { mode: preferredMode });
    } catch (error) {
      appStore.setErrorMessage(normalizeErrorMessage(error, "同步会话模式失败。"));
    }
  }

  async function deleteConversation(conversationId) {
    appStore.setLoadingAction(LOADING_ACTIONS.WORKSPACE);
    try {
      const data = await apiDelete(`/api/workspace/conversations/${conversationId}`);
      syncAppPayload(data);
    } catch (error) {
      appStore.setErrorMessage(normalizeErrorMessage(error, "删除会话失败。"));
      throw error;
    } finally {
      appStore.setLoadingAction("");
    }
  }

  function loadHistoryRecords() {
    debouncedHistoryLoader();
  }

  async function openHistoryRecord(recordId) {
    appStore.setLoadingAction(LOADING_ACTIONS.HISTORY);
    appStore.setErrorMessage("");
    try {
      const result = await apiGet(`/api/history/interviews/${recordId}`);
      appStore.setSelectedHistoryRecord(result.record || null);
      appStore.setMode(MODES.HISTORY);
    } catch (error) {
      appStore.setErrorMessage(normalizeErrorMessage(error, ERROR_MESSAGES.HISTORY_DETAIL));
    } finally {
      appStore.setLoadingAction("");
    }
  }

  async function restoreHistoryRecord(recordId) {
    appStore.setLoadingAction(LOADING_ACTIONS.HISTORY);
    appStore.setErrorMessage("");
    try {
      const result = await apiPost(`/api/history/interviews/${recordId}/restore`, {});
      candidate.value = result.candidate;
      appStore.setMode(MODES.INTERVIEW);
    } catch (error) {
      appStore.setErrorMessage(normalizeErrorMessage(error, ERROR_MESSAGES.HISTORY_RESTORE));
    } finally {
      appStore.setLoadingAction("");
    }
  }

  async function sendQaMessage() {
    await ensureCandidateReady();
    if (!candidate.value || !qaInput.value.trim() || isTyping.value) {
      return;
    }

    // 乐观更新 optimistic update：
    // 用户点击发送后，前端先展示用户气泡和 AI 占位气泡。
    // 这样即使模型还没开始返回，用户也能看到页面有反馈。
    const message = qaInput.value.trim();
    qaInput.value = "";
    appStore.setErrorMessage("");

    const optimistic = cloneValue(candidate.value);
    optimistic.qa_history.push({ role: "user", content: message });
    optimistic.qa_history.push({
      role: "assistant",
      content: UI_TEXT.QA_PENDING_MESSAGE,
      status: MESSAGE_STATUS.GENERATING,
    });
    candidate.value = optimistic;

    await streamAssistantReply({
      path: "/api/qa/chat/stream",
      payload: { message, action: STREAM_ACTIONS.SEND },
      historyKey: "qa_history",
      assistantIndex: optimistic.qa_history.length - 1,
      pendingMessage: UI_TEXT.QA_PENDING_MESSAGE,
      fallbackErrorMessage: ERROR_MESSAGES.QA_STREAM,
      abortedMessage: "这次回答已被手动停止，你可以继续生成或重试本轮回答。",
    });
  }

  async function sendInterviewMessage() {
    await ensureCandidateReady();
    if (!candidate.value || !interviewInput.value.trim() || isTyping.value) {
      return;
    }
    const message = interviewInput.value.trim();
    interviewInput.value = "";
    appStore.setErrorMessage("");

    const optimistic = cloneValue(candidate.value);
    // 面试模式和问答模式共用同一个流式函数，
    // 区别只是 historyKey、接口路径和 pending 文案不同。
    optimistic.interview_history.push({ role: "user", content: message });
    optimistic.interview_history.push({
      role: "assistant",
      content: UI_TEXT.INTERVIEW_PENDING_MESSAGE,
      status: MESSAGE_STATUS.GENERATING,
    });
    candidate.value = optimistic;

    await streamAssistantReply({
      path: "/api/interview/message/stream",
      payload: { message, action: STREAM_ACTIONS.SEND },
      historyKey: "interview_history",
      assistantIndex: optimistic.interview_history.length - 1,
      pendingMessage: UI_TEXT.INTERVIEW_PENDING_MESSAGE,
      fallbackErrorMessage: ERROR_MESSAGES.INTERVIEW_STREAM,
      abortedMessage: "这轮回复已被手动停止，你可以继续生成或重试本轮回答。",
    });
  }

  async function resumeQaReply() {
    await retryOrResumeHistory({
      path: "/api/qa/chat/stream",
      historyKey: "qa_history",
      pendingMessage: UI_TEXT.QA_PENDING_MESSAGE,
      action: STREAM_ACTIONS.RESUME,
      fallbackErrorMessage: ERROR_MESSAGES.STREAM_RESUME,
      abortedMessage: "继续生成已被停止。",
    });
  }

  async function retryQaReply() {
    await retryOrResumeHistory({
      path: "/api/qa/chat/stream",
      historyKey: "qa_history",
      pendingMessage: UI_TEXT.QA_PENDING_MESSAGE,
      action: STREAM_ACTIONS.RETRY,
      fallbackErrorMessage: ERROR_MESSAGES.STREAM_RETRY,
      abortedMessage: "重试已被停止。",
    });
  }

  async function resumeInterviewReply() {
    await retryOrResumeHistory({
      path: "/api/interview/message/stream",
      historyKey: "interview_history",
      pendingMessage: UI_TEXT.INTERVIEW_PENDING_MESSAGE,
      action: STREAM_ACTIONS.RESUME,
      fallbackErrorMessage: ERROR_MESSAGES.STREAM_RESUME,
      abortedMessage: "继续生成已被停止。",
    });
  }

  async function retryInterviewReply() {
    await retryOrResumeHistory({
      path: "/api/interview/message/stream",
      historyKey: "interview_history",
      pendingMessage: UI_TEXT.INTERVIEW_PENDING_MESSAGE,
      action: STREAM_ACTIONS.RETRY,
      fallbackErrorMessage: ERROR_MESSAGES.STREAM_RETRY,
      abortedMessage: "重试已被停止。",
    });
  }

  async function retryOrResumeHistory({ path, historyKey, pendingMessage, action, fallbackErrorMessage, abortedMessage }) {
    if (!candidate.value || isTyping.value) {
      return;
    }

    const optimistic = cloneValue(candidate.value);
    const history = optimistic[historyKey];
    if (!history?.length || history[history.length - 1]?.role !== "assistant") {
      return;
    }

    history[history.length - 1] = {
      ...history[history.length - 1],
      content: pendingMessage,
      status: MESSAGE_STATUS.GENERATING,
    };
    candidate.value = optimistic;

    // retry：后端重新生成上一轮回答。
    // resume：后端基于已生成的 partial reply 继续生成。
    await streamAssistantReply({
      path,
      payload: { action },
      historyKey,
      assistantIndex: history.length - 1,
      pendingMessage,
      fallbackErrorMessage,
      abortedMessage,
    });
  }

  async function streamAssistantReply({
    path,
    payload,
    historyKey,
    assistantIndex,
    pendingMessage,
    fallbackErrorMessage,
    abortedMessage,
  }) {
    /*
     * 真流式链路：
     * -----------------------------------------------------------------------
     * 1. fetch 请求后端流式接口。
     * 2. response.body.getReader() 循环读取字节流。
     * 3. TextDecoder 把 Uint8Array 解码成字符串。
     * 4. 后端约定每一行是一个 JSON 事件，前端按 \n 拆行解析。
     * 5. 收到 token/chunk 就更新当前 assistant 气泡。
     *
     * 这里是整个前端最值得学的地方：
     * 它把“后端持续 yield 数据”转换成“Vue 页面逐字/逐段更新”。
     */
    const controller = new AbortController();
    let partialText = "";
    appStore.setTypingState({ historyKey, messageIndex: assistantIndex, controller });
    appStore.setStopRequested(false);
    appStore.setProgressMessage("");

    try {
      const response = await apiStreamPost(path, payload, controller.signal);
      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error("当前环境不支持流式读取。");
      }

      // TextDecoder 是浏览器内置对象，用来把二进制字节解码成 UTF-8 文本。
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }
        // value 是本轮读取到的一小块 Uint8Array。
        // decoder.decode(..., { stream: true }) 表示后续可能还有没读完的字节。
        buffer += decoder.decode(value, { stream: true });
        buffer = handleStreamBuffer(buffer, historyKey, assistantIndex, pendingMessage, (chunkText, nextCandidate) => {
          partialText = chunkText;
          if (nextCandidate) {
            candidate.value = nextCandidate;
          }
        });
      }

      // reader 结束后再 decode 一次，用于刷出 TextDecoder 内部剩余字符。
      buffer += decoder.decode();
      handleStreamBuffer(buffer, historyKey, assistantIndex, pendingMessage, (chunkText, nextCandidate) => {
        partialText = chunkText;
        if (nextCandidate) {
          candidate.value = nextCandidate;
        }
      });
      const finalMessage = candidate.value?.[historyKey]?.[assistantIndex];
      if (!finalMessage || finalMessage.status === MESSAGE_STATUS.GENERATING) {
        throw new Error("流式连接提前结束，正在尝试恢复本轮结果。");
      }
    } catch (error) {
      if (error?.name === "AbortError") {
        // 用户点击“停止”会触发 AbortController.abort()，fetch 抛 AbortError。
        // 这不是系统崩溃，而是用户主动中断，所以标记为 interrupted。
        const interruptedText = partialText ? `${partialText}${UI_TEXT.INTERRUPTED_SUFFIX}` : abortedMessage;
        appStore.updateHistoryMessage(historyKey, assistantIndex, interruptedText, MESSAGE_STATUS.INTERRUPTED);
      } else {
        const recovered = path.includes("/api/interview/")
          ? await recoverCompletedInterviewRun(currentRunId.value)
          : null;
        // 面试模式支持 run_id 恢复：即使前端连接断了，后端 Agent 可能已经跑完。
        // 如果能恢复，就直接同步后端最终 candidate，减少用户丢结果的概率。
        if (recovered?.candidate) {
          candidate.value = recovered.candidate;
          appStore.setCurrentCitations(recovered.evidence || []);
          appStore.setErrorMessage("");
        } else {
          appStore.setErrorMessage(normalizeErrorMessage(error, fallbackErrorMessage));
          appStore.updateHistoryMessage(
            historyKey,
            assistantIndex,
            partialText || error.message || "回复失败，请稍后重试。",
            MESSAGE_STATUS.INTERRUPTED,
          );
        }
      }
    } finally {
      appStore.setTypingState(null);
      appStore.setStopRequested(false);
      appStore.setProgressMessage("");
    }
  }

  function handleStreamBuffer(buffer, historyKey, assistantIndex, pendingMessage, onProgress) {
    /*
     * 处理 NDJSON 流式事件：
     * -----------------------------------------------------------------------
     * NDJSON = Newline Delimited JSON，也就是“一行一个 JSON”。
     * 后端每 yield 一行，前端就能解析出一个事件。
     *
     * 但浏览器 read() 不保证每次刚好读到完整一行，所以：
     * - 完整行：立即 JSON.parse 并处理。
     * - 最后一段半行：作为 remainder 返回，下次继续拼。
     */
    const lines = buffer.split("\n");
    const remainder = lines.pop() ?? "";
    let currentText = getHistoryMessageContent(historyKey, assistantIndex);
    if (currentText === pendingMessage) {
      currentText = "";
    }

    lines.forEach((line) => {
      const raw = line.trim();
      if (!raw) {
        return;
      }
      const event = JSON.parse(raw);
      // event.type 决定这行事件要更新哪个前端状态。
      if (event.type === "run_started") {
        // 一次 Agent/流式任务开始，记录 run_id，后续可用于取消或恢复。
        appStore.beginAgentRun(event.run_id);
        appStore.recordAgentEvent(event);
        return;
      }
      if (["node_started", "node_finished", "tool_called", "retrieval_finished", "run_finished"].includes(event.type)) {
        // Agent 可视化事件：用于展示“哪个节点开始/结束、调用了什么工具、检索是否完成”。
        appStore.recordAgentEvent(event);
        if (event.content) appStore.setProgressMessage(event.content);
        return;
      }
      if (event.type === "status") {
        // 普通阶段提示，例如“正在检索知识库”“正在组织回答”。
        appStore.setProgressMessage(event.content || "");
        return;
      }
      if (event.type === "chunk" || event.type === "token") {
        // 模型真正生成的文本增量，追加到当前 assistant 气泡。
        currentText += event.content || "";
        appStore.updateHistoryMessage(historyKey, assistantIndex, currentText, MESSAGE_STATUS.GENERATING);
        onProgress(currentText);
        return;
      }
      if (event.type === "done") {
        // done 表示后端已经完成生成并持久化状态。
        // 如果后端返回 candidate，前端以 candidate 为准，避免本地状态和后端不一致。
        appStore.setCurrentCitations(event.evidence || []);
        if (event.candidate) {
          candidate.value = event.candidate;
        } else {
          appStore.updateHistoryMessage(historyKey, assistantIndex, currentText, MESSAGE_STATUS.DONE);
        }
        onProgress(event.reply || currentText, event.candidate || null);
        return;
      }
      if (event.type === "error") {
        // 普通流式错误，交给外层 catch 标记当前消息 interrupted。
        throw new Error(event.detail || "流式请求失败，请稍后重试。");
      }
      if (event.type === "run_error") {
        // Agent 工作流错误，同时记录到 Agent 面板，方便后台/前台调试。
        appStore.recordAgentEvent(event);
        throw new Error(event.detail || "Agent 工作流执行失败。");
      }
    });

    return remainder;
  }

  function getHistoryMessageContent(historyKey, messageIndex) {
    if (!candidate.value) {
      return "";
    }
    const history = candidate.value[historyKey];
    return history?.[messageIndex]?.content || "";
  }

  async function requestStopTyping() {
    // 主动停止先通知后端写入取消标记，再中断浏览器的流读取。
    // 这和网络意外断开不同：断网时后台任务会继续，以便稍后恢复结果。
    appStore.setStopRequested(true);
    if (currentRunId.value && typingState.value?.historyKey === "interview_history") {
      await apiPost(`/api/platform/agent-runs/${currentRunId.value}/cancel`, {}).catch(() => null);
    }
    typingState.value?.controller?.abort();
  }

  async function recoverCompletedInterviewRun(runId) {
    if (!runId) {
      return null;
    }
    // 模型线程可能比网络请求晚几秒结束，因此进行有限次数轮询。
    for (let attempt = 0; attempt < 8; attempt += 1) {
      try {
        return await apiPost(`/api/interview/runs/${runId}/recover`, {});
      } catch (error) {
        if (!String(error.message || "").includes("仍在生成")) {
          return null;
        }
        await new Promise((resolve) => setTimeout(resolve, 600));
      }
    }
    return null;
  }

  function normalizeErrorMessage(error, fallback) {
    const text = String(error?.message || fallback || "操作失败，请稍后重试。").trim();
    if (text.includes("401") || text.includes("未登录") || text.includes("登录已失效")) {
      return "登录状态已失效，请重新登录后再继续操作。";
    }
    if (text.includes("Network") || text.includes("Failed to fetch")) {
      return "网络连接失败，请检查后端服务或网络状态。";
    }
    if (text.includes("timeout")) {
      return "请求超时，请稍后重试。";
    }
    if (text.includes("简历")) {
      return text || "简历处理失败，请检查文件格式。";
    }
    return text || fallback || "操作失败，请稍后重试。";
  }

  // 这些包装函数显式把参数转交给 Pinia action。
  // 这样模板层拿到的是稳定的函数调用入口。
  function setAuthMode(nextMode) {
    appStore.setAuthMode(nextMode);
  }

  function setLoginForm(payload) {
    appStore.setLoginForm(payload);
  }

  function setRegisterForm(payload) {
    appStore.setRegisterForm(payload);
  }

  function setSelectedRole(role) {
    appStore.setSelectedRole(role);
  }

  function setKnowledgeFiles(files) {
    appStore.setKnowledgeFiles(files);
  }

  function setResumeFile(file) {
    appStore.setResumeFile(file);
  }

  function setQaInput(value) {
    appStore.setQaInput(value);
  }

  function setInterviewInput(value) {
    appStore.setInterviewInput(value);
  }

  function setLangsmith(payload) {
    appStore.setLangsmith(payload);
  }

  function setMode(nextMode) {
    appStore.setMode(nextMode);
  }

  function setWorkspace(payload) {
    appStore.setWorkspace(payload);
  }

  function setThemeMode(nextMode) {
    appStore.setThemeMode(nextMode);
  }

  return {
    // 页面层最终拿到两类东西：
    // 1. 响应式状态
    // 2. 可以触发的业务动作
    ...storeToRefs(appStore),
    bootstrap,
    refreshBootstrapData,
    refreshRoleOptions,
    syncAppPayload,
    login,
    register,
    logout,
    importKnowledge,
    saveLangSmith,
    uploadResume,
    clearResume,
    clearQaHistory,
    startInterview,
    endInterview,
    generateReport,
    loadHistoryRecords,
    openHistoryRecord,
    restoreHistoryRecord,
    sendQaMessage,
    sendInterviewMessage,
    resumeQaReply,
    retryQaReply,
    resumeInterviewReply,
    retryInterviewReply,
    completeOnboarding,
    createProject,
    renameProject,
    activateProject,
    togglePinProject,
    deleteProject,
    createConversation,
    renameConversation,
    activateConversation,
    togglePinConversation,
    updateConversationMode,
    deleteConversation,
    requestStopTyping,
    setAuthMode,
    setLoginForm,
    setRegisterForm,
    setSelectedRole,
    setKnowledgeFiles,
    setResumeFile,
    setQaInput,
    setInterviewInput,
    setLangsmith,
    setMode,
    setWorkspace,
    setThemeMode,
  };
}
