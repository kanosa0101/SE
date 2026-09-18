// @vitest-environment jsdom

import { mount } from "@vue/test-utils"
import { describe, expect, it } from "vitest"

import PaperTable from "./PaperTable.vue"


describe("PaperTable", () => {
  it("renders a paper and emits the selected record", async () => {
    const paper = {
      id: 7,
      title: "A Reproducible Vision Study",
      authors: "A. Researcher",
      conference: "CVPR",
      year: 2024,
      keywords: ["transformer", "segmentation"],
      source: "fixture",
    }
    const wrapper = mount(PaperTable, { props: { items: [paper] } })

    expect(wrapper.text()).toContain(paper.title)
    await wrapper.get(".title-button").trigger("click")

    expect(wrapper.emitted("detail")).toEqual([[paper]])
  })
})
