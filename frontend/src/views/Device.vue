<template>
  <div class="page-wrap">
    <!-- 页面统计 -->
    <div class="stat-chips">
      <div class="stat-chip">
        <span class="stat-value cyan">{{ devices.length }}</span>
        <span class="stat-label">设备总数</span>
      </div>
      <div class="stat-chip">
        <span class="stat-value green">{{ countByStatus("RUNNING") }}</span>
        <span class="stat-label">运行中</span>
      </div>
      <div class="stat-chip">
        <span class="stat-value yellow">{{ countByStatus("MAINTENANCE") }}</span>
        <span class="stat-label">维保中</span>
      </div>
      <div class="stat-chip">
        <span class="stat-value blue">{{ totalPoints }}</span>
        <span class="stat-label">传感器点位</span>
      </div>
    </div>

    <el-card>
      <template #header>
        <div class="card-header">
          <span class="panel-title">设备台账</span>
          <div class="header-actions">
            <el-input
              v-model="keyword"
              placeholder="搜索编号 / 名称 / 位置"
              clearable
              size="small"
              style="width: 220px"
              :prefix-icon="Search"
            />
            <el-select v-model="typeFilter" size="small" style="width: 140px" placeholder="全部类型">
              <el-option label="全部类型" value="" />
              <el-option v-for="t in deviceTypes" :key="t" :label="t" :value="t" />
            </el-select>
            <el-button type="primary" size="small" @click="openCreate">新建设备</el-button>
          </div>
        </div>
      </template>

      <el-table v-loading="loading" :data="filteredDevices" stripe>
        <el-table-column prop="device_code" label="设备编号" width="130" />
        <el-table-column prop="name" label="设备名称" min-width="140" show-overflow-tooltip />
        <el-table-column prop="device_type" label="类型" width="110">
          <template #default="{ row }">
            <span class="type-badge">{{ typeText(row.device_type) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="location" label="位置" min-width="100" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small" effect="dark">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="点位" width="190">
          <template #default="{ row }">
            <el-tag v-for="p in row.points" :key="p.id" size="small" class="point-tag" effect="plain">
              {{ pointTypeText(p.point_type) }}
            </el-tag>
            <span v-if="!row.points?.length" class="muted">无点位</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="viewDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建设备 -->
    <el-dialog v-model="dialogVisible" title="新建设备" width="520px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="设备编号" required>
          <el-input v-model="form.device_code" placeholder="如 CV-001" />
        </el-form-item>
        <el-form-item label="设备名称" required>
          <el-input v-model="form.name" placeholder="如 1号输送线" />
        </el-form-item>
        <el-form-item label="设备类型" required>
          <el-select v-model="form.device_type" style="width: 100%">
            <el-option v-for="t in deviceTypes" :key="t" :label="typeText(t)" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="位置">
          <el-input v-model="form.location" placeholder="如 A区01号" />
        </el-form-item>
        <el-form-item label="品牌/型号">
          <el-input v-model="form.brand" placeholder="品牌" style="width: 48%; margin-right: 4%" />
          <el-input v-model="form.model" placeholder="型号" style="width: 48%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 详情 -->
    <el-dialog v-model="detailVisible" title="设备详情" width="660px">
      <el-descriptions v-if="current" :column="2" border>
        <el-descriptions-item label="编号">{{ current.device_code }}</el-descriptions-item>
        <el-descriptions-item label="名称">{{ current.name }}</el-descriptions-item>
        <el-descriptions-item label="类型">{{ typeText(current.device_type) }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusType(current.status)" size="small" effect="dark">{{ statusText(current.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="位置">{{ current.location || "-" }}</el-descriptions-item>
        <el-descriptions-item label="品牌">{{ current.brand || "-" }}</el-descriptions-item>
      </el-descriptions>

      <!-- 智能诊断 -->
      <div v-if="diagnosis" class="diag-box">
        <div class="diag-head">
          <span class="panel-title">智能诊断</span>
          <el-tag :type="diagType(diagnosis.fault_type)" size="small" effect="dark">
            {{ diagTypeText(diagnosis.fault_type) }}
          </el-tag>
          <span class="muted diag-conf">置信度 {{ Math.round(diagnosis.confidence * 100) }}%</span>
        </div>
        <div v-if="diagnosis.signals?.length" class="diag-signals">
          <div
            v-for="s in diagnosis.signals"
            :key="s.name"
            class="diag-signal"
            :class="{ abnormal: s.severity !== 'NONE' }"
          >
            <span class="diag-signal-name">{{ signalText(s.name) }}</span>
            <span class="muted">{{ s.evidence }}</span>
          </div>
        </div>
        <div class="diag-recommend">{{ diagnosis.recommendation }}</div>
      </div>

      <h4 class="point-title">传感器点位（阈值）</h4>
      <el-table v-if="current?.points?.length" :data="current.points" size="small">
        <el-table-column prop="point_code" label="点位编号" />
        <el-table-column label="类型" width="110">
          <template #default="{ row }">{{ pointTypeText(row.point_type) }}</template>
        </el-table-column>
        <el-table-column label="阈值" width="150">
          <template #default="{ row }">{{ row.alarm_low ?? "-" }} ~ {{ row.alarm_high ?? "-" }} {{ row.unit || "" }}</template>
        </el-table-column>
        <el-table-column prop="unit" label="单位" width="70" />
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="openPointEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 点位阈值编辑 -->
    <el-dialog v-model="pointEditVisible" title="编辑点位阈值" width="420px">
      <el-form label-width="90px">
        <el-form-item label="点位">
          <span>{{ editingPoint?.point_code }}（{{ pointTypeText(editingPoint?.point_type) }}）</span>
        </el-form-item>
        <el-form-item label="下限">
          <el-input-number v-model="pointForm.alarm_low" :step="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="上限">
          <el-input-number v-model="pointForm.alarm_high" :step="1" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pointEditVisible = false">取消</el-button>
        <el-button type="primary" :loading="pointSaving" @click="savePoint">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { Search } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

import { deviceApi, diagnosisApi } from "../api/modules";

const deviceTypes = ["CONVEYOR", "STACKER", "AGV", "SORTER", "FORKLIFT"];
const loading = ref(false);
const submitting = ref(false);
const devices = ref([]);
const keyword = ref("");
const typeFilter = ref("");
const dialogVisible = ref(false);
const detailVisible = ref(false);
const pointEditVisible = ref(false);
const pointSaving = ref(false);
const current = ref(null);
const diagnosis = ref(null);
const editingPoint = ref(null);
const form = reactive({
  device_code: "",
  name: "",
  device_type: "CONVEYOR",
  location: "",
  brand: "",
  model: "",
});
const pointForm = reactive({ alarm_low: null, alarm_high: null });

const filteredDevices = computed(() => {
  const kw = keyword.value.trim().toLowerCase();
  return devices.value.filter((d) => {
    if (typeFilter.value && d.device_type !== typeFilter.value) return false;
    if (!kw) return true;
    return [d.device_code, d.name, d.location || ""].some((v) => v.toLowerCase().includes(kw));
  });
});

const totalPoints = computed(() => devices.value.reduce((sum, d) => sum + (d.points?.length || 0), 0));

function countByStatus(status) {
  return devices.value.filter((d) => d.status === status).length;
}

function statusType(status) {
  return { RUNNING: "success", STOPPED: "info", MAINTENANCE: "warning", SCRAPPED: "danger" }[status] || "info";
}
function statusText(status) {
  return { RUNNING: "运行", STOPPED: "停机", MAINTENANCE: "维保", SCRAPPED: "报废" }[status] || status;
}
function typeText(type) {
  return { CONVEYOR: "输送机", STACKER: "堆垛机", AGV: "AGV", SORTER: "分拣机", FORKLIFT: "叉车" }[type] || type;
}
function pointTypeText(type) {
  return { VIBRATION: "振动", TEMPERATURE: "温度", CURRENT: "电流" }[type] || type;
}

async function fetchDevices() {
  loading.value = true;
  try {
    const list = await deviceApi.list();
    // 列表接口不带点位，逐个取详情（骨架阶段数据量小，够用）
    devices.value = await Promise.all(list.map((d) => deviceApi.detail(d.id).catch(() => d)));
  } catch {
    devices.value = [];
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  Object.assign(form, {
    device_code: "",
    name: "",
    device_type: "CONVEYOR",
    location: "",
    brand: "",
    model: "",
  });
  dialogVisible.value = true;
}

async function handleCreate() {
  if (!form.device_code || !form.name) {
    ElMessage.warning("请填写设备编号和名称");
    return;
  }
  submitting.value = true;
  try {
    await deviceApi.create(form);
    ElMessage.success("设备创建成功");
    dialogVisible.value = false;
    fetchDevices();
  } catch {
    // 拦截器已提示
  } finally {
    submitting.value = false;
  }
}

function viewDetail(row) {
  current.value = row;
  diagnosis.value = null;
  detailVisible.value = true;
  loadDiagnosis(row.id);
}

async function loadDiagnosis(deviceId) {
  try {
    const records = await diagnosisApi.latest(deviceId);
    diagnosis.value = records[0] || null;
  } catch {
    diagnosis.value = null;
  }
}

function diagType(t) {
  return {
    NORMAL: "success",
    BEARING_WEAR: "warning",
    MOTOR_OVERHEAT: "warning",
    LOAD_ABNORMAL: "warning",
    COMPOSITE_FAULT: "danger",
  }[t] || "info";
}

function diagTypeText(t) {
  return {
    NORMAL: "运行正常",
    BEARING_WEAR: "轴承磨损",
    MOTOR_OVERHEAT: "电机过热",
    LOAD_ABNORMAL: "负载异常",
    COMPOSITE_FAULT: "复合故障",
  }[t] || t;
}

function signalText(t) {
  return { VIBRATION: "振动", TEMPERATURE: "温度", CURRENT: "电流" }[t] || t;
}

function openPointEdit(row) {
  editingPoint.value = row;
  Object.assign(pointForm, { alarm_low: row.alarm_low, alarm_high: row.alarm_high });
  pointEditVisible.value = true;
}

async function savePoint() {
  pointSaving.value = true;
  try {
    await deviceApi.updatePoint(editingPoint.value.id, pointForm);
    ElMessage.success("阈值已更新");
    pointEditVisible.value = false;
    current.value = await deviceApi.detail(current.value.id);
    fetchDevices();
  } catch {
    // 拦截器已提示
  } finally {
    pointSaving.value = false;
  }
}

onMounted(fetchDevices);
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
.stat-value.cyan {
  color: var(--accent);
}
.stat-value.green {
  color: var(--accent-green);
}
.stat-value.yellow {
  color: var(--accent-yellow);
}
.stat-value.blue {
  color: var(--accent-blue);
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
.point-tag {
  margin-right: 4px;
}
.type-badge {
  color: var(--accent);
  font-weight: 500;
}
.point-title {
  margin: 16px 0 8px;
}
.diag-box {
  margin: 14px 0;
  padding: 12px 14px;
  background: #f4f6fb;
  border: 1px solid var(--border);
  border-radius: 10px;
}
.diag-head {
  display: flex;
  align-items: center;
  gap: 10px;
}
.diag-conf {
  font-size: 12px;
}
.diag-signals {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 10px 0 8px;
}
.diag-signal {
  padding: 4px 10px;
  border-radius: 8px;
  border: 1px solid var(--border);
  font-size: 12px;
  background: #ffffff;
}
.diag-signal.abnormal {
  border-color: rgba(245, 158, 11, 0.5);
  color: var(--accent-yellow);
}
.diag-signal-name {
  font-weight: 600;
  margin-right: 6px;
}
.diag-recommend {
  font-size: 13px;
  color: var(--text-main);
  line-height: 1.6;
}
</style>
