<template>
  <div class="layout">
    <!-- 左侧图标导航 -->
    <aside class="rail">
      <div class="brand">
        <div class="brand-mark">仓</div>
        <div class="brand-text">
          <div class="brand-name">仓脉智诊</div>
          <div class="brand-sub">智能维检平台</div>
        </div>
      </div>
      <nav class="nav">
        <router-link
          v-for="item in navs"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          :class="{ active: $route.path === item.path }"
          :title="item.label"
        >
          <el-icon :size="20"><component :is="item.icon" /></el-icon>
          <span class="nav-label">{{ item.label }}</span>
        </router-link>
      </nav>
      <div class="rail-footer">v0.1</div>
    </aside>

    <div class="main-col">
      <!-- 顶栏 -->
      <header class="header">
        <div class="header-left">
          <div class="page-title">{{ $route.meta.title }}</div>
          <div class="page-sub">{{ $route.meta.sub }}</div>
        </div>
        <div class="header-right">
          <el-popover
            placement="bottom-end"
            :width="360"
            trigger="click"
            popper-class="notify-popper"
          >
            <template #reference>
              <div class="bell-wrap">
                <el-badge :value="unread" :hidden="!unread" :max="99" class="bell-badge">
                  <el-icon :size="19" class="bell-icon"><Bell /></el-icon>
                </el-badge>
              </div>
            </template>
            <div class="notify-head">
              <span>通知中心</span>
              <el-button v-if="unread" size="small" text type="primary" @click="markAllRead">
                全部已读
              </el-button>
            </div>
            <div class="notify-list">
              <div v-for="n in notifications" :key="n.id" class="notify-item" @click="markRead(n)">
                <span class="notify-dot" :class="notifyColor(n.notify_type)"></span>
                <div class="notify-body">
                  <div class="notify-title">{{ n.title }}</div>
                  <div class="notify-content">{{ n.content }}</div>
                  <div class="notify-time">{{ (n.created_at || "").slice(0, 16).replace("T", " ") }}</div>
                </div>
              </div>
              <el-empty v-if="!notifications.length" description="暂无通知" :image-size="60" />
            </div>
          </el-popover>

          <el-dropdown trigger="click" @command="handleUserCommand">
            <span class="user-wrap">
              <el-icon :size="17"><UserFilled /></el-icon>
              <span class="user-name">{{ userStore.user?.real_name || userStore.user?.username || "未登录" }}</span>
              <el-icon :size="12" class="muted"><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">
                  <el-icon><SwitchButton /></el-icon>退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <!-- 全局 KPI 指标条：打开任何页面都能一眼看到核心指标 -->
      <div class="kpi-zone">
        <div class="kpi-strip">
          <div v-for="k in kpis" :key="k.label" class="kpi-card" @click="router.push(k.to)">
            <div class="kpi-icon" :class="k.color">
              <el-icon :size="19"><component :is="k.icon" /></el-icon>
            </div>
            <div>
              <div class="kpi-value">{{ k.value }}</div>
              <div class="kpi-label">{{ k.label }}</div>
            </div>
          </div>
        </div>
      </div>

      <main class="main">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import {
  ArrowDown,
  Bell,
  BellFilled,
  Box,
  ChatDotRound,
  CircleCheck,
  Cpu,
  Collection,
  Monitor,
  SwitchButton,
  Tickets,
  UserFilled,
} from "@element-plus/icons-vue";

import { notificationApi, overviewApi } from "../api/modules";
import { useUserStore } from "../store/user";

const router = useRouter();
const userStore = useUserStore();

const navs = [
  { path: "/dashboard", label: "监测看板", icon: Monitor },
  { path: "/devices", label: "设备管理", icon: Cpu },
  { path: "/alerts", label: "告警中心", icon: BellFilled },
  { path: "/work-orders", label: "工单管理", icon: Tickets },
  { path: "/spare-parts", label: "备件库存", icon: Box },
  { path: "/agent", label: "智能助手", icon: ChatDotRound },
  { path: "/knowledge-base", label: "知识库", icon: Collection },
];

const stats = ref({
  devices: { total: 0, RUNNING: 0 },
  health: { HEALTHY: 0 },
  alerts: { pending: 0 },
  work_orders: { pending_assign: 0, in_progress: 0, pending_accept: 0 },
  spare_parts: { low_stock: 0 },
});
const unread = ref(0);
const notifications = ref([]);

const kpis = computed(() => [
  {
    label: "设备总数",
    value: stats.value.devices.total,
    icon: Monitor,
    color: "cyan",
    to: "/devices",
  },
  {
    label: "运行中设备",
    value: stats.value.devices.RUNNING,
    icon: Cpu,
    color: "blue",
    to: "/devices",
  },
  {
    label: "健康设备",
    value: stats.value.health.HEALTHY,
    icon: CircleCheck,
    color: "green",
    to: "/dashboard",
  },
  {
    label: "待处理告警",
    value: stats.value.alerts.pending,
    icon: BellFilled,
    color: "red",
    to: "/alerts",
  },
  {
    label: "待办工单",
    value:
      stats.value.work_orders.pending_assign +
      stats.value.work_orders.in_progress +
      stats.value.work_orders.pending_accept,
    icon: Tickets,
    color: "yellow",
    to: "/work-orders",
  },
  {
    label: "低库存备件",
    value: stats.value.spare_parts.low_stock,
    icon: Box,
    color: "orange",
    to: "/spare-parts",
  },
]);

let timer = null;

async function fetchStats() {
  try {
    stats.value = await overviewApi.stats();
  } catch {
    // 后端未就绪时保留上次数据
  }
}

async function fetchNotifications() {
  try {
    const [count, list] = await Promise.all([
      notificationApi.unreadCount(),
      notificationApi.list({ is_read: false }),
    ]);
    unread.value = count?.unread ?? 0;
    notifications.value = list;
  } catch {
    // 忽略，避免联调期刷屏
  }
}

function notifyColor(type) {
  return { ALERT: "red", WORK_ORDER: "yellow", STOCK: "blue", SYSTEM: "cyan" }[type] || "cyan";
}

async function markRead(n) {
  await notificationApi.markRead({ notification_id: n.id });
  fetchNotifications();
}

async function markAllRead() {
  await notificationApi.markRead({});
  fetchNotifications();
}

function handleUserCommand(cmd) {
  if (cmd === "logout") {
    userStore.logout();
    router.push("/login");
  }
}

onMounted(() => {
  fetchStats();
  fetchNotifications();
  timer = setInterval(() => {
    fetchStats();
    fetchNotifications();
  }, 30000);
});

onBeforeUnmount(() => {
  if (timer) clearInterval(timer);
});
</script>

<style scoped>
.layout {
  display: flex;
  height: 100%;
  background: var(--bg);
}

/* 左侧导航 */
.rail {
  width: 210px;
  flex-shrink: 0;
  background: var(--bg-rail);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  align-items: stretch;
  padding: 14px 10px;
  gap: 18px;
}
.brand {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 10px;
  padding: 2px 8px;
}
.brand-mark {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: linear-gradient(135deg, #22d3ee, #0ea5e9);
  color: #04121f;
  font-size: 20px;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 6px 16px rgba(14, 165, 233, 0.28);
  flex-shrink: 0;
}
.brand-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}
.brand-name {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-main);
  letter-spacing: 0.5px;
}
.brand-sub {
  font-size: 10px;
  color: var(--text-sub);
  letter-spacing: 0.8px;
}
.nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 100%;
  align-items: stretch;
}
.nav-item {
  width: 100%;
  height: 44px;
  border-radius: 8px;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: flex-start;
  gap: 10px;
  padding: 0 12px;
  color: var(--text-sub);
  text-decoration: none;
  transition: all 0.18s;
  border: 1px solid transparent;
  position: relative;
}
.nav-item:hover {
  color: var(--text-main);
  background: rgba(14, 165, 233, 0.08);
}
.nav-item.active {
  color: var(--accent);
  background: linear-gradient(90deg, rgba(14, 165, 233, 0.14), rgba(14, 165, 233, 0.04));
  border-color: rgba(14, 165, 233, 0.35);
  box-shadow: 0 4px 12px rgba(14, 165, 233, 0.1);
}
.nav-item.active::before {
  content: "";
  position: absolute;
  left: 4px;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 18px;
  border-radius: 2px;
  background: var(--accent);
}
.nav-label {
  font-size: 13px;
  letter-spacing: 0.3px;
}
.rail-footer {
  font-size: 11px;
  color: #aab4c4;
  padding: 0 12px;
}

/* 右侧主列 */
.main-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.header {
  height: 58px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 22px;
  background: rgba(255, 255, 255, 0.85);
  border-bottom: 1px solid var(--border);
  backdrop-filter: blur(6px);
}
.page-title {
  font-size: 17px;
  font-weight: 700;
  letter-spacing: 0.5px;
}
.page-sub {
  font-size: 12px;
  color: var(--text-sub);
  margin-top: 2px;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 18px;
}
.bell-wrap {
  cursor: pointer;
  display: flex;
  align-items: center;
  padding: 6px;
  border-radius: 8px;
  transition: background 0.2s;
}
.bell-wrap:hover {
  background: rgba(14, 165, 233, 0.08);
}
.bell-icon {
  color: var(--text-sub);
}
.user-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  color: var(--text-main);
  padding: 6px 10px;
  border-radius: 8px;
  transition: background 0.2s;
}
.user-wrap:hover {
  background: rgba(14, 165, 233, 0.08);
}
.user-name {
  font-size: 13px;
}

/* KPI 指标条 */
.kpi-zone {
  flex-shrink: 0;
  padding: 14px 20px 0;
}

/* 主内容区 */
.main {
  flex: 1;
  overflow: auto;
  padding: 16px 20px 24px;
}

/* 通知面板 */
.notify-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}
.notify-list {
  max-height: 320px;
  overflow: auto;
  margin-top: 4px;
}
.notify-item {
  display: flex;
  gap: 10px;
  padding: 10px 6px;
  border-bottom: 1px dashed rgba(223, 228, 238, 0.9);
  cursor: pointer;
  border-radius: 8px;
}
.notify-item:hover {
  background: rgba(14, 165, 233, 0.05);
}
.notify-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-top: 6px;
  flex-shrink: 0;
}
.notify-dot.red {
  background: var(--accent-red);
  box-shadow: 0 0 8px rgba(248, 113, 113, 0.7);
}
.notify-dot.yellow {
  background: var(--accent-yellow);
  box-shadow: 0 0 8px rgba(251, 191, 36, 0.6);
}
.notify-dot.blue {
  background: var(--accent-blue);
}
.notify-dot.cyan {
  background: var(--accent);
}
.notify-body {
  min-width: 0;
}
.notify-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-main);
}
.notify-content {
  font-size: 12px;
  color: var(--text-sub);
  margin-top: 2px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.notify-time {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 3px;
}
</style>
