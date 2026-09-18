// @vitest-environment jsdom

import { flushPromises, mount } from "@vue/test-utils"
import { createMemoryHistory, createRouter } from "vue-router"
import { beforeEach, describe, expect, it, vi } from "vitest"

const api = vi.hoisted(() => ({ overview: vi.fn(), topics: vi.fn(), graph: vi.fn(), inspector: vi.fn() }))

vi.mock("../api", () => ({
  statsApi: api,
  getErrorMessage: (error, fallback) => error?.message || fallback,
}))

import OverviewView from "./OverviewView.vue"

describe("OverviewView", () => {
  beforeEach(() => {
    api.overview.mockReset()
    api.topics.mockReset()
    api.graph.mockReset()
    api.inspector.mockReset()
    api.overview.mockResolvedValue({ data: { total_papers: 1, conference_count: 1, year_from: 2020, year_to: 2024 } })
    api.topics.mockResolvedValue({ data: [] })
    api.graph.mockResolvedValue({ data: { nodes: [], links: [] } })
  })

  it("uses and reloads the conference from the route query", async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: "/", name: "overview", component: OverviewView }],
    })
    await router.push({ name: "overview", query: { conference: "CVPR" } })

    mount(OverviewView, {
      global: {
        plugins: [router],
        stubs: {
          AppShell: { template: "<div><slot /></div>" },
          KeywordGraph: true,
          MetricCard: true,
        },
      },
    })
    await flushPromises()
    expect(api.overview).toHaveBeenLastCalledWith({ conference: "CVPR" })
    expect(api.topics).toHaveBeenLastCalledWith({ conference: "CVPR" })

    await router.push({ name: "overview", query: {} })
    await flushPromises()
    expect(api.overview).toHaveBeenLastCalledWith({})
    expect(api.topics).toHaveBeenLastCalledWith({})
  })

  it("opens the topic inspector when a topic row is selected", async () => {
    api.topics.mockResolvedValue({ data: [{ keyword: "transformer", papers: 2, heat: 10 }] })
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: "/", name: "overview", component: OverviewView }],
    })
    await router.push({ name: "overview" })

    const wrapper = mount(OverviewView, {
      global: {
        plugins: [router],
        stubs: {
          AppShell: { template: "<div><slot /></div>" },
          KeywordGraph: true,
          MetricCard: true,
          TopicInspectorDrawer: {
            props: ["keyword", "open"],
            template: "<aside v-if=\"open\" data-testid=\"topic-inspector\">{{ keyword }}</aside>",
          },
        },
      },
    })
    await flushPromises()

    await wrapper.get(".topic-row").trigger("click")
    expect(wrapper.get("[data-testid='topic-inspector']").text()).toBe("transformer")
  })
})
