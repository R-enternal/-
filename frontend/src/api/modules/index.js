import request from "../request";

// 各业务模块 API（第 18 步联调时按需扩展）
export const deviceApi = {
  list: (params) => request.get("/devices", { params }),
  create: (data) => request.post("/devices", data),
  detail: (id) => request.get(`/devices/${id}`),
  updatePoint: (id, data) => request.put(`/devices/points/${id}`, data),
  sensorData: (id, params) => request.get(`/devices/${id}/sensor-data`, { params }),
};

export const overviewApi = {
  stats: () => request.get("/overview/stats"),
};

export const warehouseApi = {
  list: () => request.get("/warehouses"),
};

export const userApi = {
  list: () => request.get("/auth/users"),
};

export const alertApi = {
  list: (params) => request.get("/alerts", { params }),
  handle: (id, data) => request.post(`/alerts/${id}/handle`, data),
  ignore: (id, data) => request.post(`/alerts/${id}/ignore`, data),
  convert: (id) => request.post(`/alerts/${id}/convert`),
};

export const workOrderApi = {
  list: (params) => request.get("/work-orders", { params }),
  create: (data) => request.post("/work-orders", data),
  transition: (id, data) => request.post(`/work-orders/${id}/transition`, data),
  addPart: (id, data) => request.post(`/work-orders/${id}/parts`, data),
};

export const sparePartApi = {
  list: (params) => request.get("/spare-parts", { params }),
  create: (data) => request.post("/spare-parts", data),
  inbound: (id, data) => request.post(`/spare-parts/${id}/inbound`, data),
  outbound: (id, data) => request.post(`/spare-parts/${id}/outbound`, data),
};

export const healthApi = {
  list: (params) => request.get("/health", { params }),
};

export const notificationApi = {
  list: (params) => request.get("/notifications", { params }),
  unreadCount: (params) => request.get("/notifications/unread-count", { params }),
  markRead: (data) => request.post("/notifications/read", data),
};

export const authApi = {
  login: (data) => request.post("/auth/login", data),
};

export const agentApi = {
  chat: (data) => request.post("/agent/chat", data),
  maintenanceSuggestions: () => request.get("/agent/maintenance-suggestions"),
  saveMaintenancePlans: (data) => request.post("/agent/maintenance-plans/save", data),
  listMaintenancePlans: (params) => request.get("/agent/maintenance-plans", { params }),
  convertPlan: (id) => request.post(`/agent/maintenance-plans/${id}/convert`),
  assignSuggestions: () => request.get("/agent/assign-suggestions"),
  clearSession: (sessionId) => request.post("/agent/session/clear", { session_id: sessionId }),
  sessionHistory: (sessionId) => request.get(`/agent/session/${sessionId}/history`),
};

export const kbApi = {
  upload: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return request.post("/kb/upload", fd, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  list: () => request.get("/kb/documents"),
  remove: (id) => request.delete(`/kb/documents/${id}`),
  search: (q, k = 4) => request.get("/kb/search", { params: { q, k } }),
  seed: () => request.post("/kb/seed"),
};

export const diagnosisApi = {
  latest: (deviceId) =>
    request.get("/diagnosis", { params: { device_id: deviceId, limit: 1 } }),
  diagnose: (deviceId) => request.get(`/diagnosis/${deviceId}`),
};
