import { describe, expect, it } from "vitest"

import { formatHeat } from "./filters"

describe("formatHeat", () => {
  it("formats normalized heat with one decimal place", () => {
    expect(formatHeat(12.345)).toBe("12.3%")
  })
})
