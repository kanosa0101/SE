// @vitest-environment jsdom

import { flushPromises, mount } from "@vue/test-utils"
import { beforeEach, describe, expect, it, vi } from "vitest"

const chart = vi.hoisted(() => ({
  setOption: vi.fn(),
  on: vi.fn(),
  resize: vi.fn(),
  dispose: vi.fn(),
}))
const echarts = vi.hoisted(() => ({ init: vi.fn(() => chart) }))

vi.mock("../utils/echarts", () => echarts)

import KeywordGraph from "./KeywordGraph.vue"

describe("KeywordGraph", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    globalThis.ResizeObserver = class {
      observe() {}
      disconnect() {}
    }
  })

  it("configures adjacency emphasis so hovered edges are highlighted", async () => {
    const wrapper = mount(KeywordGraph, {
      props: {
        graph: {
          nodes: [{ name: "video", value: 20 }, { name: "tracking", value: 10 }],
          links: [{ source: "video", target: "tracking", value: 40 }],
        },
      },
    })

    await flushPromises()

    const option = chart.setOption.mock.calls.at(-1)[0]
    expect(option.series[0].emphasis).toMatchObject({
      focus: "adjacency",
      lineStyle: { opacity: 1 },
    })
    expect(option.series[0].emphasis.lineStyle.width).toBeGreaterThan(1)
    wrapper.unmount()
  })

  it("advertises the lower default relationship threshold", async () => {
    const wrapper = mount(KeywordGraph)

    await flushPromises()

    expect(wrapper.text()).toContain("共现 ≥ 30 篇")
    wrapper.unmount()
  })
})
