// @vitest-environment jsdom

import { mount } from "@vue/test-utils"
import { describe, expect, it } from "vitest"

import TelemetryBar from "./TelemetryBar.vue"

describe("TelemetryBar", () => {
  it("shows a neutral value when no verified record count is supplied", () => {
    const wrapper = mount(TelemetryBar, { props: { count: null } })

    expect(wrapper.find(".telemetry-count").text()).toContain("—")
    expect(wrapper.find(".telemetry-count").text()).not.toContain("12,486")
  })

  it("renders a supplied record count", () => {
    const wrapper = mount(TelemetryBar, { props: { count: 42 } })

    expect(wrapper.find(".telemetry-count").text()).toContain("42")
  })
})
