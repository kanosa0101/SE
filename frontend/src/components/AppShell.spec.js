// @vitest-environment jsdom

import { mount } from "@vue/test-utils"
import { createMemoryHistory, createRouter } from "vue-router"
import { describe, expect, it } from "vitest"

import AppShell from "./AppShell.vue"

describe("AppShell", () => {
  it("renders the observatory shell contract", () => {
    const view = { template: "<div />" }
    const router = createRouter({
      history: createMemoryHistory(),
      routes: ["/", "/trends", "/papers", "/import", "/about"].map((path) => ({ path, component: view })),
    })

    const wrapper = mount(AppShell, {
      global: { plugins: [router] },
      slots: { default: "<div>Telemetry payload</div>" },
    })

    expect(wrapper.find(".topbar").exists()).toBe(true)
    expect(wrapper.find(".sidebar").exists()).toBe(true)
    expect(wrapper.text()).toContain("CVINSIGHT")
    expect(wrapper.text()).toContain("Navigation Matrix")
    expect(wrapper.findAll(".conference-chip")).toHaveLength(4)
  })
})
