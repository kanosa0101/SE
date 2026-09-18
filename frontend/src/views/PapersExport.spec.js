// @vitest-environment jsdom

import { flushPromises, mount } from "@vue/test-utils"
import { createMemoryHistory, createRouter } from "vue-router"
import { beforeEach, describe, expect, it, vi } from "vitest"

const api = vi.hoisted(() => ({ list: vi.fn(), export: vi.fn() }))

vi.mock("../api", () => ({
  papersApi: api,
  getErrorMessage: (error, fallback) => error?.message || fallback,
}))

import PapersView from "./PapersView.vue"

describe("PapersView exports", () => {
  beforeEach(() => {
    api.list.mockReset()
    api.export.mockReset()
    api.list.mockResolvedValue({ data: { items: [], total: 0 } })
    api.export.mockResolvedValue({ data: new Blob(["title"]) })
    Object.defineProperty(window.URL, "createObjectURL", { configurable: true, value: vi.fn(() => "blob:test") })
    Object.defineProperty(window.URL, "revokeObjectURL", { configurable: true, value: vi.fn() })
    Object.defineProperty(HTMLAnchorElement.prototype, "click", { configurable: true, value: vi.fn() })
  })

  it("exports the active filters without pagination", async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: "/papers", name: "papers", component: PapersView }],
    })
    await router.push({ name: "papers", query: { q: "vision", conference: "CVPR", year_from: "2021", year_to: "2024" } })

    const wrapper = mount(PapersView, {
      global: {
        plugins: [router],
        stubs: {
          AppShell: { template: "<div><slot /></div>" },
          PaperForm: true,
          PaperTable: true,
        },
      },
    })
    await flushPromises()

    await wrapper.get(".export-csv").trigger("click")
    await flushPromises()

    expect(api.export).toHaveBeenCalledWith("csv", {
      q: "vision",
      conference: "CVPR",
      year_from: 2021,
      year_to: 2024,
    })
    expect(window.URL.createObjectURL).toHaveBeenCalled()
    expect(window.URL.revokeObjectURL).toHaveBeenCalledWith("blob:test")
  })

  it("releases the Blob URL when the browser click fails", async () => {
    Object.defineProperty(HTMLAnchorElement.prototype, "click", { configurable: true, value: vi.fn(() => { throw new Error("download blocked") }) })
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: "/papers", name: "papers", component: PapersView }],
    })
    await router.push({ name: "papers" })
    const wrapper = mount(PapersView, {
      global: {
        plugins: [router],
        stubs: {
          AppShell: { template: "<div><slot /></div>" },
          PaperForm: true,
          PaperTable: true,
        },
      },
    })
    await flushPromises()

    await wrapper.get(".export-csv").trigger("click")
    await flushPromises()

    expect(window.URL.revokeObjectURL).toHaveBeenCalledWith("blob:test")
    expect(wrapper.text()).toContain("download blocked")
  })

  it("reads a JSON detail from a Blob error response", async () => {
    api.export.mockRejectedValueOnce({
      response: { data: new Blob([JSON.stringify({ detail: "导出被拒绝" })], { type: "application/json" }) },
    })
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: "/papers", name: "papers", component: PapersView }],
    })
    await router.push({ name: "papers" })
    const wrapper = mount(PapersView, {
      global: {
        plugins: [router],
        stubs: {
          AppShell: { template: "<div><slot /></div>" },
          PaperForm: true,
          PaperTable: true,
        },
      },
    })
    await flushPromises()

    await wrapper.get(".export-csv").trigger("click")
    await flushPromises()
    await new Promise((resolve) => setTimeout(resolve, 0))
    await flushPromises()

    expect(wrapper.text()).toContain("导出被拒绝")
  })
})
