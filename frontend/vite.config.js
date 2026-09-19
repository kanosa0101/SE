import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
  build: {
    // echarts 按需引入（core+graph+line）单独分包后约 525 kB，属图表库固有体积。
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks: {
          echarts: ["echarts"],
          vendor: ["vue", "vue-router", "axios"],
        },
      },
    },
  },
  test: {
    environment: "node",
  },
})
