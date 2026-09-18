// @vitest-environment jsdom

import { flushPromises, mount } from "@vue/test-utils"
import { beforeEach, describe, expect, it, vi } from "vitest"

const inspector = vi.hoisted(() => vi.fn())

vi.mock("../api", () => ({
  statsApi: { inspector },
  getErrorMessage: (error, fallback) => error?.message || fallback,
}))

import TopicInspectorDrawer from "./TopicInspectorDrawer.vue"

const payload = {
  keyword: "transformer",
  papers: 2,
  heat: 12.5,
  conference_breakdown: [{ conference: "CVPR", papers: 2 }],
  year_series: [{ year: 2024, papers: 2 }],
  related_keywords: [{ keyword: "attention", papers: 1, heat: 6.2 }],
  representative_papers: [{
    paper_id: 1,
    title: "A Transformer Paper",
    authors: "A. Researcher",
    conference: "CVPR",
    year: 2024,
    source: "OpenAlex",
    source_url: "https://example.com/paper",
  }],
}

describe("TopicInspectorDrawer", () => {
  beforeEach(() => inspector.mockReset())

  it("loads and renders inspector details, then emits close", async () => {
    inspector.mockResolvedValue({ data: payload })
    const wrapper = mount(TopicInspectorDrawer, { props: { keyword: "transformer", open: true } })

    await flushPromises()

    expect(inspector).toHaveBeenCalledWith("transformer")
    expect(wrapper.text()).toContain("了解更多")
    expect(wrapper.text()).toContain("A Transformer Paper")
    await wrapper.get("[aria-label='关闭主题详情']").trigger("click")
    expect(wrapper.emitted("close")).toHaveLength(1)
  })

  it("shows a recoverable error state", async () => {
    inspector.mockResolvedValue({
      get data() {
        throw new Error("inspector unavailable")
      },
    })
    const wrapper = mount(TopicInspectorDrawer, { props: { keyword: "unknown", open: true } })

    await flushPromises()

    expect(wrapper.text()).toContain("inspector unavailable")
    expect(wrapper.text()).toContain("重新加载")
  })
})
