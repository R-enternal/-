<template>
  <div class="page-wrap">
    <!-- 页面统计 -->
    <div class="stat-chips">
      <div class="stat-chip">
        <span class="stat-value yellow">{{ countByStatus("PENDING_ASSIGN") }}</span>
        <span class="stat-label">待派单</span>
      </div>
      <div class="stat-chip">
        <span class="stat-value cyan">{{ countByStatus("PENDING_EXECUTE") + countByStatus("IN_PROGRESS") }}</span>
        <span class="stat-label">执行中</span>
      </div>
      <div class="stat-chip">
        <span class="stat-value orange">{{ countByStatus("PENDING_ACCEPT") }}</span>
        <span class="stat-label">待验收</span>
      </div>
      <div class="stat-chip">
        <span class="stat-value green">{{ countByStatus("COMPLETED") }}</span>
        <span class="stat-label">已完成</span>
      </div>
    </div>

    <el-card>
      <template #header>
        <div class="card-header">
          <span class="panel-title">工单列表</span>
          <div class="header-actions">
            <el-input
              v-model="keyword"
              placeholder="搜索工单号 / 标题 / 设备"
              clearable
              size="small"
              style="width: 220px"
              :prefix-icon="Search"
            />
            <el-select v-model="statusFilter" size="small" style="width: 130px" @change="fetchOrders">
              <el-option label="全部状态" value="" />
              <el-option label="待派单" value="PENDING_ASSIGN" />
              <el-option label="待执行" value="PENDING_EXECUTE" />
              <el-option label="执行中" value="IN_PROGRESS" />
              <el-option label="待验收" value="PENDING_ACCEPT" />
              <el-option label="已完成" value="COMPLETED" />
              <el-option label="已取消" value="CANCELLED" />
            </el-select>
            <el-button type="primary" size="small" @click="openCreate">新建工单</el-button>
          </div>
        </div>
      </template>

      <el-table v-loading="loading" :data="filteredOrders" stripe>
        <el-table-column prop="order_no" label="工单号" width="175" />
        <el-table-column prop="device_name" label="设备" width="120" show-overflow-tooltip />
        <el-table-column prop="title" label="标题" min-width="160" show-overflow-tooltip />
        <el-table-column label="优先级" width="90">
          <template #default="{ row }">
            <el-tag :type="priorityType(row.priority)" size="small" effect="dark">{{ priorityText(row.priority) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="150">
          <template #default="{ row }">{{ (row.created_at || "").slice(0, 16).replace("T", " ") }}</template>
        </el-table-column>
        <el-table-column label="操作" width="230" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'PENDING_ASSIGN'" size="small" type="primary" @click="openAssign(row)">派单</el-button>
            <el-button v-if="row.status === 'PENDING_EXECUTE'" size="small" type="primary" @click="doTransition(row, 'start')">开始</el-button>
            <el-button v-if="row.status === 'IN_PROGRESS'" size="small" type="primary" @click="doTransition(row, 'submit')">提交验收</el-button>
            <el-button v-if="row.status === 'PENDING_ACCEPT'" size="small" type="success" @click="openComplete(row)">完成</el-button>
            <el-button
              v-if="['PENDING_ASSIGN', 'PENDING_EXECUTE', 'IN_PROGRESS', 'PENDING_ACCEPT'].includes(row.status)"
              size="small"
              @click="doTransition(row, 'cancel')"
            >
              取消
            </el-button>
            <span v-if="['COMPLETED', 'CANCELLED'].includes(row.status)" class="muted">-</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建工单 -->
    <el-dialog v-model="createVisible" title="新建工单" width="480px">
      <el-form label-width="80px">
        <el-form-item label="设备" required>
          <el-select v-model="createForm.device_id" style="width: 100%" filterable>
            <el-option v-for="d in devices" :key="d.id" :label="`${d.name}（${d.device_code}）`" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="标题" required>
          <el-input v-model="createForm.title" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createForm.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="createForm.priority" style="width: 100%">
            <el-option label="低" value="LOW" />
            <el-option label="中" value="MEDIUM" />
            <el-option label="高" value="HIGH" />
            <el-option label="紧急" value="URGENT" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 派单 -->
    <el-dialog v-model="assignVisible" title="派单" width="420px">
      <el-form label-width="80px">
        <el-form-item label="指派人" required>
          <el-select v-model="assignUserId" style="width: 100%" filterable>
            <el-option
              v-for="u in users"
              :key="u.id"
              :label="`${u.real_name || u.username}（${u.role}）`"
              :value="u.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="assignVisible = false">取消</el-button>
        <el-button type="primary" @click="doAssign">确认派单</el-button>
      </template>
    </el-dialog>

    <!-- 完成工单 -->
    <el-dialog v-model="completeVisible" title="完成工单" width="480px">
      <el-form label-width="80px">
        <el-form-item label="处理结果">
          <el-input v-model="completeResult" type="textarea" :rows="3" placeholder="如：更换轴承，运行正常" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="completeVisible = false">取消</el-button>
        <el-button type="success" @click="doComplete">确认完成</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { Search } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

import { deviceApi, userApi, warehouseApi, workOrderApi } from "../api/modules";

const loading = ref(false);
const orders = ref([]);
const devices = ref([]);
const warehouses = ref([]);
const users = ref([]);
const keyword = ref("");
const statusFilter = ref("");
const createVisible = ref(false);
const assignVisible = ref(false);
const completeVisible = ref(false);
const currentOrder = ref(null);
const assignUserId = ref(null);
const completeResult = ref("");
const createForm = reactive({
  warehouse_id: null,
  device_id: null,
  title: "",
  description: "",
  priority: "MEDIUM",
});

const filteredOrders = computed(() => {
  const kw = keyword.value.trim().toLowerCase();
  if (!kw) return orders.value;
  return orders.value.filter((o) =>
    [o.order_no, o.title, o.device_name].some((v) => (v || "").toLowerCase().includes(kw))
  );
});

function countByStatus(status) {
  return orders.value.filter((o) => o.status === status).length;
}

function priorityType(p) {
  return { LOW: "info", MEDIUM: "", HIGH: "warning", URGENT: "danger" }[p] || "info";
}
function priorityText(p) {
  return { LOW: "低", MEDIUM: "中", HIGH: "高", URGENT: "紧急" }[p] || p;
}
function statusType(s) {
  return {
    PENDING_ASSIGN: "warning",
    PENDING_EXECUTE: "primary",
    IN_PROGRESS: "primary",
    PENDING_ACCEPT: "warning",
    COMPLETED: "success",
    CANCELLED: "info",
  }[s] || "info";
}
function statusText(s) {
  return {
    PENDING_ASSIGN: "待派单",
    PENDING_EXECUTE: "待执行",
    IN_PROGRESS: "执行中",
    PENDING_ACCEPT: "待验收",
    COMPLETED: "已完成",
    CANCELLED: "已取消",
  }[s] || s;
}

async function fetchOrders() {
  loading.value = true;
  try {
    orders.value = await workOrderApi.list({ status: statusFilter.value || undefined });
  } catch {
    orders.value = [];
  } finally {
    loading.value = false;
  }
}

async function fetchOptions() {
  const [devList, whList, userList] = await Promise.all([
    deviceApi.list(),
    warehouseApi.list(),
    userApi.list(),
  ]);
  devices.value = devList;
  warehouses.value = whList;
  users.value = userList;
}

function openCreate() {
  Object.assign(createForm, {
    warehouse_id: warehouses.value[0]?.id || null,
    device_id: null,
    title: "",
    description: "",
    priority: "MEDIUM",
  });
  createVisible.value = true;
}

async function handleCreate() {
  if (!createForm.device_id || !createForm.title) {
    ElMessage.warning("请选择设备并填写标题");
    return;
  }
  await workOrderApi.create(createForm);
  ElMessage.success("工单创建成功");
  createVisible.value = false;
  fetchOrders();
}

function openAssign(row) {
  currentOrder.value = row;
  assignUserId.value = null;
  assignVisible.value = true;
}

async function doAssign() {
  if (!assignUserId.value) {
    ElMessage.warning("请选择指派人");
    return;
  }
  await workOrderApi.transition(currentOrder.value.id, { action: "assign", assignee_id: assignUserId.value });
  ElMessage.success("派单成功");
  assignVisible.value = false;
  fetchOrders();
}

function openComplete(row) {
  currentOrder.value = row;
  completeResult.value = "";
  completeVisible.value = true;
}

async function doComplete() {
  await workOrderApi.transition(currentOrder.value.id, {
    action: "complete",
    result: completeResult.value || undefined,
  });
  ElMessage.success("工单已完成");
  completeVisible.value = false;
  fetchOrders();
}

async function doTransition(row, action) {
  await workOrderApi.transition(row.id, { action });
  ElMessage.success("状态已更新");
  fetchOrders();
}

onMounted(async () => {
  await fetchOptions();
  await fetchOrders();
});
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
.stat-value.yellow {
  color: var(--accent-yellow);
}
.stat-value.cyan {
  color: var(--accent);
}
.stat-value.orange {
  color: #fb923c;
}
.stat-value.green {
  color: var(--accent-green);
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
