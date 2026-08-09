<template>
  <!-- 项目/会话树组件：负责展示项目空间、会话列表、创建/重命名/删除等操作入口。 -->
  <div class="workspace-section">
    <form v-if="showProjectForm" class="workspace-inline-form" @submit.prevent="submitProject">
      <!-- v-model.trim 是很典型的 Vue 表单写法：
           v-model 做双向绑定，.trim 会自动去掉首尾空格。 -->
      <input v-model.trim="projectName" class="text-input" placeholder="请输入项目名称" />
      <div class="workspace-inline-actions">
        <button class="primary-button compact-button" type="submit">创建项目</button>
      </div>
    </form>

    <!-- 如果没有用户创建的项目，只展示默认会话，降低首次使用成本。 -->
    <div v-if="!visibleProjects.length" class="workspace-tree">
      <form
        v-if="showDefaultConversationForm && defaultProject"
        class="workspace-inline-form compact"
        @submit.prevent="submitConversation(defaultProject.id)"
      >
        <input v-model.trim="conversationName" class="text-input" placeholder="请输入会话名称" />
        <div class="workspace-inline-actions">
          <button class="primary-button compact-button" type="submit">创建会话</button>
        </div>
      </form>
      <div v-if="defaultConversation" class="conversation-item">
        <button
          :class="['conversation-chip', activeConversationId === defaultConversation.id ? 'active' : '']"
          @click="emit('activate-conversation', defaultConversation.id)"
        >
          <div class="conversation-chip-main">
            <strong>{{ defaultConversation.name || "默认会话" }}</strong>
          </div>
        </button>
      </div>
      <div v-else class="mini-empty-card">暂无会话。</div>
    </div>

    <!-- 有项目后，按“项目 -> 会话”的树形结构展示。 -->
    <div v-else class="workspace-tree">
      <article
        v-for="project in visibleProjects"
        :key="project.id"
        :class="[
          'workspace-project-card',
          activeProjectId === project.id ? 'active' : '',
          hoveredProjectId === project.id ? 'hovering' : '',
        ]"
        @mouseenter="hoveredProjectId = project.id"
        @mouseleave="hoveredProjectId = ''"
      >
        <div class="workspace-item-row">
          <!-- 项目折叠按钮：展开时向下箭头，收起时向右箭头。 -->
          <button class="workspace-project-toggle" type="button" @click="toggleProjectOpen(project)">
            {{ isProjectOpen(project) ? "⌄" : ">" }}
          </button>
          <button class="workspace-item-main" type="button" @click="toggleProjectOpen(project)">
            <strong>{{ project.name }}</strong>
          </button>
          <!-- 项目工具栏：只在悬停或正在新建会话时显示，避免侧边栏过挤。 -->
          <div
            v-show="hoveredProjectId === project.id || showConversationFormFor === project.id"
            class="project-action-cluster"
          >
            <button
              class="icon-tool-button"
              :title="showConversationFormFor === project.id ? '收起新建会话' : '新建会话'"
              @click="toggleConversationForm(project.id)"
            >
              +
            </button>
            <button
              class="icon-tool-button"
              :title="project.pinned ? '取消置顶项目' : '置顶项目'"
              @click="emit('toggle-pin-project', project.id)"
            >
              {{ project.pinned ? "★" : "☆" }}
            </button>
            <button class="icon-tool-button" title="重命名项目" @click="beginEditProject(project)">✎</button>
            <button class="icon-tool-button danger" title="删除项目" @click="emit('delete-project', project.id)">×</button>
          </div>
        </div>

        <form v-if="editingProjectId === project.id" class="workspace-inline-form compact" @submit.prevent="submitProjectRename(project.id)">
          <input v-model.trim="editingProjectName" class="text-input" placeholder="输入新的项目名称" />
          <div class="workspace-inline-actions">
            <button class="ghost-button compact-button" type="button" @click="cancelProjectEdit">取消</button>
            <button class="primary-button compact-button" type="submit">保存</button>
          </div>
        </form>

        <div v-show="isProjectOpen(project)" class="workspace-conversations">
          <form v-if="showConversationFormFor === project.id" class="workspace-inline-form compact" @submit.prevent="submitConversation(project.id)">
            <input v-model.trim="conversationName" class="text-input" placeholder="请输入会话名称" />
            <div class="workspace-inline-actions">
              <button class="primary-button compact-button" type="submit">创建会话</button>
            </div>
          </form>

          <div v-if="!project.conversations.length" class="mini-empty-card compact-empty-line">暂无会话。</div>

          <!-- 会话工具栏：悬浮在当前会话右侧，点击图标触发置顶、重命名、删除。 -->
          <div
            v-for="conversation in project.conversations"
            :key="conversation.id"
            :class="['conversation-item', hoveredConversationId === conversation.id ? 'hovering' : '']"
            @mouseenter="hoveredConversationId = conversation.id"
            @mouseleave="hoveredConversationId = ''"
          >
            <button
              :class="['conversation-chip', activeConversationId === conversation.id ? 'active' : '']"
              @click="emit('activate-conversation', conversation.id)"
            >
              <div class="conversation-chip-main">
                <strong>{{ conversation.name }}</strong>
              </div>
            </button>

            <div
              v-show="hoveredConversationId === conversation.id || activeConversationId === conversation.id"
              class="conversation-tool-row workspace-tools-popover floating-conversation-tools"
            >
              <button class="icon-tool-button" :title="conversation.pinned ? '取消置顶' : '置顶会话'" @click="emit('toggle-pin-conversation', conversation.id)">
                {{ conversation.pinned ? "★" : "☆" }}
              </button>
              <button class="icon-tool-button" title="重命名" @click="beginEditConversation(conversation)">✎</button>
              <button class="icon-tool-button danger" title="删除" @click="emit('delete-conversation', conversation.id)">×</button>
            </div>
          </div>

          <form
            v-if="editingConversationId && project.conversations.some((item) => item.id === editingConversationId)"
            class="workspace-inline-form compact"
            @submit.prevent="submitConversationRename(editingConversationId)"
          >
            <input v-model.trim="editingConversationName" class="text-input" placeholder="输入新的会话名称" />
            <div class="workspace-inline-actions">
              <button class="ghost-button compact-button" type="button" @click="cancelConversationEdit">取消</button>
              <button class="primary-button compact-button" type="submit">保存</button>
            </div>
          </form>
        </div>
      </article>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from "vue";

const props = defineProps({
  // projects 来自后端工作区数据，结构是 project.conversations。
  projects: { type: Array, default: () => [] },
  activeProjectId: { type: String, default: "" },
  activeConversationId: { type: String, default: "" },
  // 父组件通过改变 key 来触发本组件打开“新建项目/新建会话”表单。
  createProjectKey: { type: Number, default: 0 },
  createConversationKey: { type: Number, default: 0 },
});

const emit = defineEmits([
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

// 这些都是局部表单 / hover 状态，用 ref 最合适。
// ref 常用于字符串、布尔值、数字这类简单状态；模板里会自动解包，不需要 .value。
const showProjectForm = ref(false);
const projectName = ref("");
const showConversationFormFor = ref("");
const showDefaultConversationForm = ref(false);
const conversationName = ref("");
const editingProjectId = ref("");
const editingProjectName = ref("");
const editingConversationId = ref("");
const editingConversationName = ref("");
const hoveredProjectId = ref("");
const hoveredConversationId = ref("");
const openedProjectIds = ref({});

// computed 用来从 props.projects 推导数据：默认项目、默认会话、可见项目列表。
// 它有缓存，依赖不变时不会反复计算。
const defaultProject = computed(() => props.projects.find((project) => project.name === "默认项目") || null);
const defaultConversation = computed(() => defaultProject.value?.conversations?.[0] || null);
const visibleProjects = computed(() => props.projects.filter((project) => project.name !== "默认项目"));

watch(
  () => [props.projects, props.activeProjectId],
  () => {
    // 当前激活项目默认展开，让用户切换会话后能看到自己在哪个项目里。
    if (props.activeProjectId && openedProjectIds.value[props.activeProjectId] !== false) {
      openedProjectIds.value = { ...openedProjectIds.value, [props.activeProjectId]: true };
    }
  },
  { immediate: true, deep: true },
);

watch(
  () => props.createProjectKey,
  (value, oldValue) => {
    // 父组件点击“新建项目”后 key 会变化，本组件 watch 到变化就打开表单。
    if (value !== oldValue) {
      showProjectForm.value = true;
    }
  },
);

watch(
  () => props.createConversationKey,
  (value, oldValue) => {
    // 新建会话有两种情况：没有项目时挂到默认项目；有项目时挂到当前项目。
    if (value === oldValue) return;
    conversationName.value = "";
    if (!visibleProjects.value.length) {
      showDefaultConversationForm.value = true;
      return;
    }
    const targetProject =
      visibleProjects.value.find((project) => project.id === props.activeProjectId) ||
      visibleProjects.value[0];
    if (targetProject) {
      openedProjectIds.value = { ...openedProjectIds.value, [targetProject.id]: true };
      showConversationFormFor.value = targetProject.id;
    }
  },
);

function isProjectOpen(project) {
  if (openedProjectIds.value[project.id] === undefined) {
    return project.id === props.activeProjectId;
  }
  return Boolean(openedProjectIds.value[project.id]);
}

// 展开/收起项目只影响前端展示，不会请求后端。
function toggleProjectOpen(project) {
  openedProjectIds.value = {
    ...openedProjectIds.value,
    [project.id]: !isProjectOpen(project),
  };
}

function toggleProjectForm() {
  showProjectForm.value = !showProjectForm.value;
  if (!showProjectForm.value) {
    projectName.value = "";
  }
}

function submitProject() {
  // 简单校验：项目名为空时不提交。真正的创建由父组件调用后端接口。
  if (!projectName.value) return;
  emit("create-project", projectName.value);
  projectName.value = "";
  showProjectForm.value = false;
}

function beginEditProject(project) {
  // 进入编辑态时，把当前名称拷贝到输入框。
  editingProjectId.value = project.id;
  editingProjectName.value = project.name;
}

function cancelProjectEdit() {
  editingProjectId.value = "";
  editingProjectName.value = "";
}

function submitProjectRename(projectId) {
  if (!editingProjectName.value) return;
  emit("rename-project", projectId, editingProjectName.value);
  cancelProjectEdit();
}

function toggleConversationForm(projectId) {
  showConversationFormFor.value = showConversationFormFor.value === projectId ? "" : projectId;
  showDefaultConversationForm.value = false;
  conversationName.value = "";
}

function submitConversation(projectId) {
  // 创建会话同样只抛事件，接口请求集中放在 useInterviewApp 里。
  if (!conversationName.value) return;
  emit("create-conversation", projectId, conversationName.value);
  conversationName.value = "";
  showConversationFormFor.value = "";
  showDefaultConversationForm.value = false;
}

function beginEditConversation(conversation) {
  editingConversationId.value = conversation.id;
  editingConversationName.value = conversation.name;
}

function cancelConversationEdit() {
  editingConversationId.value = "";
  editingConversationName.value = "";
}

function submitConversationRename(conversationId) {
  if (!editingConversationName.value) return;
  emit("rename-conversation", conversationId, editingConversationName.value);
  cancelConversationEdit();
}
</script>
