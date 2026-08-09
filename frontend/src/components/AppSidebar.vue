<template>
  <!-- AppSidebar 是左侧工作台导航，不直接请求后端，只把用户操作通过 emit 抛给 App.vue/composable。 -->
  <aside class="sidebar">
    <div class="sidebar-hero">
      <span class="sidebar-eyebrow">Interview Coach</span>
      <div class="sidebar-brand-row">
        <div class="sidebar-brand">智能面试辅导系统</div>
        <button class="sidebar-icon-button" title="返回首页" @click="emit('go-landing')">⌂</button>
      </div>
    </div>

    <section class="sidebar-section">
      <div class="user-card sidebar-brand-row">
        <div>
          <div class="user-name">{{ auth.user?.display_name || "未登录" }}</div>
          <div class="user-email">{{ auth.user?.email || "" }}</div>
        </div>
        <button class="sidebar-icon-button" title="退出登录" :disabled="loadingAction === 'logout'" @click="emit('logout')">
          {{ loadingAction === "logout" ? "…" : "↗" }}
        </button>
      </div>
    </section>

    <!-- 只有面试官和管理员能看到后台入口，普通候选人不会展示。 -->
    <section v-if="['interviewer', 'admin'].includes(auth.user?.role)" class="sidebar-section">
      <button class="sidebar-section-toggle" @click="toggleSection('platform')">
        <span>角色后台</span>
        <b>{{ expandedSections.platform ? "⌄" : ">" }}</b>
      </button>
      <div v-show="expandedSections.platform" class="sidebar-section-body">
        <button v-if="auth.user?.role === 'admin'" class="mode-button platform-entry-button" @click="emit('open-platform', 'admin')">
          平台管理
        </button>
        <button class="mode-button platform-entry-button" @click="emit('open-platform', 'interviewer')">
          {{ auth.user?.role === 'admin' ? '面试业务' : '企业面试官后台' }}
        </button>
      </div>
    </section>

    <!-- 知识库导入：文件选择交给 input，真正上传和解析由父组件调用后端接口完成。 -->
    <section class="sidebar-section">
      <button class="sidebar-section-toggle" @click="toggleSection('knowledge')">
        <span>知识库</span>
        <b>{{ expandedSections.knowledge ? "⌄" : ">" }}</b>
      </button>
      <div v-show="expandedSections.knowledge" class="sidebar-section-body">
        <button class="sidebar-action-button full" :disabled="loadingAction === 'knowledge'" @click="emit('import-knowledge')">
          {{ loadingAction === "knowledge" ? "导入中..." : "导入知识库" }}
        </button>
        <input
          class="file-input"
          type="file"
          multiple
          accept=".pdf,.txt,.md,.docx"
          @change="emit('knowledge-files-change', Array.from($event.target.files || []))"
        />
      </div>
    </section>

    <!-- 项目空间：项目和会话都来自后端/Pinia 状态，这里只负责展示和触发创建、重命名、删除等事件。 -->
    <section class="sidebar-section workspace-section-wrap">
      <div class="sidebar-section-toggle sidebar-section-title-row">
        <button class="sidebar-section-title-button" @click="toggleSection('workspace')">
          <span>项目空间</span>
          <b>{{ expandedSections.workspace ? "⌄" : ">" }}</b>
        </button>
        <div class="sidebar-create-menu">
          <button class="sidebar-icon-button workspace-create-trigger" type="button" title="新建" @click.stop>+</button>
          <div class="sidebar-create-popover">
            <button type="button" title="新建项目" @click.stop="workspaceCreateKey += 1">新建项目</button>
            <button type="button" title="新建会话" @click.stop="workspaceConversationCreateKey += 1">新建会话</button>
          </div>
        </div>
      </div>
      <WorkspaceExplorer
        v-show="expandedSections.workspace"
        :create-project-key="workspaceCreateKey"
        :create-conversation-key="workspaceConversationCreateKey"
        :projects="workspace.projects"
        :active-project-id="workspace.active_project_id"
        :active-conversation-id="workspace.active_conversation_id"
        @create-project="emit('create-project', $event)"
        @activate-project="emit('activate-project', $event)"
        @rename-project="forwardRenameProject"
        @toggle-pin-project="emit('toggle-pin-project', $event)"
        @delete-project="emit('delete-project', $event)"
        @create-conversation="forwardCreateConversation"
        @activate-conversation="emit('activate-conversation', $event)"
        @rename-conversation="forwardRenameConversation"
        @toggle-pin-conversation="emit('toggle-pin-conversation', $event)"
        @delete-conversation="emit('delete-conversation', $event)"
      />
    </section>

    <!-- 工作台模式：点击后会触发 open-mode，App.vue 再负责改路由和同步 mode。 -->
    <section class="sidebar-section">
      <button class="sidebar-section-toggle" @click="toggleSection('mode')">
        <span>工作台模式</span>
        <b>{{ expandedSections.mode ? "⌄" : ">" }}</b>
      </button>
      <div v-show="expandedSections.mode" class="mode-switcher sidebar-section-body">
        <button :class="['mode-button', mode === QA_MODE ? 'active' : '']" @click="emit('open-mode', QA_MODE)">
          <span>01</span>
          问答模式
        </button>
        <button :class="['mode-button', mode === INTERVIEW_MODE ? 'active' : '']" @click="emit('open-mode', INTERVIEW_MODE)">
          <span>02</span>
          模拟面试
        </button>
        <button :class="['mode-button', mode === HISTORY_MODE ? 'active' : '']" @click="emit('open-mode', HISTORY_MODE)">
          <span>03</span>
          历史记录
        </button>
      </div>
    </section>

    <!-- LangSmith 调试开关：用于观察 LLM/Agent 执行链路，配置仍然只保存在前端状态和后端环境中。 -->
    <section class="sidebar-section langsmith-hover-panel">
      <button class="sidebar-section-toggle" @click="toggleSection('langsmith')">
        <span>LangSmith</span>
        <b>{{ expandedSections.langsmith ? "⌄" : ">" }}</b>
      </button>
      <div class="sidebar-section-body langsmith-compact-row">
        <label class="checkbox-row">
          <input
            type="checkbox"
            :checked="langsmith.enabled"
            @change="emit('update:langsmith', { ...langsmith, enabled: $event.target.checked })"
          />
          <span>开启调试</span>
        </label>
      </div>

      <div v-show="expandedSections.langsmith" class="langsmith-hover-content">
        <input
          class="text-input"
          type="password"
          placeholder="LangSmith API Key"
          :value="langsmith.api_key"
          @input="emit('update:langsmith', { ...langsmith, api_key: $event.target.value })"
        />
        <input
          class="text-input"
          placeholder="LangSmith Project"
          :value="langsmith.project"
          @input="emit('update:langsmith', { ...langsmith, project: $event.target.value })"
        />
        <button class="primary-button-2" :disabled="loadingAction === 'langsmith'" @click="emit('save-langsmith')">
          {{ loadingAction === "langsmith" ? "应用中..." : "应用 LangSmith 设置" }}
        </button>
        <div class="mini-tip">{{ langsmithStatus }}</div>
      </div>
    </section>

    <section class="sidebar-section">
      <button class="sidebar-section-toggle" @click="toggleSection('history')">
        <span>历史概览</span>
        <b>{{ expandedSections.history ? "⌄" : ">" }}</b>
      </button>
      <div v-show="expandedSections.history" class="mini-tip sidebar-section-body">累计历史面试记录：{{ historyCount }} 条</div>
    </section>
  </aside>
</template>

<script setup>
import { reactive, ref } from "vue";
import { HISTORY_MODE, INTERVIEW_MODE, QA_MODE } from "../constants.js";
import WorkspaceExplorer from "./WorkspaceExplorer.vue";

defineProps({
  auth: { type: Object, required: true },
  workspace: { type: Object, required: true },
  langsmith: { type: Object, required: true },
  langsmithStatus: { type: String, default: "" },
  loadingAction: { type: String, default: "" },
  mode: { type: String, default: QA_MODE },
  historyCount: { type: Number, default: 0 },
  themeMode: { type: String, default: "serious" },
});

const emit = defineEmits([
  "logout",
  "go-landing",
  "open-mode",
  "open-platform",
  "knowledge-files-change",
  "import-knowledge",
  "update:langsmith",
  "save-langsmith",
  "create-project",
  "activate-project",
  "rename-project",
  "toggle-pin-project",
  "delete-project",
  "create-conversation",
  "activate-conversation",
  "rename-conversation",
  "toggle-pin-conversation",
  "delete-conversation",
]);

// 侧栏分组只影响本组件展示，属于局部 UI 状态。
// reactive 适合管理对象形式的响应式数据，例如多个折叠面板的展开/收起状态。
const expandedSections = reactive({
  platform: true,
  knowledge: false,
  workspace: true,
  mode: true,
  langsmith: false,
  history: false,
});

// 这两个 key 不是业务 ID，而是“触发器”。
// 父组件点击新建时让 key +1，子组件 watch 到变化后弹出创建输入框。
const workspaceCreateKey = ref(0);
const workspaceConversationCreateKey = ref(0);

function toggleSection(key) {
  expandedSections[key] = !expandedSections[key];
}

// forward 函数只是事件转发：子组件 WorkspaceExplorer 抛事件，本组件再继续抛给 App.vue。
// 这样可以保持组件层级清晰，不让深层组件直接知道全局业务逻辑。
function forwardRenameProject(projectId, name) {
  emit("rename-project", projectId, name);
}

function forwardCreateConversation(projectId, name) {
  emit("create-conversation", projectId, name);
}

function forwardRenameConversation(conversationId, name) {
  emit("rename-conversation", conversationId, name);
}
</script>
