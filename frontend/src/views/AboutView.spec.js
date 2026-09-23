// @vitest-environment jsdom

import { mount } from "@vue/test-utils"
import { describe, expect, it } from "vitest"

import AboutView from "./AboutView.vue"

describe("AboutView", () => {
  it("introduces all three conferences and reports the current graph snapshot", () => {
    const wrapper = mount(AboutView, {
      global: {
        stubs: {
          AppShell: { template: "<div><slot /></div>" },
          DataQualityCard: true,
        },
      },
    })

    expect(wrapper.text()).toContain("三大顶会")
    expect(wrapper.get("a[href='https://cvpr.thecvf.com/']").text()).toContain("官网")
    expect(wrapper.get("a[href='https://iccv.thecvf.com/']").text()).toContain("官网")
    expect(wrapper.get("a[href='https://eccv.ecva.net/']").text()).toContain("官网")
    expect(wrapper.text()).toContain("32 个关键词节点")
    expect(wrapper.text()).toContain("455 条共现关系")
    expect(wrapper.text()).toContain("30 篇")
    expect(wrapper.text()).not.toContain("前 50 的关键词")
    expect(wrapper.text()).not.toContain("≥ 75")
    expect(wrapper.text()).not.toContain("1222 条边")
  })
})
