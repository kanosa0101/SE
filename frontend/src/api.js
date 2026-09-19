import axios from "axios"

const client = axios.create({
  baseURL: "/api",
  // 统计接口在 12k+ 记录、SQLite 冷缓存时可达数秒，给足重查询余量。
  timeout: 15000,
})

export const statsApi = {
  overview: (params = {}) => client.get("/stats/overview", { params }),
  topics: (params = {}) => client.get("/stats/topics", { params }),
  graph: (params = {}) => client.get("/stats/graph", { params }),
  trends: (params = {}) => client.get("/stats/trends", { params }),
  evolution: (limit = 10) => client.get("/stats/evolution", { params: { limit } }),
  quality: () => client.get("/stats/quality"),
  inspector: (keyword) => client.get(`/stats/topics/${encodeURIComponent(keyword)}/inspector`),
}

export const papersApi = {
  list: (params = {}) => client.get("/papers", { params }),
  get: (id) => client.get(`/papers/${id}`),
  create: (payload) => client.post("/papers", payload),
  update: (id, payload) => client.put(`/papers/${id}`, payload),
  remove: (id) => client.delete(`/papers/${id}`),
  lookup: (title) => client.get("/papers/lookup", { params: { title } }),
  export: (format = "csv", params = {}) => client.get("/papers/export", { params: { format, ...params }, responseType: "blob" }),
  importCsv: (file) => {
    const form = new FormData()
    form.append("file", file)
    return client.post("/papers/import", form)
  },
}

export function getErrorMessage(error, fallback = "请求失败，请稍后重试") {
  return error?.response?.data?.detail || error?.message || fallback
}
