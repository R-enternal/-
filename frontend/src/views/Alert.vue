<template>
  <div class="page-wrap">
    <!-- 页面统计 -->
    <div class="stat-chips">
      <div class="stat-chip">
        <span class="stat-value red">{{ alerts.filter((a) => a.status === "PENDING").length }}</span>
        <span class="stat-label">待处理</span>
      </div>
      <div class="stat-chip">
        <span class="stat-value green">{{ alerts.filter((a) => a.status === "HANDLED").length }}</span>
        <span class="stat-label">已确认</span>
      </div>
      <div class="stat-chip">
        <span class="stat-value yellow">{{ alerts.filter((a) => a.status === "CONVERTED").length }}</span>
        <span class="stat-label">已转工单</span>
      </div>
      <div class="stat-chip">
        <span class="stat-value cyan">{{ alerts.length }}</span>
        <span class="stat-label">告警总数</span>
      </div>
    </div>

    <el-card>
      <template #header>
        <div class="card-header">
          <span class="panel-title">告警记录</span>
          <div class="header-actions">
            <el-input
              v-model="keyword"
              placeholder="搜索设备 / 点位 / 描述"
              clearable
              size="small"
              style="width: 220px"
              :prefix-icon="Search"
            />
            <el-select v-model="statusFilter" size="small" style="width: 130px" @change="fetchAlerts">
              <el-option label="全部状态" value="" />
              <el-option label="待处理" value="PENDING" />
              <el-option label="已确认" value="HANDLED" />
              <el-option label="已忽略" value="IGNORED" />
              <el-option label="已转工单" value="CONVERTED" />
            </el-select>
            <el-button size="small" @click="fetchAlerts">刷新</el-button>
          </div>
        </div>
      </template>

      <el-table v-loading="loading" :data="filteredAlerts" stripe>
        <el-table-column prop="device_name" label="设备" width="130" />
        <el-table-column prop="point_code" label="点位" width="130" />
        <el-table-column label="类型" width="150">
          <template #default="{ row }">{{ alertTypeText(row.alert_type) }}</template>
        </el-table-column>
        <el-table-column label="级别" width="90">
          <template #default="{ row }">
            <el-tag :type="levelType(row.level)" size="small" effect="dark">{{ levelText(row.level) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column label="时间" width="150">
          <template #default="{ row }">{{ (row.created_at || "").slice(0, 16).replace("T", " ") }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <template v-if="row.status === 'PENDING'">
              <el-button size="small" type="success" @click="handleAlert(row, 'handle')">确认</el-button>
              <el-button size="small" @click="handleAlert(row, 'ignore')">忽略</el-button>
            </template>
            <el-button
              v-else-if="row.status === 'HANDLED'"
              size="small"
              type="warning"
              @click="convertAlert(row)"
            >
              转工单
            </el-button>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { Search } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

import { alertApi } from "../api/modules";

const loading = ref(false);
const alerts = ref([]);
const statusFilter = ref("");
const keyword = ref("");

const filteredAlerts = computed(() => {
  const kw = keyword.value.trim().toLowerCase();
  if (!kw) return alerts.value;
  return alerts.value.filter((a) =>
    [a.device_name, a.point_code, a.description, a.title].some((v) => (v || "").toLowerCase().includes(kw))
  );
});

function levelType(level) {
  return { INFO: "info", WARNING: "warning", CRITICAL: "danger" }[level] || "info";
}
function levelText(level) {
  return { INFO: "提示", WARNING: "警告", CRITICAL: "严重" }[level] || level;
}
function statusType(status) {
  return {
    PENDING: "danger",
    HANDLED: "success",
    IGNORED: "info",
    CONVERTED: "warning",
  }[status] || "info";
}
function statusText(status) {
  return {
    PENDING: "待处理",
    HANDLED: "已确认",
    IGNORED: "已忽略",
    CONVERTED: "已转工单",
  }[status] || status;
}
function alertTypeText(type) {
  return {
    THRESHOLD_HIGH: "阈值超上限",
    THRESHOLD_LOW: "阈值低下限",
    TREND: "趋势预警",
    PREDICTIVE_HIGH: "预测超上限",
    PREDICTIVE_LOW: "预测低下限",
    ANOMALY: "异常检测",
    DATA_LINK: "数据链路",
  }[type] || type;
}

async function fetchAlerts() {
  loading.value = true;
  try {
    alerts.value = await alertApi.list({ status: statusFilter.value || undefined });
  } catch {
    alerts.value = [];
  } finally {
    loading.value = false;
  }
}

async function handleAlert(row, action) {
  const fn = action === "handle" ? alertApi.handle : alertApi.ignore;
  await fn(row.id, { handled_by: "admin", handle_note: `${action === "handle" ? "确认" : "忽略"}` });
  ElMessage.success(action === "handle" ? "已确认" : "已忽略");
  fetchAlerts();
}

async function convertAlert(row) {
  await alertApi.convert(row.id);
  ElMessage.success("已转工单");
  fetchAlerts();
}

onMounted(fetchAlerts);
</script>

<style scoped>
.stat-chips {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
}
.stat-chip {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 12px 16px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
}
.stat-value {
  font-size: 24px;
  font-weight: 800;
}
.stat-value.red {
  color: var(--accent-red);
}
.stat-value.green {
  color: var(--accent-green);
}
.stat-value.yellow {
  color: var(--accent-yellow);
}
.stat-value.cyan {
  color: var(--accent);
}
.stat-label {
  font-size: 13px;
  color: var(--text-sub);
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
