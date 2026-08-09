<template>
  <AuthPanel
    :auth-mode="authMode"
    :login-form="loginForm"
    :register-form="registerForm"
    :loading-action="loadingAction"
    :error-message="errorMessage"
    @update:authMode="emit('update:authMode', $event)"
    @update:loginForm="emit('update:loginForm', $event)"
    @update:registerForm="emit('update:registerForm', $event)"
    @login="emit('login')"
    @register="emit('register')"
  />
</template>

<script setup>
import AuthPanel from "../components/AuthPanel.vue";

// View 层可以理解成页面中转层：
// 上面承接 App.vue / composable，下面承接真正的展示组件。
defineProps({
  authMode: { type: String, default: "login" },
  loginForm: { type: Object, required: true },
  registerForm: { type: Object, required: true },
  loadingAction: { type: String, default: "" },
  errorMessage: { type: String, default: "" },
});

const emit = defineEmits(["update:authMode", "update:loginForm", "update:registerForm", "login", "register"]);
</script>
