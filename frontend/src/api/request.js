import axios from "axios";
import { ElMessage } from "element-plus";

import router from "../router";

// axios 封装：baseURL 指向后端（vite proxy /api → 9901）
const request = axios.create({
  baseURL: "/api",
  timeout: 15000,
});

// 请求拦截：注入 token
request.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截：统一拆 {code, message, data}，code 非 200 报错
request.interceptors.response.use(
  (response) => {
    const { code, message, data } = response.data;
    if (code === 200) {
      return data;
    }
    ElMessage.error(message || "请求失败");
    return Promise.reject(new Error(message || "请求失败"));
  },
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      router.push("/login");
      ElMessage.error("登录已失效，请重新登录");
    } else {
      ElMessage.error(error.response?.data?.message || error.message || "网络错误");
    }
    return Promise.reject(error);
  }
);

export default request;
