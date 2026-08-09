import {
  createDefaultAuth,
  createDefaultLangSmith,
  createDefaultLoginForm,
  createDefaultMeta,
  createDefaultRegisterForm,
  createDefaultWeather,
  createDefaultWorkspace,
} from "../types/app.js";

// 统一常量的好处：
// 1. 避免到处散落魔法字符串
// 2. 页面层、状态层、接口层共用同一套业务枚举
// 3. 后续修改字段名或文案时更容易集中维护
export const MODES = {
  QA: "qa",
  INTERVIEW: "interview",
  HISTORY: "history",
};

// 当前正在执行的加载动作。
// 页面会根据它控制按钮禁用、loading 文案和错误提示。
export const LOADING_ACTIONS = {
  LOGIN: "login",
  REGISTER: "register",
  LOGOUT: "logout",
  KNOWLEDGE: "knowledge",
  LANGSMITH: "langsmith",
  RESUME: "resume",
  RESUME_CLEAR: "resume-clear",
  QA_CLEAR: "qa-clear",
  INTERVIEW_START: "interview-start",
  INTERVIEW_END: "interview-end",
  REPORT: "report",
  HISTORY: "history",
  WORKSPACE: "workspace",
};

export const THEME_MODES = {
  SERIOUS: "serious",
  LIGHT: "light",
  SPRINT: "sprint",
};

export const THEME_LABELS = {
  [THEME_MODES.SERIOUS]: {
    title: "严肃面试官模式",
    subtitle: "更克制、更专业，适合正式模拟面试。",
  },
  [THEME_MODES.LIGHT]: {
    title: "轻量练习模式",
    subtitle: "更轻松、更柔和，适合日常知识点练习。",
  },
  [THEME_MODES.SPRINT]: {
    title: "冲刺复习模式",
    subtitle: "更聚焦、更高对比，适合短期冲刺准备。",
  },
};

// 流式接口支持的动作类型：
// - send：正常发送
// - resume：继续生成
// - retry：重试本轮回答
export const STREAM_ACTIONS = {
  SEND: "send",
  RESUME: "resume",
  RETRY: "retry",
};

// 消息在前端展示时的状态。
export const MESSAGE_STATUS = {
  DONE: "done",
  GENERATING: "generating",
  INTERRUPTED: "interrupted",
};

export const UI_TEXT = {
  QA_PENDING_MESSAGE: "面试助手正在整理答案中...",
  INTERVIEW_PENDING_MESSAGE: "面试官正在组织语言中...",
  INTERRUPTED_SUFFIX: "\n\n[这条回复已被手动停止。]",
};

export const ERROR_MESSAGES = {
  BOOTSTRAP: "初始化失败，请检查后端服务是否已启动。",
  LOGIN: "登录失败，请检查邮箱和密码。",
  REGISTER: "注册失败，请检查输入信息。",
  LOGOUT: "退出登录失败。",
  KNOWLEDGE_IMPORT: "知识库导入失败，请检查文件格式或后端服务。",
  LANGSMITH_SAVE: "LangSmith 设置保存失败。",
  RESUME_UPLOAD: "简历上传失败，请检查文件格式或大小。",
  RESUME_CLEAR: "清除简历失败。",
  QA_CLEAR: "清空问答历史失败。",
  INTERVIEW_START: "启动面试失败，请稍后重试。",
  INTERVIEW_END: "结束面试失败。",
  REPORT: "生成报告失败，请稍后重试。",
  HISTORY_LIST: "加载历史记录失败。",
  HISTORY_DETAIL: "加载历史详情失败。",
  HISTORY_RESTORE: "恢复历史记录失败。",
  QA_STREAM: "问答请求失败。",
  INTERVIEW_STREAM: "面试回复失败。",
  STREAM_RESUME: "继续生成失败。",
  STREAM_RETRY: "重试失败。",
};

export const DEFAULT_AUTH = createDefaultAuth();
export const DEFAULT_WEATHER = createDefaultWeather();
export const DEFAULT_META = createDefaultMeta();
export const DEFAULT_LANGSMITH = createDefaultLangSmith();
export const DEFAULT_LOGIN_FORM = createDefaultLoginForm();
export const DEFAULT_REGISTER_FORM = createDefaultRegisterForm();
export const DEFAULT_HISTORY_DETAIL = null;
export const DEFAULT_WORKSPACE = createDefaultWorkspace();
