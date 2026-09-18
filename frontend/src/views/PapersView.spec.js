// @vitest-environment jsdom

import { flushPromises, mount } from "@vue/test-utils"
import { createMemoryHistory, createRouter } from "vue-router"
import { beforeEach, describe, expect, it, vi } from "vitest"

const api = vi.hoisted(() => ({ list: vi.fn() }))

vi.mock("../api", () => ({
  papersApi: { list: api.list },
  getErrorMessage: (error, fallback) => error?.message || fallback,
}))

import PapersView from "./PapersView.vue"

describe("PapersView", () => {
  beforeEach(() => {
    api.list.mockReset()
    api.list.mockResolvedValue({ data: { items: [], total: 0 } })
  })

  it("reloads papers when the conference route query changes", async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: "/papers", name: "papers", component: PapersView }],
    })
    await router.push({ name: "papers", query: { q: "vision" } })

    mount(PapersView, {
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
    expect(api.list).toHaveBeenLastCalledWith({ page: 1, page_size: 15, q: "vision" })

    await router.push({ name: "papers", query: { q: "vision", conference: "CVPR" } })
    await flushPromises()
    expect(api.list).toHaveBeenLastCalledWith({ page: 1, page_size: 15, q: "vision", conference: "CVPR" })

    await router.push({ name: "papers", query: { q: "vision" } })
    await flushPromises()
    expect(api.list).toHaveBeenLastCalledWith({ page: 1, page_size: 15, q: "vision" })
  })
})