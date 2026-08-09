import { defineStore } from "pinia";
import { apiGet, apiPatch, apiPost } from "../api/client.js";

// 管理端使用独立 Store，避免候选人聊天状态和后台统计状态相互污染。
// Pinia Store 可以理解为“前端数据层”：页面组件负责展示，Store 负责保存后台数据和调用接口。
export const usePlatformStore = defineStore("platform", {
  state: () => ({
    // dashboard 总览指标，例如用户数、运行次数、报告数等。
    summary: null,
    // 以下列表分别对应后台页面中的表格数据。
    users: [],
    organizations: [],
    runs: [],
    interviewTasks: [],
    reports: [],
    metrics: [],
    // ECharts 图表数据。后端返回统一结构后，前端 ChartCard 负责渲染。
    charts: {
      run_status: [],
      latency_trend: [],
      score_trend: [],
      role_distribution: [],
      template_roles: [],
      question_dimensions: [],
    },
    // 后台配置类数据：岗位模板、题库、知识库文档、Prompt 版本、模型配置。
    configuration: { templates: [], questions: [], documents: [], prompts: [], models: [] },
    // loading/error 是典型的请求状态，用来做骨架屏、按钮禁用和错误提示。
    loading: false,
    error: "",
  }),
  actions: {
    async loadDashboard() {
      this.loading = true;
      this.error = "";
      try {
        // Promise.all 并行请求多个后台接口，比一个个串行请求更快。
        // 面试可以说：后台首页需要多类数据，所以这里统一并发加载后写入 Store。
        const [dashboard, charts, users, organizations, runs, evaluations, configuration, tasks, reports] = await Promise.all([
          apiGet("/api/platform/dashboard"),
          apiGet("/api/platform/charts"),
          apiGet("/api/platform/users"),
          apiGet("/api/platform/organizations"),
          apiGet("/api/platform/agent-runs"),
          apiGet("/api/platform/evaluations"),
          apiGet("/api/platform/configuration"),
          apiGet("/api/platform/interview-tasks"),
          apiGet("/api/platform/reports"),
        ]);
        this.summary = dashboard.summary;
        this.charts = charts.charts || this.charts;
        this.users = users.users || [];
        this.organizations = organizations.organizations || [];
        this.runs = runs.runs || [];
        this.metrics = evaluations.metrics || [];
        this.configuration = configuration;
        this.interviewTasks = tasks.tasks || [];
        this.reports = reports.reports || [];
      } catch (error) {
        // 接口失败时不让页面白屏，而是把错误保存到 Store 给页面展示。
        this.error = error.message || "管理台数据加载失败。";
      } finally {
        this.loading = false;
      }
    },
    async createOrganization(name) {
      // 创建/修改类操作完成后重新 loadDashboard，保证页面显示的是后端最新数据。
      await apiPost("/api/platform/organizations", { name });
      await this.loadDashboard();
    },
    async updateRole(userId, role, organizationId) {
      // 角色更新属于管理员操作，后端会再次校验当前用户是否有 admin 权限。
      await apiPatch(`/api/platform/users/${userId}/role`, {
        role,
        organization_id: organizationId || null,
      });
      await this.loadDashboard();
    },
    async createTemplate(payload) {
      // 新增岗位模板后，前台模拟面试的岗位列表也可以从后端刷新到最新配置。
      await apiPost("/api/platform/templates", payload);
      await this.loadDashboard();
    },
    async createQuestion(payload) {
      // 题库问题用于后续面试 Planner 和知识点覆盖追踪。
      await apiPost("/api/platform/questions", payload);
      await this.loadDashboard();
    },
    async createPrompt(payload) {
      // Prompt 版本用于管理不同业务链路的提示词，例如问答、追问、评分、报告。
      await apiPost("/api/platform/prompts", payload);
      await this.loadDashboard();
    },
  },
});
