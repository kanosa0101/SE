import { describe, expect, it } from "vitest"

import { edgeVisual, EDGE_MIN_WIDTH, EDGE_MAX_WIDTH, EDGE_MIN_OPACITY, EDGE_MAX_OPACITY, STRONG_EDGE_THRESHOLD } from "./graph"

describe("edgeVisual", () => {
  it("maps the maximum value to the strongest style", () => {
    expect(edgeVisual(447, 447)).toEqual({ width: EDGE_MAX_WIDTH, opacity: EDGE_MAX_OPACITY })
  })

  it("maps weaker values to fainter styles", () => {
    const weak = edgeVisual(1, 447)
    const strong = edgeVisual(447, 447)
    expect(weak.width).toBeLessThan(strong.width)
    expect(weak.opacity).toBeLessThan(strong.opacity)
    expect(weak.width).toBeLessThan(1.5)
  })

  it("compresses long-tailed values with a square-root scale", () => {
    const mid = edgeVisual(112, 447)
    expect(mid.width).toBeGreaterThan(EDGE_MIN_WIDTH + 1)
    expect(mid.width).toBeLessThan(EDGE_MAX_WIDTH - 1)
  })

  it("falls back to the faintest style for invalid input", () => {
    expect(edgeVisual(undefined, 100)).toEqual({ width: EDGE_MIN_WIDTH, opacity: EDGE_MIN_OPACITY })
    expect(edgeVisual(10, 0)).toEqual({ width: EDGE_MIN_WIDTH, opacity: EDGE_MIN_OPACITY })
  })

  it("keeps the strong-relation threshold inside the top quarter of values", () => {
    expect(STRONG_EDGE_THRESHOLD).toBeGreaterThan(0)
  })
})
