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
      routes: ["/", "/trends", "/papers", "/import", "/about"].map((path) => ({ path, name: path === "/papers" ? "papers" : undefined, component: view })),
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

  it("preserves route filters when global search updates q", async () => {
    const router = createTestRouter()
    await router.push({ path: "/papers", query: { conference: "CVPR", year: "2024", keyword: "transformer" } })

    const wrapper = mount(AppShell, {
      global: { plugins: [router] },
      slots: { default: "<div />" },
    })

    const input = wrapper.get("input[aria-label='Search papers']")
    await input.setValue("vision")
    await input.trigger("keyup.enter")
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(router.currentRoute.value.path).toBe("/papers")
    expect(router.currentRoute.value.query).toEqual({
      conference: "CVPR",
      year: "2024",
      keyword: "transformer",
      q: "vision",
    })
  })

  it("connects the drawer button to one stable sidebar", () => {
    const router = createTestRouter()
    const wrapper = mount(AppShell, {
      global: { plugins: [router] },
      slots: { default: "<div />" },
    })

    const toggle = wrapper.get(".drawer-toggle")
    const sidebar = wrapper.get("aside.sidebar")
    expect(toggle.attributes("aria-controls")).toBe(sidebar.attributes("id"))
    expect(toggle.attributes("aria-expanded")).toBe("false")
    expect(wrapper.findAll(".drawer-toggle")).toHaveLength(1)
  })
})
