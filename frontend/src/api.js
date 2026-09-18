import axios from "axios"

const client = axios.create({
  baseURL: "/api",
  timeout: 8000,
})

export const statsApi = {
  overview: (params = {}) => client.get("/stats/overview", { params }),
  topics: (params = {}) => client.get("/stats/topics", { params }),
  graph: (params = {}) => client.get("/stats/graph", { params }),
  trends: (params = {}) => client.get("/stats/trends", { params }),
}

export const papersApi = {
  list: (params = {}) => client.get("/papers", { params }),
  get: (id) => client.get(`/papers/${id}`),
  create: (payload) => client.post("/papers", payload),
  update: (id, payload) => client.put(`/papers/${id}`, payload),
  remove: (id) => client.delete(`/papers/${id}`),
  lookup: (title) => client.get("/papers/lookup", { params: { title } }),
  importCsv: (file) => {
    const form = new FormData()
    form.append("file", file)
    return client.post("/papers/import", form)
  },
}

export function getErrorMessage(error, fallback = "请求失败，请稍后重试") {
  return error?.response?.data?.detail || error?.message || fallback
}
