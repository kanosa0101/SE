// @vitest-environment jsdom

import { flushPromises, mount } from "@vue/test-utils"
import { beforeEach, describe, expect, it, vi } from "vitest"

const quality = vi.hoisted(() => vi.fn())

vi.mock("../api", () => ({
  statsApi: { quality },
  getErrorMessage: (error, fallback) => error?.message || fallback,
}))

import DataQualityCard from "./DataQualityCard.vue"

describe("DataQualityCard", () => {
  beforeEach(() => quality.mockReset())

  it("renders the real audit summary, source breakdown and coverage matrix", async () => {
    quality.mockResolvedValue({
      data: {
        total: 42,
        keyword_coverage: 92.9,
        missing_fields: { abstract: 2, authors: 1, source_url: 4 },
        source_breakdown: [{ source: "cvf", papers: 30 }, { source: "csv", papers: 12 }],
        conference_year_matrix: [{ conference: "CVPR", year: 2024, papers: 24 }],
      },
    })

    const wrapper = mount(DataQualityCard)
    await flushPromises()

    expect(wrapper.text()).toContain("42")
    expect(wrapper.text()).toContain("92.9%")
    expect(wrapper.text()).toContain("cvf")
    expect(wrapper.text()).toContain("CVPR")
    expect(wrapper.text()).toContain("24")
  })

  it("shows an honest empty state for an empty database", async () => {
    quality.mockResolvedValue({
      data: {
        total: 0,
        keyword_coverage: 0,
        missing_fields: { abstract: 0, authors: 0, source_url: 0 },
        source_breakdown: [],
        conference_year_matrix: [],
      },
    })

    const wrapper = mount(DataQualityCard)
    await flushPromises()

    expect(wrapper.text()).toContain("暂无可审计的论文数据")
  })

  it("shows a recoverable error and retries", async () => {
    quality.mockResolvedValue({
      get data() {
        throw new Error("quality unavailable")
      },
    })

    const wrapper = mount(DataQualityCard)
    await flushPromises()
    expect(wrapper.text()).toContain("quality unavailable")
    expect(wrapper.text()).toContain("重试")

    quality.mockResolvedValue({
      data: {
        total: 1,
        keyword_coverage: 100,
        missing_fields: { abstract: 0, authors: 0, source_url: 0 },
        source_breakdown: [{ source: "cvf", papers: 1 }],
        conference_year_matrix: [{ conference: "ECCV", year: 2024, papers: 1 }],
      },
    })
    await wrapper.get(".retry").trigger("click")
    await flushPromises()
    expect(wrapper.text()).toContain("ECCV")
  })
})
