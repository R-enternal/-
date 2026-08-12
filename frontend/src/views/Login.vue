<template>
  <div class="login-page">
    <div class="glow glow-a"></div>
    <div class="glow glow-b"></div>

    <div class="login-card">
      <div class="brand">
        <div class="brand-mark">仓</div>
        <div>
          <h1 class="title">仓脉智诊</h1>
          <p class="subtitle">轻量化 AI 仓储设备智能维检平台</p>
        </div>
      </div>

      <el-form :model="form" @submit.prevent="handleLogin">
        <el-form-item>
          <el-input v-model="form.username" placeholder="用户名" size="large" :prefix-icon="User" />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            size="large"
            show-password
            :prefix-icon="Lock"
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        <el-button type="primary" class="submit-btn" size="large" :loading="loading" @click="handleLogin">
          登 录
        </el-button>
      </el-form>

      <div class="tips">
        <span>演示账号：admin / admin123</span>
        <span class="dot">·</span>
        <span>worker / worker123</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from "vue";
import { Lock, User } from "@element-plus/icons-vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";

import { authApi } from "../api/modules";
import { useUserStore } from "../store/user";

const router = useRouter();
const userStore = useUserStore();
const loading = ref(false);
const form = reactive({ username: "admin", password: "admin123" });

async function handleLogin() {
  loading.value = true;
  try {
    const result = await authApi.login(form);
    userStore.setLogin(result.token, result.user);
    ElMessage.success("登录成功");
    router.push("/");
  } catch {
    // 错误提示由拦截器统一处理
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.login-page {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(ellipse 60% 45% at 20% 15%, rgba(14, 165, 233, 0.1), transparent),
    radial-gradient(ellipse 55% 40% at 85% 85%, rgba(59, 130, 246, 0.1), transparent),
    linear-gradient(160deg, #eef4fb 0%, #f6f8fd 55%, #eef2fa 100%);
  position: relative;
  overflow: hidden;
}
.glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(90px);
  opacity: 0.16;
  pointer-events: none;
}
.glow-a {
  width: 360px;
  height: 360px;
  background: #7dd3fc;
  top: -120px;
  left: -80px;
}
.glow-b {
  width: 420px;
  height: 420px;
  background: #93c5fd;
  bottom: -160px;
  right: -100px;
}

.login-card {
  position: relative;
  width: 400px;
  padding: 34px 34px 26px;
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid var(--border);
  border-radius: 16px;
  box-shadow: 0 18px 48px rgba(15, 23, 42, 0.1);
  backdrop-filter: blur(8px);
}
.brand {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 26px;
}
.brand-mark {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  background: linear-gradient(135deg, #22d3ee, #0ea5e9);
  color: #04121f;
  font-size: 28px;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 24px rgba(14, 165, 233, 0.35);
  flex-shrink: 0;
}
.title {
  font-size: 26px;
  font-weight: 800;
  letter-spacing: 2px;
}
.subtitle {
  color: var(--text-sub);
  font-size: 13px;
  margin-top: 2px;
}
.submit-btn {
  width: 100%;
  margin-top: 4px;
  font-size: 15px;
  letter-spacing: 6px;
  background: linear-gradient(90deg, #0ea5e9, #0284c7);
  border: none;
}
.submit-btn:hover {
  background: linear-gradient(90deg, #38bdf8, #0284c7);
  box-shadow: 0 6px 20px rgba(14, 165, 233, 0.3);
}
.tips {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 8px;
  margin-top: 18px;
  color: #94a3b8;
  font-size: 12px;
}
.dot {
  color: #cbd5e1;
}
</style>
