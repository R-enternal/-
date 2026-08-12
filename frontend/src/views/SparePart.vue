<template>
  <div class="page-wrap">
    <!-- 页面统计 -->
    <div class="stat-chips">
      <div class="stat-chip">
        <span class="stat-value cyan">{{ parts.length }}</span>
        <span class="stat-label">备件种类</span>
      </div>
      <div class="stat-chip">
        <span class="stat-value blue">{{ totalStock }}</span>
        <span class="stat-label">库存总量</span>
      </div>
      <div class="stat-chip">
        <span class="stat-value red">{{ lowStockCount }}</span>
        <span class="stat-label">低库存</span>
      </div>
      <div class="stat-chip">
        <span class="stat-value green">{{ parts.length - lowStockCount }}</span>
        <span class="stat-label">库存正常</span>
      </div>
    </div>

    <el-card>
      <template #header>
        <div class="card-header">
          <span class="panel-title">备件清单</span>
          <div class="header-actions">
            <el-input
              v-model="keyword"
              placeholder="搜索编号 / 名称 / 规格"
              clearable
              size="small"
              style="width: 220px"
              :prefix-icon="Search"
            />
            <el-checkbox v-model="lowStockOnly" @change="fetchParts">仅看低库存</el-checkbox>
            <el-button type="primary" size="small" @click="openCreate">新建备件</el-button>
          </div>
        </div>
      </template>

      <el-table v-loading="loading" :data="filteredParts" stripe>
        <el-table-column prop="part_code" label="编号" width="130" />
        <el-table-column prop="name" label="名称" min-width="130" show-overflow-tooltip />
        <el-table-column prop="spec" label="规格" width="110" />
        <el-table-column label="库存" width="180">
          <template #default="{ row }">
            <div class="stock-cell">
              <span class="stock-num" :class="{ danger: isLow(row) }">{{ row.stock_quantity }}</span>
              <el-progress
                :percentage="stockPercent(row)"
                :stroke-width="6"
                :show-text="false"
                :color="isLow(row) ? '#ef4444' : '#10b981'"
                class="stock-progress"
              />
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="safe_quantity" label="安全库存" width="90" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="isLow(row) ? 'danger' : 'success'" size="small" effect="dark">
              {{ isLow(row) ? "低库存" : "正常" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="storage_location" label="库位" width="100" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="success" @click="openStock(row, 'inbound')">入库</el-button>
            <el-button size="small" type="warning" @click="openStock(row, 'outbound')">出库</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建备件 -->
    <el-dialog v-model="createVisible" title="新建备件" width="480px">
      <el-form label-width="90px">
        <el-form-item label="备件编号" required>
          <el-input v-model="createForm.part_code" />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="createForm.name" />
        </el-form-item>
        <el-form-item label="规格">
          <el-input v-model="createForm.spec" />
        </el-form-item>
        <el-form-item label="安全库存">
          <el-input-number v-model="createForm.safe_quantity" :min="0" />
        </el-form-item>
        <el-form-item label="库位">
          <el-input v-model="createForm.storage_location" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 入库/出库 -->
    <el-dialog :title="stockAction === 'inbound' ? '入库' : '出库'" v-model="stockVisible" width="420px">
      <el-form label-width="80px">
        <el-form-item label="备件">
          <span>{{ currentPart?.name }}（当前库存 {{ currentPart?.stock_quantity }}）</span>
        </el-form-item>
        <el-form-item label="数量" required>
          <el-input-number v-model="stockForm.quantity" :min="1" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="stockForm.remark" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="stockVisible = false">取消</el-button>
        <el-button type="primary" @click="handleStock">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { Search } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

import { sparePartApi, warehouseApi } from "../api/modules";

const loading = ref(false);
const parts = ref([]);
const warehouses = ref([]);
const lowStockOnly = ref(false);
const keyword = ref("");
const createVisible = ref(false);
const stockVisible = ref(false);
const stockAction = ref("inbound");
const currentPart = ref(null);
const createForm = reactive({
  warehouse_id: null,
  part_code: "",
  name: "",
  spec: "",
  safe_quantity: 5,
  storage_location: "",
});
const stockForm = reactive({ quantity: 1, remark: "" });

const filteredParts = computed(() => {
  const kw = keyword.value.trim().toLowerCase();
  if (!kw) return parts.value;
  return parts.value.filter((p) =>
    [p.part_code, p.name, p.spec].some((v) => (v || "").toLowerCase().includes(kw))
  );
});

const totalStock = computed(() => parts.value.reduce((sum, p) => sum + (p.stock_quantity || 0), 0));
const lowStockCount = computed(() => parts.value.filter(isLow).length);

function isLow(p) {
  return p.safe_quantity > 0 && p.stock_quantity < p.safe_quantity;
}
function stockPercent(p) {
  if (p.safe_quantity <= 0) return 100;
  return Math.min(Math.round((p.stock_quantity / p.safe_quantity) * 100), 100);
}

async function fetchParts() {
  loading.value = true;
  try {
    parts.value = await sparePartApi.list({ low_stock: lowStockOnly.value || undefined });
  } catch {
    parts.value = [];
  } finally {
    loading.value = false;
  }
}

async function fetchWarehouses() {
  warehouses.value = await warehouseApi.list();
}

function openCreate() {
  Object.assign(createForm, {
    warehouse_id: warehouses.value[0]?.id || null,
    part_code: "",
    name: "",
    spec: "",
    safe_quantity: 5,
    storage_location: "",
  });
  createVisible.value = true;
}

async function handleCreate() {
  if (!createForm.part_code || !createForm.name) {
    ElMessage.warning("请填写编号和名称");
    return;
  }
  await sparePartApi.create(createForm);
  ElMessage.success("备件创建成功");
  createVisible.value = false;
  fetchParts();
}

function openStock(row, action) {
  currentPart.value = row;
  stockAction.value = action;
  Object.assign(stockForm, { quantity: 1, remark: "" });
  stockVisible.value = true;
}

async function handleStock() {
  const fn = stockAction.value === "inbound" ? sparePartApi.inbound : sparePartApi.outbound;
  await fn(currentPart.value.id, stockForm);
  ElMessage.success(stockAction.value === "inbound" ? "入库成功" : "出库成功");
  stockVisible.value = false;
  fetchParts();
}

onMounted(async () => {
  await fetchWarehouses();
  await fetchParts();
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
.stat-value.cyan {
  color: var(--accent);
}
.stat-value.blue {
  color: var(--accent-blue);
}
.stat-value.red {
  color: var(--accent-red);
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
.stock-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}
.stock-num {
  font-weight: 700;
  min-width: 24px;
}
.stock-num.danger {
  color: var(--accent-red);
}
.stock-progress {
  flex: 1;
}
</style>
