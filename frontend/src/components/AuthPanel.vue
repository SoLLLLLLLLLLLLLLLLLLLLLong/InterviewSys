<template>
  <div class="entry-shell">
    <div class="entry-card auth-card">
      <div class="entry-eyebrow">智能面试辅导系统</div>
      <h1>先登录，再进入你的专属面试工作台</h1>
      <p>当前系统支持邮箱 + 密码登录、用户隔离、历史记录留存和面试报告留存。</p>

      <div class="auth-switcher">
        <!-- 这里通过条件状态切换“登录 / 注册”两种认证视图。
             本质上还是一个页面，只是根据 authMode 改变展示内容。 -->
        <button :class="['mode-button', authMode === 'login' ? 'active' : '']" @click="emit('update:authMode', 'login')">
          登录
        </button>
        <button :class="['mode-button', authMode === 'register' ? 'active' : '']" @click="emit('update:authMode', 'register')">
          注册
        </button>
      </div>

      <input
        v-if="authMode === 'register'"
        :value="registerForm.display_name"
        class="text-input entry-input"
        placeholder="请输入用户名"
        @input="emit('update:registerForm', { ...registerForm, display_name: $event.target.value })"
      />

      <input
        :value="authMode === 'login' ? loginForm.email : registerForm.email"
        class="text-input entry-input"
        placeholder="请输入邮箱"
        @input="handleEmailInput"
      />

      <input
        :value="authMode === 'login' ? loginForm.password : registerForm.password"
        class="text-input entry-input"
        type="password"
        placeholder="请输入密码"
        @input="handlePasswordInput"
        @keyup.enter="authMode === 'login' ? emit('login') : emit('register')"
      />

      <button
        class="primary-button entry-button"
        :disabled="loadingAction === 'login' || loadingAction === 'register'"
        @click="authMode === 'login' ? emit('login') : emit('register')"
      >
        {{
          authMode === "login"
            ? loadingAction === "login"
              ? "登录中..."
              : "登录系统"
            : loadingAction === "register"
              ? "注册中..."
              : "注册并进入"
        }}
      </button>

      <div v-if="errorMessage" class="error-banner entry-error">{{ errorMessage }}</div>
    </div>
  </div>
</template>

<script setup>
// <script setup> 是 Vue 3 里更现代的写法。
// 相比 export default，它更适合把模板直接用到的变量和函数平铺暴露出来，
// 写起来更简洁，也更符合现在多数 Vue 3 工程的风格。
const props = defineProps({
  // 这是一个“受控表单组件”：
  // 表单值不在组件内部长期保存，而是由上层 store 统一管理。
  authMode: {
    type: String,
    default: "login",
  },
  loginForm: {
    type: Object,
    required: true,
  },
  registerForm: {
    type: Object,
    required: true,
  },
  loadingAction: {
    type: String,
    default: "",
  },
  errorMessage: {
    type: String,
    default: "",
  },
});

// 组件通信方式：
// - defineProps：父传子
// - defineEmits：子传父
const emit = defineEmits(["update:authMode", "update:loginForm", "update:registerForm", "login", "register"]);

function handleEmailInput(event) {
  const value = event.target.value;
  if (props.authMode === "login") {
    emit("update:loginForm", { ...props.loginForm, email: value });
    return;
  }
  emit("update:registerForm", { ...props.registerForm, email: value });
}

function handlePasswordInput(event) {
  const value = event.target.value;
  if (props.authMode === "login") {
    emit("update:loginForm", { ...props.loginForm, password: value });
    return;
  }
  emit("update:registerForm", { ...props.registerForm, password: value });
}
</script>
