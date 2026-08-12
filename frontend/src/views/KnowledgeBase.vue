<template>
  <div class="page-wrap">
    <el-row :gutter="14">
      <!-- 左：文档管理 -->
      <el-col :xs="24" :lg="14">
        <el-card>
          <template #header>
            <div class="card-header">
              <span class="panel-title">文档管理</span>
              <span class="muted">支持 .md / .txt，UTF-8 编码</span>
            </div>
          </template>

          <el-upload
            drag
            action="#"
            :auto-upload="false"
            :limit="1"
            accept=".md,.txt,.markdown"
            :on-change="onFileChange"
            :file-list="fileList"
          >
            <el-icon :size="40" class="upload-icon"><UploadFilled /></el-icon>
            <div class="el-upload__text">拖拽文档到此处，或 <em>点击选择</em></div>
            <template #tip>
              <div class="el-upload__tip">维保手册、故障案例、操作规范等 Markdown/文本文档</div>
            </template>
          </el-upload>
          <div class="upload-actions">
            <el-button type="primary" :loading="uploading" :disabled="!selectedFile" @click="handleUpload">
              上传并建立索引
            </el-button>
            <el-button :loading="seeding" @click="seedDemo">灌入演示手册</el-button>
          </div>

          <el-table v-loading="loading" :data="documents" size="small" class="doc-table">
            <el-table-column prop="filename" label="文件名" min-width="200" show-overflow-tooltip />
            <el-table-column prop="doc_type" label="类型" width="80" />
            <el-table-column prop="chunk_count" label="切块" width="70" />
            <el-table-column prop="status" label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="row.status === 'READY' ? 'success' : 'danger'" size="small">
                  {{ row.status === "READY" ? "已索引" : "失败" }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="上传时间" width="140">
              <template #default="{ row }">{{ (row.created_at || "").slice(0, 16).replace("T", " ") }}</template>
            </el-table-column>
            <el-table-column label="操作" width="80" fixed="right">
              <template #default="{ row }">
                <el-button size="small" text type="danger" @click="removeDoc(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <!-- 右：检索测试 -->
      <el-col :xs="24" :lg="10">
        <el-card>
          <template #header>
            <span class="panel-title">语义检索测试</span>
          </template>
          <div class="search-row">
            <el-input
              v-model="query"
              placeholder="试试：电机过热怎么排查？输送机如何保养？"
              clearable
              @keyup.enter="doSearch"
            />
            <el-button type="primary" :loading="searching" @click="doSearch">检索</el-button>
          </div>

          <div v-if="searchResults.length" class="search-results">
            <div v-for="(r, i) in searchResults" :key="i" class="search-item">
              <div class="search-head">
                <span class="search-source">{{ r.source }}</span>
                <span class="muted">相似度 {{ r.score }}</span>
              </div>
              <div class="search-content">{{ r.content }}</div>
            </div>
          </div>
          <el-empty v-else description="输入问题后点击检索，验证知识库命中效果" :image-size="70" />

          <el-alert
            class="kb-tip"
            type="info"
            :closable="false"
            title="在「智能助手」里直接问知识性问题，Agent 会自动检索知识库并回答，例如：电机过热怎么排查？"
          />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { UploadFilled } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";

import { kbApi } from "../api/modules";

const loading = ref(false);
const uploading = ref(false);
const seeding = ref(false);
const searching = ref(false);
const documents = ref([]);
const fileList = ref([]);
const selectedFile = ref(null);
const query = ref("");
const searchResults = ref([]);

async function fetchDocuments() {
  loading.value = true;
  try {
    documents.value = await kbApi.list();
  } catch {
    documents.value = [];
  } finally {
    loading.value = false;
  }
}

function onFileChange(file) {
  selectedFile.value = file.raw;
}

async function handleUpload() {
  if (!selectedFile.value) return;
  uploading.value = true;
  try {
    const resp = await kbApi.upload(selectedFile.value);
    ElMessage.success(resp.message || "上传成功");
    selectedFile.value = null;
    fileList.value = [];
    await fetchDocuments();
  } catch {
    // 拦截器已提示
  } finally {
    uploading.value = false;
  }
}

async function seedDemo() {
  seeding.value = true;
  try {
    const resp = await kbApi.seed();
    ElMessage.success(resp.message || "演示手册已灌入");
    await fetchDocuments();
  } finally {
    seeding.value = false;
  }
}

async function removeDoc(row) {
  await ElMessageBox.confirm(`确定删除「${row.filename}」及其向量索引吗？`, "删除文档", {
    type: "warning",
  });
  await kbApi.remove(row.id);
  ElMessage.success("已删除");
  await fetchDocuments();
}

async function doSearch() {
  const q = query.value.trim();
  if (!q) return;
  searching.value = true;
  try {
    searchResults.value = await kbApi.search(q);
  } finally {
    searching.value = false;
  }
}

onMounted(fetchDocuments);
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.upload-icon {
  color: var(--accent);
  margin-bottom: 6px;
}
.upload-actions {
  display: flex;
  gap: 8px;
  margin: 10px 0 16px;
}
.doc-table {
  margin-top: 4px;
}
.search-row {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
}
.search-results {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.search-item {
  background: #f4f6fb;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 10px 12px;
}
.search-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.search-source {
  font-size: 12px;
  color: var(--accent);
  font-weight: 600;
}
.search-content {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-main);
  white-space: pre-wrap;
  display: -webkit-box;
  -webkit-line-clamp: 5;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.kb-tip {
  margin-top: 16px;
}
</style>
