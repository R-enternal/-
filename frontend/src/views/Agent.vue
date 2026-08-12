<template>
  <div class="page-wrap agent-page">
    <el-row :gutter="14">
      <!-- 左：智能对话 -->
      <el-col :xs="24" :lg="14">
        <el-card class="chat-card">
          <template #header>
            <div class="chat-head">
              <span class="panel-title">智能查询</span>
              <el-button size="small" text type="primary" @click="clearChat">清空会话</el-button>
            </div>
          </template>

          <div ref="chatBodyRef" class="chat-body">
            <div
              v-for="(m, i) in messages"
              :key="i"
              class="msg"
              :class="m.role === 'user' ? 'msg-user' : 'msg-assistant'"
            >
              <div class="msg-avatar" :class="m.role === 'user' ? 'avatar-user' : 'avatar-ai'">
                {{ m.role === "user" ? "我" : "AI" }}
              </div>
              <div class="msg-bubble" :class="{ streaming: m.streaming }">
                <div v-if="m.toolCalls?.length" class="msg-tools">
                  <el-tag v-for="(t, ti) in m.toolCalls" :key="ti" size="small" effect="plain">
                    ⚙ {{ t }}
                  </el-tag>
                </div>
                <div class="msg-text">{{ m.content }}</div>
              </div>
            </div>
            <div v-if="chatLoading" class="msg msg-assistant">
              <div class="msg-avatar avatar-ai">AI</div>
              <div class="msg-bubble thinking">
                <span class="dot-pulse"></span> 正在思考...
              </div>
            </div>
          </div>

          <div class="quick-questions">
            <el-tag
              v-for="q in quickQuestions"
              :key="q"
              size="small"
              effect="plain"
              class="quick-tag"
              @click="ask(q)"
            >
              {{ q }}
            </el-tag>
          </div>

          <div class="chat-input">
            <el-input
              v-model="question"
              placeholder="问我：1号输送线健康度怎么样？有哪些待处理告警？"
              clearable
              @keyup.enter="sendQuestion"
            />
            <el-button type="primary" :loading="chatLoading" @click="sendQuestion">发送</el-button>
          </div>
        </el-card>
      </el-col>

      <!-- 右：维保计划 + 智能调度 -->
      <el-col :xs="24" :lg="10">
        <el-card class="plan-card">
          <template #header>
            <div class="plan-head">
              <span class="panel-title">AI 维保计划</span>
              <div>
                <el-button size="small" :loading="planLoading" @click="runPlan">生成计划</el-button>
                <el-button
                  size="small"
                  type="success"
                  :disabled="!planReport || planSaved"
                  @click="savePlan"
                >
                  保存落库
                </el-button>
              </div>
            </div>
          </template>

          <div v-if="planSteps.length" class="plan-steps">
            <div v-for="(s, i) in planSteps" :key="i" class="plan-step">
              <span class="step-no">{{ i + 1 }}</span>
              <span class="step-text">{{ s }}</span>
            </div>
          </div>

          <div v-if="planReport" class="plan-report">
            <pre>{{ planReport }}</pre>
          </div>
          <el-empty v-else description="点击「生成计划」，AI 将根据健康度、告警与忙闲生成维保方案" :image-size="70" />

          <template v-if="plans.length">
            <h4 class="sub-title">已保存计划（可转工单）</h4>
            <el-table :data="plans" size="small" max-height="240">
              <el-table-column prop="device_name" label="设备" min-width="110" show-overflow-tooltip />
              <el-table-column label="类型" width="80">
                <template #default="{ row }">{{ taskTypeText(row.task_type) }}</template>
              </el-table-column>
              <el-table-column prop="plan_date" label="日期" width="100" />
              <el-table-column prop="start_time" label="建议时段" width="110">
                <template #default="{ row }">{{ row.start_time || "--" }} ~ {{ row.end_time || "--" }}</template>
              </el-table-column>
              <el-table-column prop="status" label="状态" width="90">
                <template #default="{ row }">
                  <el-tag size="small" :type="planStatusType(row.status)">{{ planStatusText(row.status) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="90" fixed="right">
                <template #default="{ row }">
                  <el-button
                    v-if="row.status === 'DRAFT'"
                    size="small"
                    type="warning"
                    @click="convertPlan(row)"
                  >
                    转工单
                  </el-button>
                  <span v-else class="muted">-</span>
                </template>
              </el-table-column>
            </el-table>
          </template>
        </el-card>

        <el-card class="assign-card">
          <template #header>
            <div class="plan-head">
              <span class="panel-title">智能调度建议</span>
              <el-button size="small" :loading="assignLoading" @click="loadAssignSuggestions">
                生成建议
              </el-button>
            </div>
          </template>
          <div v-if="assignSuggestions.length" class="assign-list">
            <div v-for="s in assignSuggestions" :key="s.order_id" class="assign-item">
              <div class="assign-info">
                <div class="assign-title">{{ s.title }}</div>
                <div class="assign-meta">
                  {{ s.order_no }} · {{ s.device_name }} · {{ priorityText(s.priority) }} ·
                  健康度 {{ s.device_score }}
                </div>
                <div class="assign-reason muted">{{ s.reason }}</div>
              </div>
              <div class="assign-action">
                <el-select v-model="assignMap[s.order_id]" size="small" placeholder="选指派人" style="width: 110px">
                  <el-option
                    v-for="u in workers"
                    :key="u.id"
                    :label="u.real_name || u.username"
                    :value="u.id"
                  />
                </el-select>
                <el-button size="small" type="primary" @click="confirmAssign(s)">派单</el-button>
              </div>
            </div>
          </div>
          <el-empty v-else description="点击「生成建议」，AI 按优先级与健康度推荐派单顺序" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { nextTick, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";

import { agentApi, userApi, workOrderApi } from "../api/modules";

// 每个标签页独立的会话 ID：避免多个窗口共用同一个会话，
// 一个窗口的异常历史污染所有用户的对话；刷新页面后同标签页仍可恢复。
function getAgentSessionId() {
  let sid = sessionStorage.getItem("agent_session_id");
  if (!sid) {
    sid = `web-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
    sessionStorage.setItem("agent_session_id", sid);
  }
  return sid;
}
const SESSION_ID = getAgentSessionId();

const chatBodyRef = ref(null);
const messages = ref([]);
const question = ref("");
const chatLoading = ref(false);

const planLoading = ref(false);
const planSteps = ref([]);
const planReport = ref("");
const planSaved = ref(false);
const plans = ref([]);

const assignLoading = ref(false);
const assignSuggestions = ref([]);
const assignMap = reactive({});
const workers = ref([]);

const quickQuestions = ["有哪些待处理告警", "1号输送线健康度怎么样", "有哪些低库存备件", "仓库今天忙闲如何"];

/* ---------- 对话 ---------- */
function scrollBottom() {
  nextTick(() => {
    if (chatBodyRef.value) chatBodyRef.value.scrollTop = chatBodyRef.value.scrollHeight;
  });
}

async function ask(q) {
  question.value = q;
  await sendQuestion();
}

async function sendQuestion() {
  const q = question.value.trim();
  if (!q || chatLoading.value) return;
  question.value = "";
  messages.value.push({ role: "user", content: q });
  const assistant = reactive({ role: "assistant", content: "", toolCalls: [], streaming: true });
  messages.value.push(assistant);
  chatLoading.value = true;
  scrollBottom();

  try {
    const resp = await fetch("/api/agent/chat_stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: SESSION_ID, question: q }),
    });
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      buf = buf.replace(/\r\n/g, "\n"); // SSE 事件以 CRLF 分隔，统一换行便于解析
      let idx;
      while ((idx = buf.indexOf("\n\n")) >= 0) {
        const raw = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        for (const line of raw.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          const evt = JSON.parse(line.slice(6));
          if (evt.type === "tool_call") assistant.toolCalls.push(evt.data);
          else if (evt.type === "content") assistant.content += evt.data;
          else if (evt.type === "error") assistant.content += `\n[错误] ${evt.data}`;
        }
        scrollBottom();
      }
    }
  } catch (e) {
    assistant.content = `连接失败：${e.message}`;
  } finally {
    assistant.streaming = false;
    chatLoading.value = false;
    scrollBottom();
  }
}

async function clearChat() {
  messages.value = [];
  await agentApi.clearSession(SESSION_ID);
  sessionStorage.removeItem("agent_session_id");
  ElMessage.success("会话已清空");
}

async function loadHistory() {
  try {
    const history = await agentApi.sessionHistory(SESSION_ID);
    messages.value = history.map((m) => ({
      role: m.role,
      content: m.content,
      toolCalls: m.tools || [],
      streaming: false,
    }));
    scrollBottom();
  } catch {
    messages.value = [];
  }
}

/* ---------- 维保计划 ---------- */
async function runPlan() {
  planLoading.value = true;
  planSteps.value = [];
  planReport.value = "";
  planSaved.value = false;
  try {
    const resp = await fetch("/api/agent/plan_stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: SESSION_ID, task: "生成明天的维保计划" }),
    });
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      buf = buf.replace(/\r\n/g, "\n"); // SSE 事件以 CRLF 分隔，统一换行便于解析
      let idx;
      while ((idx = buf.indexOf("\n\n")) >= 0) {
        const raw = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        for (const line of raw.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          const evt = JSON.parse(line.slice(6));
          if (evt.type === "plan") planSteps.value = evt.data;
          else if (evt.type === "step_complete") planSteps.value.push(`✓ ${evt.step}`);
          else if (evt.type === "report") planReport.value = evt.data;
          else if (evt.type === "error") planReport.value = `[错误] ${evt.data}`;
        }
      }
    }
  } catch (e) {
    planReport.value = `连接失败：${e.message}`;
  } finally {
    planLoading.value = false;
  }
}

async function savePlan() {
  if (!planReport.value) return;
  const resp = await agentApi.saveMaintenancePlans({ plan_date: null, created_by: "admin" });
  ElMessage.success(resp.message || `已保存 ${resp.saved} 条`);
  planSaved.value = true;
  await fetchPlans();
}

async function convertPlan(row) {
  await agentApi.convertPlan(row.id);
  ElMessage.success("已转工单");
  await fetchPlans();
}

async function fetchPlans() {
  plans.value = await agentApi.listMaintenancePlans();
}

/* ---------- 智能调度 ---------- */
async function loadAssignSuggestions() {
  assignLoading.value = true;
  try {
    const [suggestions, userList] = await Promise.all([
      agentApi.assignSuggestions(),
      userApi.list(),
    ]);
    assignSuggestions.value = suggestions;
    workers.value = userList.filter((u) => u.role === "MAINTENANCE_WORKER" && u.status === "ACTIVE");
    for (const s of suggestions) {
      if (assignMap[s.order_id] === undefined && s.suggested_assignee_id != null) {
        assignMap[s.order_id] = s.suggested_assignee_id;
      }
    }
  } finally {
    assignLoading.value = false;
  }
}

async function confirmAssign(s) {
  const assigneeId = assignMap[s.order_id];
  if (!assigneeId) {
    ElMessage.warning("请选择指派人");
    return;
  }
  await workOrderApi.transition(s.order_id, { action: "assign", assignee_id: assigneeId });
  ElMessage.success("派单成功");
  await loadAssignSuggestions();
}

/* ---------- 工具函数 ---------- */
function taskTypeText(t) {
  return { REPAIR: "检修", MAINTAIN: "保养", INSPECT: "巡检" }[t] || t;
}
function planStatusType(s) {
  return { DRAFT: "info", CONFIRMED: "warning", EXECUTED: "success", CANCELLED: "danger" }[s] || "info";
}
function planStatusText(s) {
  return { DRAFT: "草稿", CONFIRMED: "已转工单", EXECUTED: "已执行", CANCELLED: "已取消" }[s] || s;
}
function priorityText(p) {
  return { LOW: "低", MEDIUM: "中", HIGH: "高", URGENT: "紧急" }[p] || p;
}

onMounted(async () => {
  await loadHistory();
  await fetchPlans();
});
</script>

<style scoped>
.chat-card {
  display: flex;
  flex-direction: column;
}
.chat-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.chat-body {
  height: 620px;
  overflow: auto;
  padding: 4px 8px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.msg {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}
.msg-user {
  flex-direction: row-reverse;
}
.msg-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}
.avatar-user {
  background: rgba(14, 165, 233, 0.14);
  color: var(--accent);
}
.avatar-ai {
  background: linear-gradient(135deg, #22d3ee, #0ea5e9);
  color: #04121f;
}
.msg-bubble {
  max-width: 78%;
  padding: 10px 14px;
  border-radius: 12px;
  background: #f4f6fb;
  border: 1px solid var(--border);
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
.msg-user .msg-bubble {
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.14), rgba(14, 165, 233, 0.07));
  border-color: rgba(14, 165, 233, 0.35);
}
.msg-bubble.streaming {
  border-color: rgba(14, 165, 233, 0.5);
}
.msg-tools {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 6px;
}
.msg-text {
  white-space: pre-wrap;
}
.thinking {
  color: var(--text-sub);
  display: flex;
  align-items: center;
  gap: 8px;
}
.dot-pulse {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
  animation: pulse 1s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 0.3; }
  50% { opacity: 1; }
}
.quick-questions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 10px 4px 4px;
}
.quick-tag {
  cursor: pointer;
}
.quick-tag:hover {
  color: var(--accent);
  border-color: var(--accent);
}
.chat-input {
  display: flex;
  gap: 8px;
  padding-top: 8px;
}

.plan-card,
.assign-card {
  margin-bottom: 14px;
}
.plan-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.plan-steps {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 12px;
}
.plan-step {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.step-no {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: rgba(14, 165, 233, 0.14);
  color: var(--accent);
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.step-text {
  color: var(--text-main);
}
.plan-report {
  max-height: 260px;
  overflow: auto;
  background: #f4f6fb;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px;
  margin-bottom: 12px;
}
.plan-report pre {
  font-family: inherit;
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-main);
  white-space: pre-wrap;
}
.sub-title {
  margin: 12px 0 8px;
  font-size: 14px;
}
.assign-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.assign-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  padding: 10px;
  background: #f4f6fb;
  border: 1px solid var(--border);
  border-radius: 10px;
}
.assign-info {
  min-width: 0;
}
.assign-title {
  font-size: 13px;
  font-weight: 600;
}
.assign-meta {
  font-size: 12px;
  color: var(--text-sub);
  margin-top: 2px;
}
.assign-reason {
  font-size: 11px;
  margin-top: 2px;
}
.assign-action {
  display: flex;
  gap: 6px;
  align-items: center;
  flex-shrink: 0;
}
</style>
