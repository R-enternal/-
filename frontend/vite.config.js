import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// 前端开发服务器：/api 代理到后端 9901
export default defineConfig({
  plugins: [vue()],
  build: {
    rollupOptions: {
      output: {
        // 把体积大的三方依赖拆成独立 chunk，避免首屏加载单文件 1.7MB
        manualChunks: {
          "vendor-vue": ["vue", "vue-router", "pinia", "axios"],
          "vendor-element": ["element-plus", "@element-plus/icons-vue"],
          "vendor-echarts": ["echarts", "vue-echarts"],
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:9901",
        changeOrigin: true,
      },
    },
  },
});
