import { createRouter, createWebHistory } from "vue-router";

import MainLayout from "../layout/MainLayout.vue";
import Login from "../views/Login.vue";
import Dashboard from "../views/Dashboard.vue";
import Device from "../views/Device.vue";
import Alert from "../views/Alert.vue";
import WorkOrder from "../views/WorkOrder.vue";
import SparePart from "../views/SparePart.vue";
import Agent from "../views/Agent.vue";
import KnowledgeBase from "../views/KnowledgeBase.vue";

const routes = [
  { path: "/login", component: Login },
  {
    path: "/",
    component: MainLayout,
    children: [
      { path: "", redirect: "/dashboard" },
      {
        path: "dashboard",
        component: Dashboard,
        meta: { title: "监测看板", sub: "设备健康 · 运行指标一目了然" },
      },
      {
        path: "devices",
        component: Device,
        meta: { title: "设备管理", sub: "设备台账 · 传感器点位 · 阈值配置" },
      },
      {
        path: "alerts",
        component: Alert,
        meta: { title: "告警中心", sub: "阈值告警 · 趋势预警 · 闭环处理" },
      },
      {
        path: "work-orders",
        component: WorkOrder,
        meta: { title: "工单管理", sub: "派单 · 执行 · 验收全流程" },
      },
      {
        path: "spare-parts",
        component: SparePart,
        meta: { title: "备件库存", sub: "库存水位 · 出入库 · 低库存预警" },
      },
      {
        path: "agent",
        component: Agent,
        meta: { title: "智能助手", sub: "AI 智能查询 · 维保计划 · 工单调度" },
      },
      {
        path: "knowledge-base",
        component: KnowledgeBase,
        meta: { title: "知识库", sub: "维保手册 · 故障案例 · 文档管理" },
      },
    ],
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
