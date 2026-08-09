import axios from "axios";

/*
 * 前端接口层总览
 * ---------------------------------------------------------------------------
 * 这个文件是所有普通 HTTP 请求的统一入口，页面组件不要到处直接写 fetch/axios。
 *
 * 为什么要单独封装？
 * 1. 统一 baseURL：本地开发、服务器部署时接口地址可能不同。
 * 2. 统一携带 Cookie：后端使用 Cookie Session 鉴权，前端请求必须带上 Cookie。
 * 3. 统一错误处理：FastAPI 报错通常在 detail 字段里，这里提前整理成 Error。
 * 4. 区分普通请求和流式请求：普通 JSON 用 axios，聊天流式响应用 fetch。
 *
 * 面试里可以这样讲：
 * “我把接口请求统一封装在 api 层，页面只调用 apiGet/apiPost 这些方法，
 * 这样如果后端地址、错误处理、登录态携带方式变化，只需要改这一处。”
 */

// API_BASE 支持两种注入方式：
// 1. Vite 环境变量 `VITE_APP_API_BASE_URL`
// 2. 页面运行时注入的 `window.__APP_API_BASE_URL__`
//
// 这样做的好处是本地开发和部署环境都能灵活切换接口地址。
const explicitApiBase =
  (typeof window !== "undefined" && window.__APP_API_BASE_URL__) ||
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_APP_API_BASE_URL) ||
  "";

function resolveDefaultApiBase() {
  if (typeof window === "undefined") {
    return "";
  }

  const { protocol, hostname, port } = window.location;

  // 如果前端页面本身就是被 FastAPI 直接托管的，就走同源请求。
  // 同源请求的好处：浏览器不会触发跨域限制，Cookie 也更容易正确携带。
  if (port === "8080" || port === "8000") {
    return "";
  }

  // 本地开发时，如果前端跑在 Vite 端口上，就默认把请求打到 8080。
  // 例子：前端 localhost:5173，后端 127.0.0.1:8080。
  if (hostname === "localhost" || hostname === "127.0.0.1") {
    return `${protocol}//127.0.0.1:8080`;
  }

  return "";
}

export const API_BASE = String(explicitApiBase || resolveDefaultApiBase()).replace(/\/$/, "");

// 普通接口统一走 axios：
// - 自动拼接 baseURL
// - 自动控制超时
// - 统一错误处理
// - 自动携带 Cookie
const request = axios.create({
  baseURL: API_BASE,
  timeout: 20000,
  // withCredentials=true 表示跨端口请求时也携带 Cookie。
  // 当前项目登录态在后端 HttpOnly Cookie 里，不是 localStorage token。
  withCredentials: true,
});

request.interceptors.response.use(
  (response) => response,
  (error) => {
    // FastAPI 的错误通常会放在 detail 字段里，这里统一提取出来。
    const detail = error?.response?.data?.detail;
    throw new Error(detail || error.message || "请求失败，请稍后重试。");
  },
);

// GET：读取数据，比如 bootstrap、历史记录列表、历史详情。
export async function apiGet(path) {
  const response = await request.get(path);
  return response.data;
}

// POST + JSON：适合登录、注册、创建记录、切换状态等标准接口。
export async function apiPost(path, body) {
  // JSON 请求：前端把普通 JS 对象 JSON.stringify 后交给后端。
  // axios 会帮我们完成大部分序列化工作，这里显式写 Content-Type 方便学习理解。
  const response = await request.post(path, body, {
    headers: {
      "Content-Type": "application/json",
    },
  });
  return response.data;
}

export async function apiPatch(path, body) {
  const response = await request.patch(path, body, {
    headers: {
      "Content-Type": "application/json",
    },
  });
  return response.data;
}

export async function apiDelete(path) {
  const response = await request.delete(path);
  return response.data;
}

// FormData：浏览器官方提供的文件上传数据结构。
// 例如：
// const formData = new FormData()
// formData.append("file", file)
// 然后交给后端作为 multipart/form-data 解析。
export async function apiFormPost(path, formData) {
  // 注意：上传文件时不要手动写 Content-Type。
  // 浏览器会自动生成 multipart boundary；手动写反而可能让后端解析失败。
  const response = await request.post(path, formData);
  return response.data;
}

// 流式请求保留 fetch。
// 原因是 fetch 更适合直接读取 ReadableStream，
// 后面可以通过 response.body.getReader() 一段一段拿后端数据。
export async function apiStreamPost(path, body, signal) {
  /*
   * 真实流式请求为什么不用 axios？
   * -------------------------------------------------------------------------
   * 浏览器 fetch 原生暴露 response.body，也就是 ReadableStream。
   * 前端可以通过 getReader().read() 不断读取后端一点点 yield 出来的数据。
   *
   * signal 来自 AbortController：
   * - 用户点击“停止”时，前端调用 controller.abort()
   * - fetch 会抛出 AbortError
   * - composable 再把当前 assistant 消息标记为 interrupted
   */
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "include",
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || "流式请求失败，请稍后重试。");
  }

  return response;
}
