// @vitest-environment jsdom

import { mount } from "@vue/test-utils"
import { describe, expect, it } from "vitest"

import PaperTable from "./PaperTable.vue"

describe("PaperTable provenance", () => {
  it("shows crawl and parser metadata only when supplied", () => {
    const wrapper = mount(PaperTable, {
      props: {
        items: [{
          id: 11,
          title: "CVF Provenance Paper",
          authors: "Researcher",
          conference: "ICCV",
          year: 2025,
          keywords: ["vision"],
          source: "cvf",
          crawled_at: "2026-09-18T12:34:56Z",
          parser_version: "cvf-v2",
        }],
      },
    })

    expect(wrapper.text()).toContain("cvf")
    expect(wrapper.text()).toContain("抓取 2026-09-18 12:34:56")
    expect(wrapper.text()).toContain("解析 cvf-v2")
  })
})
