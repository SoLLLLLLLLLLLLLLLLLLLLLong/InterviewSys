<template>
  <div class="platform-shell">
    <aside class="platform-rail">
      <div>
        <span class="platform-rail-eyebrow">{{ consoleTitle }}</span>
        <h1>{{ consoleHeadline }}</h1>
        <p>{{ consoleDescription }}</p>
      </div>

      <nav class="platform-rail-nav" aria-label="后台模块">
        <button
          v-for="item in tabs"
          :key="item.value"
          :class="['platform-rail-item', activeSection === item.value ? 'active' : '']"
          @click="openSection(item.value)"
        >
          <span>{{ item.icon }}</span>
          <strong>{{ item.label }}</strong>
        </button>
      </nav>

      <div class="platform-rail-footer">
        <button class="ghost-button" @click="emit('back')">返回工作台</button>
        <button class="primary-button" :disabled="platform.loading" @click="platform.loadDashboard()">
          {{ platform.loading ? "刷新中..." : "刷新数据" }}
        </button>
      </div>
    </aside>

    <main class="platform-main">
      <header class="platform-topbar">
        <div>
          <span class="setup-eyebrow">{{ roleBadge }}</span>
          <h2>{{ activeTab?.label || "数据概览" }}</h2>
        </div>
        <div class="platform-toolbar">
          <input v-model.trim="keyword" class="platform-search" placeholder="搜索用户、岗位、Run ID 或报告" />
          <select v-model="statusFilter" class="compact-select">
            <option value="">全部状态</option>
            <option value="running">运行中</option>
            <option value="completed">已完成</option>
            <option value="failed">失败</option>
            <option value="cancelled">已取消</option>
          </select>
        </div>
      </header>

      <div v-if="platform.error" class="error-banner">{{ platform.error }}</div>
      <PanelSkeleton v-if="platform.loading && !platform.summary" :rows="6" />

      <template v-else>
        <section class="platform-stat-grid">
          <article v-for="card in statCards" :key="card.label" class="platform-stat-card">
            <span>{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
            <small>{{ card.caption }}</small>
          </article>
        </section>

        <section v-if="isAdminConsole && activeSection === 'overview'" class="platform-grid two-columns">
          <article class="platform-card feature-card">
            <div class="platform-card-heading">
              <h3>平台治理</h3>
              <span>RBAC / 组织 / 系统指标</span>
            </div>
            <div class="metric-list">
              <div><span>管理员视角</span><strong>全平台</strong></div>
              <div><span>用户总数</span><strong>{{ platform.summary?.users || 0 }}</strong></div>
              <div><span>组织数量</span><strong>{{ platform.summary?.organizations || 0 }}</strong></div>
              <div><span>知识库文档</span><strong>{{ platform.summary?.documents || 0 }}</strong></div>
            </div>
          </article>

          <article class="platform-card feature-card dark">
            <div class="platform-card-heading">
              <h3>Agent 可观测</h3>
              <span>运行状态 / 延迟 / 错误</span>
            </div>
            <div class="metric-list">
              <div v-for="(count, status) in platform.summary?.runs_by_status || {}" :key="status">
                <span>{{ statusLabel(status) }}</span><strong>{{ count }}</strong>
              </div>
              <div><span>平均延迟</span><strong>{{ platform.summary?.average_latency_ms || 0 }} ms</strong></div>
            </div>
          </article>

          <ChartCard
            title="Agent 运行状态"
            subtitle="按状态统计 Run 数量"
            type="pie"
            :data="platform.charts.run_status"
          />

          <ChartCard
            title="Agent 延迟趋势"
            subtitle="最近 12 次运行耗时"
            type="line"
            :data="platform.charts.latency_trend"
          />

          <article class="platform-card">
            <div class="platform-card-heading">
              <h3>自动评测</h3>
              <span>Router / RAG / 评分一致性</span>
            </div>
            <div v-if="!platform.metrics.length" class="platform-empty">尚未导入评测结果，可后续接入 LangSmith Dataset 或评测脚本。</div>
            <div v-else class="metric-list">
              <div v-for="item in platform.metrics" :key="item.metric">
                <span>{{ item.metric }} · {{ item.samples }} 个样本</span><strong>{{ formatScore(item.score) }}</strong>
              </div>
            </div>
          </article>

          <article class="platform-card">
            <div class="platform-card-heading">
              <h3>最近失败</h3>
              <span>用于排查 Prompt、Tool 或模型异常</span>
            </div>
            <div v-if="!failedRuns.length" class="platform-empty">当前没有失败运行记录。</div>
            <div v-else class="run-timeline">
              <div v-for="run in failedRuns.slice(0, 5)" :key="run.run_id" class="run-timeline-item">
                <span class="run-dot failed"></span>
                <div>
                  <strong>{{ shortId(run.run_id) }} · {{ run.workflow }}</strong>
                  <p>{{ run.current_node || "未知节点" }} · {{ formatDate(run.created_at) }}</p>
                </div>
              </div>
            </div>
          </article>

          <ChartCard
            title="候选人得分趋势"
            subtitle="最近面试报告分数"
            type="line"
            :data="platform.charts.score_trend"
          />

          <ChartCard
            title="岗位任务分布"
            subtitle="不同岗位的面试任务量"
            type="bar"
            :data="platform.charts.role_distribution"
          />
        </section>

        <section v-else-if="!isAdminConsole && activeSection === 'workspace'" class="platform-grid two-columns">
          <article class="platform-card feature-card">
            <div class="platform-card-heading">
              <h3>面试业务概览</h3>
              <span>候选人 / 任务 / 报告</span>
            </div>
            <div class="metric-list">
              <div><span>当前组织</span><strong>{{ currentOrganization }}</strong></div>
              <div><span>面试任务</span><strong>{{ platform.interviewTasks.length }}</strong></div>
              <div><span>面试报告</span><strong>{{ platform.reports.length }}</strong></div>
              <div><span>平均分</span><strong>{{ averageInterviewScore }} 分</strong></div>
            </div>
          </article>

          <article class="platform-card">
            <div class="platform-card-heading">
              <h3>评分趋势</h3>
              <span>最近报告表现</span>
            </div>
            <div v-if="!filteredReports.length" class="platform-empty">暂无报告，完成模拟面试后会出现在这里。</div>
            <div v-else class="score-bars">
              <div v-for="report in filteredReports.slice(0, 6)" :key="report.id" class="score-bar-row">
                <span>{{ report.candidate_name || "候选人" }}</span>
                <div><i :style="{ width: `${Math.min(Number(report.score || 0), 100)}%` }"></i></div>
                <strong>{{ report.score || 0 }}</strong>
              </div>
            </div>
          </article>

          <article class="platform-card">
            <div class="platform-card-heading">
              <h3>待复盘任务</h3>
              <span>按最近时间排序</span>
            </div>
            <InterviewTaskTable :tasks="filteredTasks.slice(0, 8)" />
          </article>

          <article class="platform-card">
            <div class="platform-card-heading">
              <h3>岗位配置完成度</h3>
              <span>模板与题库</span>
            </div>
            <div class="metric-list">
              <div><span>面试模板</span><strong>{{ platform.configuration.templates.length }}</strong></div>
              <div><span>企业题库</span><strong>{{ platform.configuration.questions.length }}</strong></div>
              <div><span>知识文档</span><strong>{{ platform.configuration.documents?.length || platform.summary?.documents || 0 }}</strong></div>
            </div>
          </article>
        </section>

        <section v-else-if="activeSection === 'runs'" class="platform-card">
          <div class="platform-card-heading">
            <h3>Agent 执行记录</h3>
            <span>观察 Router、RAG、评估与报告链路</span>
          </div>
          <RunTable :runs="filteredRuns" />
        </section>

        <section v-else-if="activeSection === 'users' || activeSection === 'candidates'" class="platform-card">
          <div class="platform-card-heading">
            <h3>{{ isAdminConsole ? "用户权限" : "候选人列表" }}</h3>
            <span>{{ isAdminConsole ? "管理员可分配角色和组织" : "面试官查看所属组织候选人" }}</span>
          </div>
          <UserTable
            :users="filteredUsers"
            :organizations="platform.organizations"
            :editable="isAdmin"
            :role-drafts="roleDrafts"
            :organization-drafts="organizationDrafts"
            @save-role="saveRole"
          />
        </section>

        <section v-else-if="activeSection === 'organizations'" class="platform-card">
          <div class="platform-card-heading">
            <h3>组织管理</h3>
            <span>管理员维护企业租户，面试官只读所属组织</span>
          </div>
          <form v-if="isAdmin" class="inline-control-row organization-form" @submit.prevent="createOrganization">
            <input v-model.trim="organizationNameInput" class="text-input" placeholder="输入组织名称" />
            <button class="primary-button" type="submit">创建组织</button>
          </form>
          <div class="organization-grid">
            <article v-for="organization in platform.organizations" :key="organization.id" class="organization-card">
              <strong>{{ organization.name }}</strong>
              <span>组织 ID：{{ organization.id }}</span>
            </article>
          </div>
        </section>

        <section v-else-if="activeSection === 'interviews'" class="platform-card">
          <div class="platform-card-heading">
            <h3>面试任务</h3>
            <span>从岗位模拟面试自动沉淀业务记录</span>
          </div>
          <InterviewTaskTable :tasks="filteredTasks" />
        </section>

        <section v-else-if="activeSection === 'reports'" class="platform-card">
          <div class="platform-card-heading">
            <h3>面试报告</h3>
            <span>评分、引用来源与复盘材料</span>
          </div>
          <ReportList :reports="filteredReports" />
        </section>

        <section v-else-if="activeSection === 'prompts'" class="platform-grid two-columns">
          <article class="platform-card">
            <div class="platform-card-heading">
              <h3>Prompt 版本</h3>
              <span>只有管理员可以调整系统 Prompt</span>
            </div>
            <form class="configuration-form" @submit.prevent="createPrompt">
              <input v-model.trim="promptForm.prompt_key" class="text-input" placeholder="Prompt 标识，例如 interview_question" required />
              <input v-model.trim="promptForm.version" class="text-input" placeholder="版本，例如 v2" required />
              <textarea v-model.trim="promptForm.content" class="text-input" rows="4" placeholder="Prompt 内容" required></textarea>
              <label class="checkbox-row"><input v-model="promptForm.is_active" type="checkbox" /> 保存后设为启用版本</label>
              <button class="primary-button" type="submit">保存 Prompt</button>
            </form>
            <div class="configuration-list">
              <div v-for="item in platform.configuration.prompts" :key="item.id">
                <strong>{{ item.prompt_key }} · {{ item.version }}</strong>
                <span>{{ item.is_active ? "当前启用" : "历史版本" }}</span>
              </div>
            </div>
          </article>

          <article class="platform-card">
            <div class="platform-card-heading">
              <h3>模型配置</h3>
              <span>密钥仅保存在服务端环境变量</span>
            </div>
            <div class="configuration-list">
              <div v-for="item in platform.configuration.models || []" :key="item.purpose">
                <strong>{{ item.purpose }} · {{ item.model }}</strong>
                <span>{{ item.base_url }}</span>
              </div>
            </div>
          </article>
        </section>

        <section v-else class="platform-grid two-columns">
          <ChartCard
            title="岗位模板分布"
            subtitle="后台配置驱动前台岗位选择"
            type="bar"
            :data="platform.charts.template_roles"
          />

          <ChartCard
            title="题库维度覆盖"
            subtitle="按能力维度统计题库数量"
            type="pie"
            :data="platform.charts.question_dimensions"
          />

          <article class="platform-card">
            <div class="platform-card-heading">
              <h3>新增面试岗位</h3>
              <span>先创建岗位配置，再围绕岗位补充模板和题库</span>
            </div>
            <form class="configuration-form" @submit.prevent="createRoleConfig">
              <input v-model.trim="roleConfigForm.role_name" class="text-input" placeholder="岗位名称，例如 AI 应用开发实习生" required />
              <input v-model.trim="roleConfigForm.dimension_text" class="text-input" placeholder="能力维度，例如 Vue3 / FastAPI / RAG / 联调能力" />
              <div class="inline-control-row">
                <select v-model="roleConfigForm.difficulty" class="compact-select">
                  <option value="easy">简单</option>
                  <option value="medium">中等</option>
                  <option value="hard">困难</option>
                </select>
                <input v-model.number="roleConfigForm.question_count" class="text-input" type="number" min="1" max="20" />
              </div>
              <button class="primary-button" type="submit">新增岗位配置</button>
            </form>
          </article>

          <article class="platform-card">
            <div class="platform-card-heading">
              <h3>面试模板</h3>
              <span>控制岗位、难度和题量</span>
            </div>
            <form class="configuration-form" @submit.prevent="createTemplate">
              <input v-model.trim="templateForm.name" class="text-input" placeholder="模板名称" required />
              <input v-model.trim="templateForm.role_name" class="text-input" placeholder="目标岗位" required />
              <div class="inline-control-row">
                <select v-model="templateForm.difficulty" class="compact-select">
                  <option value="easy">简单</option>
                  <option value="medium">中等</option>
                  <option value="hard">困难</option>
                </select>
                <input v-model.number="templateForm.question_count" class="text-input" type="number" min="1" max="20" />
              </div>
              <button class="primary-button" type="submit">创建模板</button>
            </form>
            <div class="configuration-list">
              <div v-for="item in filteredTemplates" :key="item.id">
                <strong>{{ item.name }}</strong>
                <span>{{ item.role_name }} · {{ difficultyLabel(item.difficulty) }} · {{ item.question_count }} 题</span>
              </div>
            </div>
          </article>

          <article class="platform-card">
            <div class="platform-card-heading">
              <h3>企业题库</h3>
              <span>按岗位和能力维度组织问题</span>
            </div>
            <form class="configuration-form" @submit.prevent="createQuestion">
              <input v-model.trim="questionForm.role_name" class="text-input" placeholder="目标岗位" required />
              <input v-model.trim="questionForm.dimension" class="text-input" placeholder="能力维度" required />
              <textarea v-model.trim="questionForm.question_text" class="text-input" rows="3" placeholder="面试问题" required></textarea>
              <button class="primary-button" type="submit">新增题目</button>
            </form>
            <div class="configuration-list">
              <div v-for="item in filteredQuestions" :key="item.id">
                <strong>{{ item.question_text }}</strong>
                <span>{{ item.role_name }} · {{ item.dimension }} · {{ difficultyLabel(item.difficulty) }}</span>
              </div>
            </div>
          </article>
        </section>
      </template>
    </main>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import ChartCard from "../components/ChartCard.vue";
import PanelSkeleton from "../components/PanelSkeleton.vue";
import { usePlatformStore } from "../stores/platformStore.js";

const props = defineProps({ auth: { type: Object, required: true } });
const emit = defineEmits(["back", "roles-updated"]);
const route = useRoute();
const router = useRouter();
const platform = usePlatformStore();

/*
 * PlatformView 后台管理页总览
 * ---------------------------------------------------------------------------
 * 这个页面同时服务两个后台：
 * - 管理员后台：用户权限、组织、Prompt、模型配置、Agent Run 观测。
 * - 面试官后台：岗位题库、候选人、面试任务、报告和趋势看板。
 *
 * 前端通过 route.params.console 判断当前后台视角；
 * 后端仍然会在 /api/platform/* 接口里做 RBAC 校验。
 *
 * 学习重点：
 * - ref：搜索词、筛选状态、表单输入。
 * - reactive：多个字段组成的表单对象。
 * - computed：根据角色/筛选条件推导可见数据。
 * - watch/onMounted：页面进入或路由变化时加载后台数据。
 */
const keyword = ref("");
const statusFilter = ref("");
const organizationNameInput = ref("");
const roleDrafts = reactive({});
const organizationDrafts = reactive({});
const templateForm = reactive({ name: "", role_name: "", difficulty: "medium", question_count: 8 });
const questionForm = reactive({ role_name: "", dimension: "", difficulty: "medium", question_text: "", reference_answer: "" });
const promptForm = reactive({ prompt_key: "", version: "v1", content: "", is_active: false });
const roleConfigForm = reactive({ role_name: "", dimension_text: "", difficulty: "medium", question_count: 8 });

// computed 不是存一个新值，而是根据现有状态实时推导。
// 用户角色或路由变化后，这些标题、tab、权限按钮都会自动更新。
const isAdmin = computed(() => props.auth.user?.role === "admin");
const isAdminConsole = computed(() => route.params.console === "admin");
const activeSection = computed(() => String(route.params.section || (isAdminConsole.value ? "overview" : "workspace")));
const roleBadge = computed(() => (isAdminConsole.value ? "平台管理员 · 全局视角" : "企业面试官 · 组织视角"));
const consoleTitle = computed(() => (isAdminConsole.value ? "Admin Console" : "Interviewer Console"));
const consoleHeadline = computed(() => (isAdminConsole.value ? "平台运营与 Agent 观测台" : "企业面试业务工作台"));
const consoleDescription = computed(() =>
  isAdminConsole.value
    ? "关注权限、组织、Prompt、模型与 Agent 运行质量。"
    : "关注岗位、候选人、面试任务、题库和报告复盘。",
);

const adminTabs = [
  { value: "overview", label: "平台概览", icon: "01" },
  { value: "runs", label: "Agent 观测", icon: "02" },
  { value: "users", label: "用户权限", icon: "03" },
  { value: "organizations", label: "组织管理", icon: "04" },
  { value: "prompts", label: "Prompt 配置", icon: "05" },
];

const interviewerTabs = [
  { value: "workspace", label: "面试工作台", icon: "01" },
  { value: "candidates", label: "候选人", icon: "02" },
  { value: "interviews", label: "面试任务", icon: "03" },
  { value: "configuration", label: "岗位题库", icon: "04" },
  { value: "reports", label: "面试报告", icon: "05" },
];

const tabs = computed(() => (isAdminConsole.value ? adminTabs : interviewerTabs));
const activeTab = computed(() => tabs.value.find((item) => item.value === activeSection.value));
const normalizedKeyword = computed(() => keyword.value.toLowerCase());

const filteredRuns = computed(() =>
  (platform.runs || []).filter((run) => {
    const text = `${run.run_id || ""} ${run.workflow || ""} ${run.current_node || ""}`.toLowerCase();
    const matchKeyword = !normalizedKeyword.value || text.includes(normalizedKeyword.value);
    const matchStatus = !statusFilter.value || run.status === statusFilter.value;
    return matchKeyword && matchStatus;
  }),
);

const failedRuns = computed(() => (platform.runs || []).filter((run) => ["failed", "error"].includes(run.status)));
const filteredUsers = computed(() =>
  (platform.users || []).filter((user) => {
    const text = `${user.display_name || ""} ${user.email || ""} ${user.role || ""}`.toLowerCase();
    return !normalizedKeyword.value || text.includes(normalizedKeyword.value);
  }),
);

const filteredTasks = computed(() =>
  (platform.interviewTasks || []).filter((task) => {
    const text = `${task.candidate_name || ""} ${task.role_name || ""} ${task.status || ""}`.toLowerCase();
    const matchKeyword = !normalizedKeyword.value || text.includes(normalizedKeyword.value);
    const matchStatus = !statusFilter.value || task.status === statusFilter.value;
    return matchKeyword && matchStatus;
  }),
);

const filteredReports = computed(() =>
  (platform.reports || []).filter((report) => {
    const text = `${report.candidate_name || ""} ${report.role_name || ""}`.toLowerCase();
    return !normalizedKeyword.value || text.includes(normalizedKeyword.value);
  }),
);

const filteredTemplates = computed(() =>
  (platform.configuration.templates || []).filter((item) => `${item.name || ""} ${item.role_name || ""}`.toLowerCase().includes(normalizedKeyword.value)),
);

const filteredQuestions = computed(() =>
  (platform.configuration.questions || []).filter((item) =>
    `${item.question_text || ""} ${item.role_name || ""} ${item.dimension || ""}`.toLowerCase().includes(normalizedKeyword.value),
  ),
);

const averageInterviewScore = computed(() => {
  const scores = (platform.reports || []).map((item) => Number(item.score || 0)).filter((score) => score > 0);
  if (!scores.length) return 0;
  return Math.round(scores.reduce((total, score) => total + score, 0) / scores.length);
});

const currentOrganization = computed(() => {
  const organizationId = props.auth.user?.organization_id;
  return platform.organizations.find((item) => item.id === organizationId)?.name || (isAdmin.value ? "全平台" : "未绑定组织");
});

const statCards = computed(() => {
  if (isAdminConsole.value) {
    return [
      { label: "用户数", value: platform.summary?.users || 0, caption: "全平台账号" },
      { label: "组织数", value: platform.summary?.organizations || 0, caption: "企业租户" },
      { label: "Agent Runs", value: platform.summary?.agent_runs || 0, caption: `失败 ${platform.summary?.failed_runs || 0} 次` },
      { label: "平均延迟", value: `${platform.summary?.average_latency_ms || 0} ms`, caption: "端到端运行" },
    ];
  }
  return [
    { label: "候选人", value: filteredUsers.value.length, caption: "当前组织范围" },
    { label: "面试任务", value: platform.interviewTasks.length, caption: "已沉淀任务" },
    { label: "面试报告", value: platform.reports.length, caption: "可复盘记录" },
    { label: "平均分", value: `${averageInterviewScore.value} 分`, caption: "最近报告" },
  ];
});

watch(
  () => platform.users,
  (users) => {
    users.forEach((user) => {
      roleDrafts[user.id] = user.role;
      organizationDrafts[user.id] = user.organization_id || "";
    });
  },
  { deep: true },
);

watch(
  () => [route.params.console, route.params.section],
  () => {
    if (!tabs.value.some((item) => item.value === activeSection.value)) {
      router.replace(`/platform/${route.params.console}/${tabs.value[0].value}`);
    }
  },
  { immediate: true },
);

onMounted(() => platform.loadDashboard());

function openSection(section) {
  router.push(`/platform/${route.params.console}/${section}`);
}

function shortId(value) {
  return String(value || "").slice(0, 10);
}

function formatDate(value) {
  return value ? new Date(value).toLocaleString("zh-CN") : "-";
}

function formatScore(value) {
  return `${Math.round(Number(value || 0) * 100)}%`;
}

function statusLabel(status) {
  return { completed: "已完成", failed: "失败", running: "运行中", cancelled: "已取消" }[status] || status || "-";
}

function difficultyLabel(value) {
  return { easy: "简单", medium: "中等", hard: "困难" }[value] || value || "-";
}

function organizationName(id) {
  return platform.organizations.find((item) => item.id === id)?.name || "未绑定";
}

async function saveRole(user) {
  if (!window.confirm(`确认将 ${user.email} 调整为 ${roleDrafts[user.id]} 吗？`)) return;
  await platform.updateRole(user.id, roleDrafts[user.id], organizationDrafts[user.id]);
}

async function createOrganization() {
  if (!organizationNameInput.value) return;
  await platform.createOrganization(organizationNameInput.value);
  organizationNameInput.value = "";
}

async function createTemplate() {
  await platform.createTemplate({ ...templateForm });
  templateForm.name = "";
  emit("roles-updated");
}

async function createRoleConfig() {
  const roleName = roleConfigForm.role_name.trim();
  if (!roleName) return;
  const dimensions = roleConfigForm.dimension_text
    .split(/[、,，/]/)
    .map((item) => item.trim())
    .filter(Boolean)
    .map((name) => ({ name, focus: `${name} 相关能力与项目落地经验` }));
  await platform.createTemplate({
    name: `${roleName} 默认面试配置`,
    role_name: roleName,
    difficulty: roleConfigForm.difficulty,
    question_count: roleConfigForm.question_count,
    dimensions,
  });
  roleConfigForm.role_name = "";
  roleConfigForm.dimension_text = "";
  roleConfigForm.difficulty = "medium";
  roleConfigForm.question_count = 8;
  emit("roles-updated");
}

async function createQuestion() {
  await platform.createQuestion({ ...questionForm });
  questionForm.question_text = "";
  emit("roles-updated");
}

async function createPrompt() {
  await platform.createPrompt({ ...promptForm });
  promptForm.content = "";
}

const RunTable = defineComponent({
  props: { runs: { type: Array, default: () => [] } },
  setup(props) {
    return () =>
      props.runs.length
        ? h("div", { class: "platform-table-wrap" }, [
            h("table", { class: "platform-table" }, [
              h("thead", [h("tr", ["Run ID", "工作流", "状态", "当前节点", "耗时", "创建时间"].map((text) => h("th", text)))]),
              h(
                "tbody",
                props.runs.map((run) =>
                  h("tr", { key: run.run_id }, [
                    h("td", [h("code", shortId(run.run_id))]),
                    h("td", run.workflow || "-"),
                    h("td", [h("span", { class: ["run-status", `status-${run.status}`] }, statusLabel(run.status))]),
                    h("td", run.current_node || "-"),
                    h("td", `${run.latency_ms || 0} ms`),
                    h("td", formatDate(run.created_at)),
                  ]),
                ),
              ),
            ]),
          ])
        : h("div", { class: "platform-empty" }, "暂无 Agent 运行记录。");
  },
});

const UserTable = defineComponent({
  props: {
    users: { type: Array, default: () => [] },
    organizations: { type: Array, default: () => [] },
    editable: { type: Boolean, default: false },
    roleDrafts: { type: Object, required: true },
    organizationDrafts: { type: Object, required: true },
  },
  emits: ["save-role"],
  setup(props, { emit }) {
    return () =>
      props.users.length
        ? h("div", { class: "platform-table-wrap" }, [
            h("table", { class: "platform-table" }, [
              h("thead", [
                h("tr", ["用户", "邮箱", "角色", "组织", props.editable ? "操作" : ""].filter(Boolean).map((text) => h("th", text))),
              ]),
              h(
                "tbody",
                props.users.map((user) =>
                  h("tr", { key: user.id }, [
                    h("td", user.display_name || "-"),
                    h("td", user.email || "-"),
                    h("td", roleLabel(user.role)),
                    h("td", organizationName(user.organization_id)),
                    props.editable
                      ? h("td", [
                          h("div", { class: "inline-control-row" }, [
                            h(
                              "select",
                              {
                                class: "compact-select",
                                value: props.roleDrafts[user.id],
                                onChange: (event) => {
                                  props.roleDrafts[user.id] = event.target.value;
                                },
                              },
                              [
                                h("option", { value: "candidate" }, "候选人"),
                                h("option", { value: "interviewer" }, "企业面试官"),
                                h("option", { value: "admin" }, "平台管理员"),
                              ],
                            ),
                            h(
                              "select",
                              {
                                class: "compact-select",
                                value: props.organizationDrafts[user.id],
                                onChange: (event) => {
                                  props.organizationDrafts[user.id] = event.target.value;
                                },
                              },
                              [
                                h("option", { value: "" }, "无组织"),
                                ...props.organizations.map((organization) =>
                                  h("option", { value: organization.id, key: organization.id }, organization.name),
                                ),
                              ],
                            ),
                            h("button", { class: "text-button", onClick: () => emit("save-role", user) }, "保存"),
                          ]),
                        ])
                      : null,
                  ]),
                ),
              ),
            ]),
          ])
        : h("div", { class: "platform-empty" }, "暂无用户数据。");
  },
});

const InterviewTaskTable = defineComponent({
  props: { tasks: { type: Array, default: () => [] } },
  setup(props) {
    return () =>
      props.tasks.length
        ? h("div", { class: "platform-table-wrap" }, [
            h("table", { class: "platform-table" }, [
              h("thead", [h("tr", ["候选人", "岗位", "状态", "得分", "时间"].map((text) => h("th", text)))]),
              h(
                "tbody",
                props.tasks.map((task) =>
                  h("tr", { key: task.id }, [
                    h("td", task.candidate_name || "-"),
                    h("td", task.role_name || "-"),
                    h("td", [h("span", { class: ["run-status", `status-${task.status}`] }, statusLabel(task.status))]),
                    h("td", task.score || 0),
                    h("td", formatDate(task.created_at)),
                  ]),
                ),
              ),
            ]),
          ])
        : h("div", { class: "platform-empty" }, "暂无面试任务。");
  },
});

const ReportList = defineComponent({
  props: { reports: { type: Array, default: () => [] } },
  setup(props) {
    return () =>
      props.reports.length
        ? h(
            "div",
            { class: "report-card-list" },
            props.reports.map((report) =>
              h("article", { class: "report-card-item", key: report.id }, [
                h("div", [h("strong", `${report.candidate_name || "候选人"} · ${report.role_name || "未命名岗位"}`), h("p", formatDate(report.created_at))]),
                h("span", `${report.score || 0} 分`),
                h("small", `${report.citation_count || 0} 条引用`),
              ]),
            ),
          )
        : h("div", { class: "platform-empty" }, "暂无报告。");
  },
});
</script>
