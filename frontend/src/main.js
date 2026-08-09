import { createApp } from "vue";
import { createPinia } from "pinia";
import App from "./App.vue";
import { router } from "./router/index.js";
import "./styles.css";

// 前端启动入口。
// 浏览器打开页面后，Vite 会先执行这个文件，再把整个 Vue 应用挂到 index.html 的 #app 节点。
//
// 可以直接记这 4 步：
// 1. createApp(App) 创建应用实例
// 2. app.use(createPinia()) 注册全局状态管理
// 3. app.use(router) 注册前端路由
// 4. app.mount("#app") 挂载到页面根节点
const app = createApp(App);

// Pinia 可以理解成前端里的全局状态仓库。
// 这个项目里登录态、当前会话、聊天记录、输入框内容、加载状态都由它统一管理。
// 面试表达：组件不直接互相改数据，而是通过 Store 读写共享状态，页面会自动响应式更新。
app.use(createPinia());

// Vue Router 负责根据 URL 切换首页、工作台、后台等页面。
app.use(router);

// mount 之后，Vue 才真正接管 index.html 里的页面渲染。
app.mount("#app");
