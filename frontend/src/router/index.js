import { createRouter, createWebHistory } from "vue-router";

// 当前项目的路由比较轻。
// URL 主要承担“页面入口”和“当前模式”这两个职责，
// 真正的大页面切换仍然在 App.vue 里按 mode 来控制。
// 这样做的好处是：路由负责“去哪”，App.vue 负责“展示什么组件”，状态仍然集中在 Pinia/composable。
const RouteStub = {
  template: "<div></div>",
};

const routes = [
  {
    // 首页落地页。
    path: "/",
    name: "landing",
    component: RouteStub,
  },
  {
    // 工作台三种模式：问答、模拟面试、历史记录。
    // :mode 是动态路由参数，App.vue 会读取它并同步到 mode 状态。
    path: "/workspace/:mode(qa|interview|history)",
    name: "workspace",
    component: RouteStub,
    props: true,
  },
  {
    // 角色后台：admin/interviewer 两套入口，section 表示后台里的具体模块。
    // meta.roles 用来表达该路由需要的角色，真正拦截逻辑目前在 App.vue 的 watch 里做。
    path: "/platform/:console(admin|interviewer)/:section(overview|runs|users|organizations|prompts|workspace|candidates|interviews|configuration|reports)?",
    name: "platform",
    component: RouteStub,
    meta: { roles: ["interviewer", "admin"] },
  },
  {
    // 兼容旧路径，避免用户访问 /platform/overview 时白屏。
    path: "/platform/:section(overview|runs|users|organizations|interviews|configuration)?",
    redirect: "/platform/interviewer/workspace",
  },
  {
    // 兜底路由：任何不存在的地址都回首页。
    path: "/:pathMatch(.*)*",
    redirect: "/",
  },
];

export const router = createRouter({
  // createWebHistory 使用浏览器原生 History API。
  // 这样 URL 更干净，不会带 #。
  history: createWebHistory(),
  routes,
});
