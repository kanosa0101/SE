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

  it("draws separate conference lines for one selected area and leaves missing years empty", async () => {
    vi.useFakeTimers()
    const wrapper = mount(TrendChart, {
      props: {
        keyword: "Vision-Language & Multimodal",
        payload: {
          years: [2023, 2024, 2025],
          series: [{
            keyword: "Vision-Language & Multimodal",
            data: [
              { conference: "CVPR", year: 2023, heat: 20 },
              { conference: "ICCV", year: 2023, heat: 30 },
              { conference: "CVPR", year: 2024, heat: 40 },
              { conference: "CVPR", year: 2025, heat: 50 },
              { conference: "ICCV", year: 2025, heat: 60 },
            ],
          }],
        },
      },
    })

    await wrapper.get("button").trigger("click")
    await vi.advanceTimersByTimeAsync(2400)

    const chart = chartApi.init.mock.results[0].value
    const option = chart.setOption.mock.calls.at(-1)[0]
    expect(option.series.map((series) => series.name)).toEqual(["CVPR", "ICCV", "ECCV"])
    expect(option.series.map((series) => series.lineStyle.type)).toEqual(["solid", "solid", "solid"])
    expect(option.series.find((series) => series.name === "CVPR").data).toEqual([20, 40, 50])
    expect(option.series.find((series) => series.name === "ICCV").data).toEqual([30, null, 60])
    expect(option.series.find((series) => series.name === "ECCV").data).toEqual([null, null, null])
    expect(option.series[0].connectNulls).toBe(true)
    wrapper.unmount()
    vi.useRealTimers()
  })

  it("shows all three conferences when the all-conferences option is selected", () => {
    const wrapper = mount(TrendChart, {
      props: {
        conference: "ALL",
        keyword: "Video Understanding",
        payload: {
          years: [2023, 2024],
          series: [{
            keyword: "Video Understanding",
            data: [
              { conference: "CVPR", year: 2023, heat: 12 },
              { conference: "ICCV", year: 2023, heat: 8 },
              { conference: "ECCV", year: 2024, heat: 10 },
            ],
          }],
        },
      },
    })

    const chart = chartApi.init.mock.results[0].value
    const option = chart.setOption.mock.calls[0][0]
    expect(option.series.map((series) => series.name)).toEqual(["CVPR", "ICCV", "ECCV"])
    expect(option.series.map((series) => series.data)).toEqual([[12], [8], [null]])
    wrapper.unmount()
  })
})
