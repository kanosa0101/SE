import * as echarts from "echarts/core"
import { GraphChart, LineChart } from "echarts/charts"
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components"
import { CanvasRenderer } from "echarts/renderers"

// 按需注册，避免全量引入 echarts 导致生产包体积告警。
echarts.use([GraphChart, LineChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

export * from "echarts/core"
