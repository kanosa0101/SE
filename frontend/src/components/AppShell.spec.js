// @vitest-environment jsdom

import { mount } from "@vue/test-utils"
import { createMemoryHistory, createRouter } from "vue-router"
import { describe, expect, it } from "vitest"

import AppShell from "./AppShell.vue"

describe("AppShell", () => {
  function createTestRouter() {
    const view = { template: "<div />" }
    return createRouter({
      history: createMemoryHistory(),
      routes: ["/", "/trends", "/papers", "/import", "/about"].map((path) => ({ path, component: view })),
    })
  }

  it("renders the observatory shell contract", async () => {
    const router = createTestRouter()
    await router.push("/")

    const wrapper = mount(AppShell, {
      global: { plugins: [router] },
      slots: { default: "<div>Telemetry payload</div>" },
    })

    expect(wrapper.find(".topbar").exists()).toBe(true)
    expect(wrapper.find(".sidebar").exists()).toBe(true)
    expect(wrapper.text()).toContain("CVINSIGHT")
    expect(wrapper.text()).toContain("Navigation Matrix")
    expect(wrapper.findAll(".conference-chip")).toHaveLength(4)
    expect(wrapper.find(".telemetry-count").text()).toContain("—")
    expect(wrapper.text()).not.toContain("12,486")
    expect(wrapper.findAll(".drawer-toggle")).toHaveLength(1)
    expect(wrapper.findAll(".mobile-menu")).toHaveLength(0)
    expect(wrapper.find(".conference-chip:nth-child(1)").classes()).toContain("chip-cyan")
    expect(wrapper.find(".conference-chip:nth-child(2)").classes()).toContain("chip-cyan")
    expect(wrapper.find(".conference-chip:nth-child(3)").classes()).toContain("chip-amber")
    expect(wrapper.find(".conference-chip:nth-child(4)").classes()).toContain("chip-green")
  })

  it("syncs conference chips to the router query and clears All", async () => {
    const router = createTestRouter()
    await router.push({ path: "/papers", query: { q: "vision" } })

    const wrapper = mount(AppShell, {
      global: { plugins: [router] },
      slots: { default: "<div />" },
    })

    await wrapper.findAll(".conference-chip")[1].trigger("click")
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(router.currentRoute.value.query).toEqual({ q: "vision", conference: "CVPR" })

    await wrapper.findAll(".conference-chip")[0].trigger("click")
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(router.currentRoute.value.query).toEqual({ q: "vision" })
  })
})
