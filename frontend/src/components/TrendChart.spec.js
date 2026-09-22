// @vitest-environment jsdom

import { mount } from "@vue/test-utils"
import { beforeEach, describe, expect, it, vi } from "vitest"

const chartApi = vi.hoisted(() => ({ init: vi.fn() }))

vi.mock("../utils/echarts", () => ({ init: chartApi.init }))

import TrendChart from "./TrendChart.vue"

describe("TrendChart", () => {
  beforeEach(() => {
    chartApi.init.mockReset()
    chartApi.init.mockReturnValue({ setOption: vi.fn(), dispose: vi.fn() })
  })

  it("keeps the vertical axis title away from the legend", () => {
    const wrapper = mount(TrendChart, {
      props: {
        payload: {
          years: [2023],
          series: [{ keyword: "Video Understanding", data: [{ year: 2023, heat: 12 }] }],
        },
      },
    })

    const chart = chartApi.init.mock.results[0].value
    const option = chart.setOption.mock.calls[0][0]

    expect(option.grid.top).toBeGreaterThanOrEqual(56)
    expect(option.yAxis.nameLocation).toBe("middle")
    expect(option.yAxis.nameGap).toBeGreaterThanOrEqual(32)
    expect(option.legend.left).toBeGreaterThan(0)

    wrapper.unmount()
  })
})
