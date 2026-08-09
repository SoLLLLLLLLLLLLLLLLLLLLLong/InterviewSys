// 兼容旧导入路径，统一转发到新的 constants 目录。
export * from "./constants/app.js";

import { MODES } from "./constants/app.js";

// 这几个常量在老文件里用得比较多，先保留别名，避免一次性重构太大。
export const QA_MODE = "qa";
export const INTERVIEW_MODE = "interview";
export const HISTORY_MODE = "history";
export const defaultModes = MODES;
