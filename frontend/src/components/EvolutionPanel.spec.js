// @vitest-environment jsdom

import { flushPromises, mount } from "@vue/test-utils"
import { nextTick } from "vue"
import { beforeEach, describe, expect, it, vi } from "vitest"

const evolution = vi.hoisted(() => vi.fn())

vi.mock("../api", () => ({
  statsApi: { evolution },
  getErrorMessage: (error, fallback) => error?.message || fallback,
}))

import EvolutionPanel from "./EvolutionPanel.vue"

const topics = Array.from({ length: 12 }, (_, index) => ({
  keyword: `topic-${index + 1}`,
  papers: 12 - index,
  heat: 120 - index * 5,
}))

describe("EvolutionPanel", () => {
  beforeEach(() => evolution.mockReset())

  it("renders the current year and at most ten topics from the real payload", async () => {
    evolution.mockResolvedValue({
      data: {
        years: [2022, 2023],
        frames: [
          { year: 2022, topics },
          { year: 2023, topics: [{ keyword: "new-topic", papers: 3, heat: 30 }] },
        ],
      },
    })

    const wrapper = mount(EvolutionPanel)
    await flushPromises()

    expect(wrapper.get(".evolution-year").text()).toContain("2022")
    expect(wrapper.findAll(".evolution-row")).toHaveLength(10)
    expect(wrapper.text()).toContain("topic-1")
    expect(wrapper.findAll(".evolution-row").map((row) => row.find(".evolution-keyword").text())).not.toContain("topic-11")

    await wrapper.get("[aria-label='下一年']").trigger("click")
    expect(wrapper.get(".evolution-year").text()).toContain("2023")
  })

  it("shows a truthful empty state and a recoverable error", async () => {
    evolution.mockResolvedValue({ data: { years: [], frames: [] } })
    const emptyWrapper = mount(EvolutionPanel)
    await flushPromises()
    expect(emptyWrapper.text()).toContain("暂无年度热词数据")
    expect(emptyWrapper.text()).not.toMatch(/20\d{2}/)

    evolution.mockResolvedValue({
      get data() {
        throw new Error("evolution unavailable")
      },
    })
    const errorWrapper = mount(EvolutionPanel)
    await flushPromises()
    expect(errorWrapper.text()).toContain("evolution unavailable")
    expect(errorWrapper.text()).toContain("重试")
  })

  it("provides playback controls and advances one frame with fake timers", async () => {
    evolution.mockResolvedValue({
      data: {
        years: [2022, 2023],
        frames: [
          { year: 2022, topics: [{ keyword: "first", papers: 1, heat: 10 }] },
          { year: 2023, topics: [{ keyword: "second", papers: 2, heat: 20 }] },
        ],
      },
    })
    vi.useFakeTimers()
    const wrapper = mount(EvolutionPanel)
    await flushPromises()

    expect(wrapper.get("[aria-label='播放']").exists()).toBe(true)
    await wrapper.get("[aria-label='播放']").trigger("click")
    expect(wrapper.get("[aria-label='暂停']").exists()).toBe(true)
    vi.advanceTimersByTime(1200)
    await nextTick()
    expect(wrapper.get(".evolution-year").text()).toContain("2023")
    await wrapper.get("[aria-label='暂停']").trigger("click")
    vi.useRealTimers()
    wrapper.unmount()
  })
})
