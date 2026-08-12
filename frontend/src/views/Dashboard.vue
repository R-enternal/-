<template>
  <div class="page-wrap dashboard">
    <!-- 设备健康度总览 -->
    <div class="section">
      <div class="section-head">
        <span class="panel-title">设备健康度总览</span>
        <span class="muted refresh-time">
          点击设备卡片切换下方实时参数 · 最近更新 {{ lastRefresh }}
        </span>
      </div>
      <div v-if="cards.length" class="health-grid">
        <div
          v-for="card in cards"
          :key="card.device_id"
          class="health-card"
          :class="{ active: card.device_id === sensorDeviceId }"
          @click="selectSensorDevice(card.device_id)"
        >
          <div class="hc-top">
            <span class="hc-name" :title="card.device_name">{{ card.device_name }}</span>
            <el-tag :type="statusType(card.status)" size="small" effect="dark" class="hc-status">
              {{ statusText(card.status) }}
            </el-tag>
          </div>
          <div class="hc-score-row">
            <span class="hc-score" :style="{ color: levelColor(card.level) }">
              {{ card.score }}
            </span>
            <span class="hc-level" :style="{ background: levelColor(card.level) }">
              {{ levelText(card.level) }}
            </span>
          </div>
          <div class="hc-bar">
            <div
              class="hc-bar-fill"
              :style="{ width: card.score + '%', background: levelColor(card.level) }"
            ></div>
          </div>
          <div class="hc-bottom">
            <svg v-if="card.spark.length > 1" class="hc-spark" viewBox="0 0 100 26" preserveAspectRatio="none">
              <polyline
                :points="sparkPoints(card.spark)"
                fill="none"
                :stroke="levelColor(card.level)"
                stroke-width="2"
                stroke-linejoin="round"
                stroke-linecap="round"
              />
            </svg>
            <span v-else class="muted spark-empty">暂无趋势</span>
            <span class="hc-time">{{ card.updated_at }}</span>
          </div>
        </div>
      </div>
      <el-empty v-else description="暂无健康度数据（后台每 5 分钟自动计算一次）" :image-size="90" />
    </div>

    <!-- 运行参数实时监控 -->
    <div class="section">
      <div class="section-head">
        <span class="panel-title">运行参数实时监控</span>
        <div class="sensor-select-row">
          <span v-if="currentDeviceName" class="muted current-device">当前设备：{{ currentDeviceName }}</span>
          <el-select v-model="sensorDeviceId" size="small" style="width: 220px" @change="onSensorDeviceChange">
            <el-option v-for="d in devices" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </div>
      </div>
      <div class="sensor-grid">
        <div v-for="m in metricCards" :key="m.type" class="sensor-card">
          <div class="sc-head">
            <span class="sc-name" :style="{ color: m.color }">{{ metricText(m.type) }}</span>
            <span class="muted sc-point">{{ m.point_code || "无此类点位" }}</span>
          </div>
          <div class="sc-value-row">
            <span
              class="sc-value"
              :style="{ color: m.status === 'ABNORMAL' ? '#ef4444' : m.color }"
            >
              {{ m.current ?? "--" }}
            </span>
            <span class="sc-unit">{{ m.unit }}</span>
            <el-tag
              v-if="m.rows.length"
              :type="m.status === 'ABNORMAL' ? 'danger' : 'success'"
              size="small"
              effect="dark"
            >
              {{ m.status === "ABNORMAL" ? "异常" : "正常" }}
            </el-tag>
          </div>
          <div class="sc-range">报警区间 {{ m.low ?? "—" }} ~ {{ m.high ?? "—" }} {{ m.unit }}</div>
          <v-chart v-if="m.rows.length" class="sc-chart" :option="m.option" autoresize />
          <div v-else class="sc-empty muted">暂无数据（每分钟采集一次）</div>
        </div>
      </div>
    </div>

    <!-- 健康度趋势 -->
    <el-card class="chart-card">
      <template #header>
        <div class="chart-head">
          <span class="panel-title">健康度趋势</span>
          <span class="muted trend-hint">{{ currentDeviceName }} · 底部可拖动查看更早数据</span>
        </div>
      </template>
      <v-chart v-if="trendOption.series[0]?.data.length" class="chart" :option="trendOption" autoresize />
      <el-empty v-else description="暂无健康度记录" :image-size="80" />
    </el-card>

    <!-- 三大速览面板 -->
    <el-row :gutter="14">
      <el-col :xs="24" :md="8">
        <el-card class="quick-card">
          <template #header>
            <div class="quick-head">
              <span class="panel-title">最新告警</span>
              <router-link to="/alerts" class="more-link">查看全部 →</router-link>
            </div>
          </template>
          <div v-if="recentAlerts.length" class="quick-list">
            <div v-for="a in recentAlerts" :key="a.id" class="quick-item">
              <span class="dot" :class="alertLevelClass(a.level)"></span>
              <div class="qi-body">
                <div class="qi-title">{{ a.title }}</div>
                <div class="qi-meta">{{ a.device_name }} · {{ (a.created_at || "").slice(11, 16) }}</div>
              </div>
              <el-tag size="small" :type="alertStatusType(a.status)" effect="plain">{{ alertStatusText(a.status) }}</el-tag>
            </div>
          </div>
          <el-empty v-else description="暂无告警" :image-size="60" />
        </el-card>
      </el-col>
      <el-col :xs="24" :md="8">
        <el-card class="quick-card">
          <template #header>
            <div class="quick-head">
              <span class="panel-title">低库存备件</span>
              <router-link to="/spare-parts" class="more-link">查看全部 →</router-link>
            </div>
          </template>
          <div v-if="lowStockParts.length" class="quick-list">
            <div v-for="p in lowStockParts" :key="p.id" class="quick-item">
              <span class="dot red"></span>
              <div class="qi-body">
                <div class="qi-title">{{ p.name }}（{{ p.part_code }}）</div>
                <el-progress
                  :percentage="stockPercent(p)"
                  :stroke-width="6"
                  :show-text="false"
                  :color="stockPercent(p) < 50 ? '#ef4444' : '#f97316'"
                  class="stock-bar"
                />
                <div class="qi-meta">库存 {{ p.stock_quantity }} / 安全 {{ p.safe_quantity }}</div>
              </div>
            </div>
          </div>
          <el-empty v-else description="备件库存充足" :image-size="60" />
        </el-card>
      </el-col>
      <el-col :xs="24" :md="8">
        <el-card class="quick-card">
          <template #header>
            <div class="quick-head">
              <span class="panel-title">待办工单</span>
              <router-link to="/work-orders" class="more-link">查看全部 →</router-link>
            </div>
          </template>
          <div v-if="activeOrders.length" class="quick-list">
            <div v-for="o in activeOrders" :key="o.id" class="quick-item">
              <span class="dot yellow"></span>
              <div class="qi-body">
                <div class="qi-title">{{ o.title }}</div>
                <div class="qi-meta">{{ o.device_name }} · {{ o.order_no }}</div>
              </div>
              <el-tag size="small" :type="orderStatusType(o.status)" effect="plain">{{ orderStatusText(o.status) }}</el-tag>
            </div>
          </div>
          <el-empty v-else description="暂无待办工单" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { LineChart } from "echarts/charts";
import {
  DataZoomComponent,
  GridComponent,
  MarkLineComponent,
  TooltipComponent,
} from "echarts/components";
import VChart from "vue-echarts";

import { alertApi, deviceApi, healthApi, sparePartApi, workOrderApi } from "../api/modules";

use([
  CanvasRenderer,
  LineChart,
  GridComponent,
  TooltipComponent,
  MarkLineComponent,
  DataZoomComponent,
]);

const devices = ref([]);
const healthRecords = ref([]);
const alerts = ref([]);
const parts = ref([]);
const orders = ref([]);
const lastRefresh = ref("--");

const trendRecords = ref([]);
const sensorDeviceId = ref(null);
const sensorPoints = ref([]);
const sensorRows = ref([]);

const currentDeviceName = computed(
  () => devices.value.find((d) => d.id === sensorDeviceId.value)?.name || ""
);

/* ---------- 健康度卡片 ---------- */
const cards = computed(() => {
  const latest = new Map();
  const history = new Map();
  for (const r of healthRecords.value) {
    if (!history.has(r.device_id)) history.set(r.device_id, []);
    history.get(r.device_id).push(r);
    if (!latest.has(r.device_id)) latest.set(r.device_id, r);
  }
  const nameMap = new Map(devices.value.map((d) => [d.id, d]));
  return [...latest.entries()].map(([device_id, r]) => {
    const device = nameMap.get(device_id) || {};
    const hist = (history.get(device_id) || []).slice().reverse(); // 时间正序
    return {
      device_id,
      device_name: device.name || `设备#${device_id}`,
      status: device.status || "UNKNOWN",
      score: Math.round(r.score * 10) / 10,
      level: r.level,
      updated_at: (r.computed_at || "").slice(11, 16),
      spark: hist.slice(-12).map((h) => h.score),
    };
  });
});

function sparkPoints(values) {
  const min = Math.min(...values, 60);
  const max = Math.max(...values, 100);
  const span = Math.max(max - min, 1);
  return values
    .map((v, i) => `${(i / (values.length - 1)) * 100},${24 - ((v - min) / span) * 22}`)
    .join(" ");
}

function levelColor(level) {
  return { HEALTHY: "#10b981", SUB_HEALTHY: "#fbbf24", ABNORMAL: "#ef4444" }[level] || "#64748b";
}
function levelText(level) {
  return { HEALTHY: "健康", SUB_HEALTHY: "亚健康", ABNORMAL: "异常" }[level] || level;
}
function statusType(status) {
  return { RUNNING: "success", STOPPED: "info", MAINTENANCE: "warning", SCRAPPED: "danger" }[status] || "info";
}
function statusText(status) {
  return { RUNNING: "运行", STOPPED: "停机", MAINTENANCE: "维保", SCRAPPED: "报废" }[status] || status;
}

/* ---------- 健康度趋势图 ---------- */
const trendOption = computed(() => {
  // 趋势图跟随当前选中设备：单设备一条线，纵轴自适应，底部滑块可回看历史
  const recs = [...trendRecords.value].reverse(); // 后端倒序 → 转时间正序
  if (!recs.length) return { series: [] };

  const times = recs.map((r) => (r.computed_at || "").slice(11, 16));
  const scores = recs.map((r) => r.score);

  // 纵轴按数据范围自适应：让曲线在纵向充分展开
  const dataMin = Math.min(...scores);
  const yMin = Math.max(0, Math.floor((dataMin - 8) / 5) * 5);

  // 横轴：默认窗口展示最近 2 小时（健康度每 5 分钟一条），可往左拖动看更早
  const WINDOW_COUNT = 24;
  const zoomStart = scores.length > WINDOW_COUNT ? ((scores.length - WINDOW_COUNT) / scores.length) * 100 : 0;

  return {
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(255,255,255,.96)",
      borderColor: "#dfe4ee",
      textStyle: { color: "#1f2937" },
    },
    grid: { left: 46, right: 18, top: 24, bottom: 48 },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: times,
      axisLine: { lineStyle: { color: "#dfe4ee" } },
      // 每 5 分钟一个数据点，刻度每 6 个点显示一个（即每 30 分钟一个坐标）
      axisLabel: { color: "#64748b", fontSize: 11, hideOverlap: true, interval: 6 },
    },
    yAxis: {
      type: "value",
      min: yMin,
      max: 100,
      splitLine: { lineStyle: { color: "rgba(148,163,184,.4)", type: "dashed" } },
      axisLabel: { color: "#64748b", fontSize: 11 },
    },
    dataZoom: [
      {
        type: "slider",
        start: zoomStart,
        end: 100,
        bottom: 8,
        height: 18,
        borderColor: "#dfe4ee",
        backgroundColor: "rgba(241,245,249,.9)",
        fillerColor: "rgba(14,165,233,.16)",
        handleStyle: { color: "#0ea5e9", borderColor: "#0ea5e9" },
        moveHandleStyle: { color: "#0ea5e9" },
        textStyle: { color: "#64748b" },
        dataBackground: {
          lineStyle: { color: "#cbd5e1" },
          areaStyle: { color: "rgba(203,213,225,.5)" },
        },
      },
      { type: "inside", start: zoomStart, end: 100 },
    ],
    series: [
      {
        name: currentDeviceName.value,
        type: "line",
        smooth: true,
        showSymbol: false,
        data: scores,
        lineStyle: { width: 2, color: "#0ea5e9" },
        itemStyle: { color: "#0ea5e9" },
        areaStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(14,165,233,.28)" },
              { offset: 1, color: "rgba(14,165,233,.02)" },
            ],
          },
        },
        markLine: {
          symbol: "none",
          data: [{ yAxis: 90, name: "健康线" }],
          lineStyle: { type: "dashed", color: "#10b981", width: 1 },
          label: { color: "#10b981", fontSize: 10, formatter: "健康线 90" },
        },
      },
    ],
  };
});

/* ---------- 运行参数实时监控（温度/振动/电流） ---------- */
const METRIC_META = {
  TEMPERATURE: { text: "温度", color: "#f97316", area: "rgba(249,115,22," },
  VIBRATION: { text: "振动", color: "#a78bfa", area: "rgba(167,139,250," },
  CURRENT: { text: "电流", color: "#0ea5e9", area: "rgba(14,165,233," },
};

function metricText(type) {
  return METRIC_META[type]?.text || type;
}

function buildSensorOption(rows, point, type) {
  const meta = METRIC_META[type] || METRIC_META.CURRENT;
  // 纵轴按实际数据范围缩放（留 18% 边距），让波动在图上明显可读
  const values = rows.map((r) => r.value);
  let yMin = 0;
  let yMax = 100;
  if (values.length) {
    const dMin = Math.min(...values);
    const dMax = Math.max(...values);
    const pad = (dMax - dMin) * 0.18 || Math.max(Math.abs(dMax) * 0.1, 1);
    yMin = +(dMin - pad).toFixed(2);
    yMax = +(dMax + pad).toFixed(2);
  }

  // 数据每 1 分钟一条：默认窗口最近 1 小时（比最小窗口略大），
  // 底部滑块可往左拖看完整 24 小时，也可继续缩小到最小 30 分钟
  const WINDOW_COUNT = 60;
  const MIN_WINDOW = 30;
  const zoomStart =
    rows.length > WINDOW_COUNT ? ((rows.length - WINDOW_COUNT) / rows.length) * 100 : 0;

  const markLineData = [];
  if (point?.alarm_high != null) {
    markLineData.push({ yAxis: point.alarm_high, name: "上限" });
  }
  if (point?.alarm_low != null) {
    markLineData.push({ yAxis: point.alarm_low, name: "下限" });
  }
  return {
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(255,255,255,.96)",
      borderColor: "#dfe4ee",
      textStyle: { color: "#1f2937" },
    },
    grid: { left: 40, right: 12, top: 18, bottom: 44 },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: rows.map((r) => (r.collected_at || "").slice(11, 16)),
      axisLine: { lineStyle: { color: "#dfe4ee" } },
      // 每 1 分钟一个数据点，刻度每 30 个点显示一个（即每 30 分钟一个坐标）
      axisLabel: { color: "#64748b", fontSize: 11, hideOverlap: true, interval: (index) => index % 30 === 0 },
    },
    yAxis: {
      type: "value",
      min: yMin,
      max: yMax,
      splitLine: { lineStyle: { color: "rgba(148,163,184,.4)", type: "dashed" } },
      axisLabel: { color: "#64748b", fontSize: 11 },
    },
    dataZoom: [
      {
        type: "slider",
        start: zoomStart,
        end: 100,
        minValueSpan: MIN_WINDOW,
        bottom: 2,
        height: 16,
        borderColor: "#dfe4ee",
        backgroundColor: "rgba(241,245,249,.9)",
        fillerColor: "rgba(14,165,233,.16)",
        handleStyle: { color: "#0ea5e9", borderColor: "#0ea5e9" },
        moveHandleStyle: { color: "#0ea5e9" },
        textStyle: { color: "#64748b", fontSize: 10 },
        dataBackground: {
          lineStyle: { color: "#cbd5e1" },
          areaStyle: { color: "rgba(203,213,225,.5)" },
        },
      },
      { type: "inside", start: zoomStart, end: 100, minValueSpan: MIN_WINDOW },
    ],
    series: [
      {
        type: "line",
        smooth: true,
        showSymbol: false,
        data: rows.map((r) => r.value),
        lineStyle: { width: 2, color: meta.color },
        itemStyle: { color: meta.color },
        areaStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: `${meta.area}0.28)` },
              { offset: 1, color: `${meta.area}0.02)` },
            ],
          },
        },
        markLine: {
          symbol: "none",
          data: markLineData,
          lineStyle: { type: "dashed", color: "#ef4444", width: 1 },
          label: { color: "#ef4444", fontSize: 10 },
        },
      },
    ],
  };
}

const metricCards = computed(() =>
  ["TEMPERATURE", "VIBRATION", "CURRENT"].map((type) => {
    const point = sensorPoints.value.find((p) => p.point_type === type);
    const rows = point ? sensorRows.value.filter((r) => r.point_id === point.id) : [];
    const last = rows.length ? rows[rows.length - 1] : null;
    return {
      type,
      point_code: point?.point_code,
      unit: point?.unit || last?.unit || "",
      low: point?.alarm_low,
      high: point?.alarm_high,
      current: last?.value ?? null,
      status: last?.status || "NORMAL",
      rows,
      color: METRIC_META[type].color,
      option: buildSensorOption(rows, point, type),
    };
  })
);

/* ---------- 速览面板 ---------- */
const recentAlerts = computed(() => alerts.value.slice(0, 5));
const lowStockParts = computed(() =>
  parts.value
    .filter((p) => p.safe_quantity > 0 && p.stock_quantity < p.safe_quantity)
    .sort((a, b) => a.stock_quantity / a.safe_quantity - b.stock_quantity / b.safe_quantity)
    .slice(0, 5)
);
const activeOrders = computed(() =>
  orders.value
    .filter((o) => ["PENDING_ASSIGN", "PENDING_EXECUTE", "IN_PROGRESS", "PENDING_ACCEPT"].includes(o.status))
    .slice(0, 5)
);

function stockPercent(p) {
  return Math.min(Math.round((p.stock_quantity / p.safe_quantity) * 100), 100);
}
function alertLevelClass(level) {
  return { INFO: "cyan", WARNING: "yellow", CRITICAL: "red" }[level] || "cyan";
}
function alertStatusType(status) {
  return { PENDING: "danger", HANDLED: "success", IGNORED: "info", CONVERTED: "warning" }[status] || "info";
}
function alertStatusText(status) {
  return { PENDING: "待处理", HANDLED: "已确认", IGNORED: "已忽略", CONVERTED: "已转工单" }[status] || status;
}
function orderStatusType(status) {
  return {
    PENDING_ASSIGN: "warning",
    PENDING_EXECUTE: "primary",
    IN_PROGRESS: "primary",
    PENDING_ACCEPT: "warning",
    COMPLETED: "success",
    CANCELLED: "info",
  }[status] || "info";
}
function orderStatusText(status) {
  return {
    PENDING_ASSIGN: "待派单",
    PENDING_EXECUTE: "待执行",
    IN_PROGRESS: "执行中",
    PENDING_ACCEPT: "待验收",
    COMPLETED: "已完成",
    CANCELLED: "已取消",
  }[status] || status;
}
/* ---------- 数据加载 ---------- */
async function fetchOverview() {
  try {
    const [devList, records, alertList, partList, orderList] = await Promise.all([
      deviceApi.list(),
      healthApi.list({ limit: 200 }),
      alertApi.list(),
      sparePartApi.list(),
      workOrderApi.list(),
    ]);
    devices.value = devList;
    healthRecords.value = records;
    alerts.value = alertList;
    parts.value = partList;
    orders.value = orderList;
    lastRefresh.value = new Date().toTimeString().slice(0, 5);

    if (!sensorDeviceId.value && devList.length) {
      await selectSensorDevice(devList[0].id);
    } else if (sensorDeviceId.value) {
      fetchTrendRecords(sensorDeviceId.value);
    }
  } catch {
    // 后端未就绪时静默保留
  }
}

async function selectSensorDevice(deviceId) {
  sensorDeviceId.value = deviceId;
  const [detail, trendRecs] = await Promise.all([
    deviceApi.detail(deviceId).catch(() => null),
    healthApi.list({ device_id: deviceId, limit: 500 }).catch(() => []),
  ]);
  sensorPoints.value = detail?.points || [];
  trendRecords.value = trendRecs;
  await fetchSensorData();
}

async function fetchTrendRecords(deviceId) {
  try {
    trendRecords.value = await healthApi.list({ device_id: deviceId, limit: 500 });
  } catch {
    // 后端未就绪时保留旧数据
  }
}

async function onSensorDeviceChange(id) {
  await selectSensorDevice(id);
}

async function fetchSensorData() {
  if (!sensorDeviceId.value) return;
  try {
    sensorRows.value = await deviceApi.sensorData(sensorDeviceId.value, { limit: 1440 });
  } catch {
    sensorRows.value = [];
  }
}

let timer = null;

onMounted(() => {
  fetchOverview();
  timer = setInterval(() => {
    fetchOverview();
    fetchSensorData();
  }, 30000);
});

onBeforeUnmount(() => {
  if (timer) clearInterval(timer);
});
</script>

<style scoped>
.section {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 14px 18px 18px;
}
.section-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}
.refresh-time {
  font-size: 12px;
}

.health-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(228px, 1fr));
  gap: 12px;
}
.health-card {
  background: var(--bg-card-solid);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 14px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03), 0 6px 18px rgba(15, 23, 42, 0.04);
  cursor: pointer;
  transition: border-color 0.2s, transform 0.15s, box-shadow 0.2s;
}
.health-card:hover {
  border-color: rgba(14, 165, 233, 0.5);
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(14, 165, 233, 0.1);
}
.health-card.active {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent), 0 8px 24px rgba(14, 165, 233, 0.18);
}
.hc-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.hc-name {
  font-weight: 600;
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hc-status {
  flex-shrink: 0;
}
.hc-score-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin: 10px 0 8px;
}
.hc-score {
  font-size: 34px;
  font-weight: 800;
  line-height: 1;
}
.hc-level {
  font-size: 12px;
  color: #04121f;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 999px;
}
.hc-bar {
  height: 6px;
  border-radius: 3px;
  background: #e2e8f0;
  overflow: hidden;
}
.hc-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.5s;
}
.hc-bottom {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-top: 10px;
  gap: 8px;
}
.hc-spark {
  width: 90px;
  height: 26px;
}
.spark-empty {
  font-size: 12px;
}
.hc-time {
  font-size: 12px;
  color: var(--text-sub);
}

.chart-card {
  margin-bottom: 14px;
}
.chart-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.chart {
  height: 300px;
}
.trend-hint {
  font-size: 13px;
}
.sensor-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 12px;
}
.sensor-select-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.current-device {
  font-size: 13px;
}
.sensor-card {
  background: var(--bg-card-solid);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 14px 14px 10px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03), 0 6px 18px rgba(15, 23, 42, 0.04);
  transition: border-color 0.2s;
}
.sensor-card:hover {
  border-color: rgba(14, 165, 233, 0.4);
}
.sc-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.sc-name {
  font-size: 15px;
  font-weight: 700;
}
.sc-point {
  font-size: 12px;
}
.sc-value-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin: 10px 0 4px;
}
.sc-value {
  font-size: 38px;
  font-weight: 800;
  line-height: 1;
}
.sc-unit {
  font-size: 14px;
  color: var(--text-sub);
}
.sc-range {
  font-size: 12px;
  margin-bottom: 8px;
}
.sc-chart {
  height: 172px;
}
.sc-empty {
  height: 172px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
}

.quick-card {
  margin-bottom: 14px;
}
.quick-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.more-link {
  font-size: 12px;
  color: var(--accent);
  text-decoration: none;
}
.more-link:hover {
  text-decoration: underline;
}
.quick-list {
  max-height: 300px;
  overflow: auto;
}
.quick-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 4px;
  border-bottom: 1px dashed #e2e8f0;
}
.quick-item:last-child {
  border-bottom: none;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.dot.red {
  background: var(--accent-red);
  box-shadow: 0 0 8px rgba(239, 68, 68, 0.5);
}
.dot.yellow {
  background: var(--accent-yellow);
  box-shadow: 0 0 8px rgba(251, 191, 36, 0.5);
}
.dot.cyan {
  background: var(--accent);
}
.qi-body {
  flex: 1;
  min-width: 0;
}
.qi-title {
  font-size: 13px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.qi-meta {
  font-size: 11px;
  color: var(--text-sub);
  margin-top: 2px;
}
.stock-bar {
  margin: 4px 0 2px;
}
</style>
