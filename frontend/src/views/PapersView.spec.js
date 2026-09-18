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

  it("reloads and applies every route filter when the papers route is reused", async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: "/papers", name: "papers", component: PapersView }],
    })
    await router.push({ name: "papers", query: { q: "first" } })

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

    await router.push({ name: "papers", query: { q: "second", conference: "CVPR", year: "2023", year_from: "2021", year_to: "2024", keyword: "segmentation" } })
    await flushPromises()
    expect(api.list).toHaveBeenLastCalledWith({
      page: 1,
      page_size: 15,
      q: "second",
      conference: "CVPR",
      year: 2023,
      year_from: 2021,
      year_to: 2024,
      keyword: "segmentation",
    })
  })

  it("does not let an older response overwrite a newer query", async () => {
    let resolveFirst
    let resolveSecond
    api.list
      .mockImplementationOnce(() => new Promise((resolve) => { resolveFirst = resolve }))
      .mockImplementationOnce(() => new Promise((resolve) => { resolveSecond = resolve }))

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: "/papers", name: "papers", component: PapersView }],
    })
    await router.push({ name: "papers", query: { q: "first" } })

    const wrapper = mount(PapersView, {
      global: {
        plugins: [router],
        stubs: {
          AppShell: { template: "<div><slot /></div>" },
          PaperForm: true,
          PaperTable: { props: ["items"], template: "<div class='papers'>{{ items[0]?.title }}</div>" },
        },
      },
    })
    await flushPromises()

    await router.push({ name: "papers", query: { q: "second" } })
    await flushPromises()
    expect(api.list).toHaveBeenCalledTimes(2)

    resolveSecond({ data: { items: [{ title: "newer" }], total: 1 } })
    await flushPromises()
    resolveFirst({ data: { items: [{ title: "older" }], total: 1 } })
    await flushPromises()

    expect(wrapper.find(".papers").text()).toBe("newer")
  })
})


