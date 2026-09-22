import { beforeEach, describe, expect, it, vi } from "vitest"

const api = vi.hoisted(() => ({
  client: {
    get: vi.fn().mockResolvedValue({ data: {} }),
    post: vi.fn().mockResolvedValue({ data: {} }),
  },
}))

vi.mock("axios", () => ({
  default: {
    create: vi.fn(() => api.client),
  },
}))

import { papersApi, statsApi } from "./api"

describe("papersApi long-running requests", () => {
  beforeEach(() => {
    api.client.get.mockClear()
    api.client.post.mockClear()
  })

  it("allows enough time for CVF website lookup", async () => {
    await papersApi.lookup("A Test Paper")

    expect(api.client.get).toHaveBeenCalledWith("/papers/lookup", {
      params: { title: "A Test Paper" },
      timeout: 600_000,
    })
  })

  it("allows enough time for large CSV import", async () => {
    await papersApi.importCsv(new Blob(["title,conference,year\nPaper,CVPR,2024\n"]))

    expect(api.client.post).toHaveBeenCalledWith(
      "/papers/import",
      expect.any(FormData),
      { timeout: 600_000 },
    )
  })

  it("allows enough time for topic inspector aggregation", async () => {
    await statsApi.inspector("Object Detection", "area")

    expect(api.client.get).toHaveBeenCalledWith(
      "/stats/topics/Object%20Detection/inspector",
      { params: { scope: "area" }, timeout: 60_000 },
    )
  })

  it("allows enough time for homepage statistics", async () => {
    const params = { conference: "CVPR" }

    await statsApi.overview(params)
    await statsApi.topics(params)
    await statsApi.graph(params)

    expect(api.client.get).toHaveBeenNthCalledWith(1, "/stats/overview", { params, timeout: 60_000 })
    expect(api.client.get).toHaveBeenNthCalledWith(2, "/stats/topics", { params, timeout: 60_000 })
    expect(api.client.get).toHaveBeenNthCalledWith(3, "/stats/graph", { params, timeout: 60_000 })
  })
})
