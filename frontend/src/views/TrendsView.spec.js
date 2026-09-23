// @vitest-environment jsdom

import { flushPromises, mount } from "@vue/test-utils"
import { createMemoryHistory, createRouter } from "vue-router"
import { beforeEach, describe, expect, it, vi } from "vitest"

const api = vi.hoisted(() => ({ trends: vi.fn() }))

vi.mock("../api", () => ({
  statsApi: api,
  getErrorMessage: (error, fallback) => error?.message || fallback,
}))

import TrendsView from "./TrendsView.vue"

describe("TrendsView", () => {
  beforeEach(() => {
    api.trends.mockReset()
    api.trends.mockResolvedValue({ data: { years: [], series: [] } })
  })

  it("uses the global conference query and reloads when it changes", async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: "/trends", name: "trends", component: TrendsView }],
    })
    await router.push({ name: "trends", query: { conference: "CVPR" } })

    mount(TrendsView, {
      global: {
        plugins: [router],
        stubs: {
          AppShell: { template: "<div><slot /></div>" },
          TrendChart: true,
        },
      },
    })
    await flushPromises()
    expect(api.trends).toHaveBeenLastCalledWith({ conference: "CVPR" })

    await router.push({ name: "trends", query: {} })
    await flushPromises()
    expect(api.trends).toHaveBeenLastCalledWith({})
  })

  it("offers returned research directions for animated comparison", async () => {
    api.trends.mockResolvedValue({
      data: {
        years: [2023, 2024],
        series: [
          { keyword: "Video Understanding", data: [{ conference: "CVPR", year: 2023, heat: 20 }] },
          { keyword: "Segmentation", data: [{ conference: "ICCV", year: 2023, heat: 30 }] },
        ],
      },
    })
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: "/trends", name: "trends", component: TrendsView }],
    })
    await router.push({ name: "trends" })

    const wrapper = mount(TrendsView, {
      global: {
        plugins: [router],
        stubs: {
          AppShell: { template: "<div><slot /></div>" },
          EvolutionPanel: true,
          TrendChart: true,
        },
      },
    })
    await flushPromises()

    const directionSelect = wrapper.get("select[aria-label='研究方向']")
    expect(directionSelect.findAll("option").map((option) => option.text())).toEqual([
      "Video Understanding",
      "Segmentation",
    ])
    expect(directionSelect.element.value).toBe("Video Understanding")

    await directionSelect.setValue("Segmentation")
    expect(directionSelect.element.value).toBe("Segmentation")
  })
})
