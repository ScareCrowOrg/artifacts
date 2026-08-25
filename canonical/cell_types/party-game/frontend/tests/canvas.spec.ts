/**
 * @file canvas.spec.ts
 * @description Unit tests for canvas.ts — pure drawing utilities (Buffer Local).
 */

import { describe, it, expect, vi } from 'vitest'
import {
  clearCanvas,
  commitStroke,
  createStroke,
  eventToCanvasPoint,
  extendStroke,
  renderStroke,
  renderStrokes,
} from '../canvas'
import type { Stroke } from '../gameStore'

/** Minimal fake CanvasRenderingContext2D recording what it draws. */
function makeCtx(): any {
  return {
    save: vi.fn(),
    restore: vi.fn(),
    setTransform: vi.fn(),
    clearRect: vi.fn(),
    beginPath: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    stroke: vi.fn(),
    lineCap: '',
    lineJoin: '',
    strokeStyle: '',
    lineWidth: 0,
    globalCompositeOperation: 'source-over',
  }
}

describe('createStroke', () => {
  it('builds a local stroke with style and the first point', () => {
    const s = createStroke('pen', '#000000', 4, { x: 1, y: 2 })
    expect(s).toMatchObject({ tool: 'pen', color: '#000000', width: 4 })
    expect(s.points).toEqual([{ x: 1, y: 2 }])
    expect(s.id).toBeUndefined()
  })
})

describe('extendStroke', () => {
  it('appends the point and draws a segment (Buffer Local — no store write)', () => {
    const ctx = makeCtx()
    const s = createStroke('pen', '#f00', 2, { x: 0, y: 0 })
    extendStroke(ctx, s, { x: 5, y: 5 })
    expect(s.points).toHaveLength(2)
    expect(ctx.lineTo).toHaveBeenCalledWith(5, 5)
    expect(ctx.stroke).toHaveBeenCalled()
    expect(ctx.lineCap).toBe('round')
  })

  it('uses destination-out when extending an eraser stroke', () => {
    const ctx = makeCtx()
    const s = createStroke('eraser', '#000', 8, { x: 0, y: 0 })
    extendStroke(ctx, s, { x: 3, y: 3 })
    expect(ctx.globalCompositeOperation).toBe('destination-out')
  })
})

describe('commitStroke', () => {
  it('assigns an id and returns a copy', () => {
    const s = createStroke('pen', '#000', 2, { x: 0, y: 0 })
    const committed = commitStroke(s)
    expect(committed.id).toBeDefined()
    expect(committed).not.toBe(s)
    expect(committed.points).not.toBe(s.points)
  })

  it('keeps an existing id', () => {
    const s = { tool: 'pen', color: '#000', width: 2, points: [{ x: 0, y: 0 }], id: 'abc' } as Stroke
    expect(commitStroke(s).id).toBe('abc')
  })
})

describe('renderStrokes / renderStroke / clearCanvas', () => {
  it('renders every committed stroke after clearing', () => {
    const ctx = makeCtx()
    const strokes = [
      { tool: 'pen', color: '#000', width: 2, points: [{ x: 0, y: 0 }, { x: 1, y: 1 }] },
      { tool: 'pen', color: '#f00', width: 4, points: [{ x: 2, y: 2 }] },
    ] as Stroke[]
    renderStrokes(ctx, strokes, 800, 500)
    expect(ctx.clearRect).toHaveBeenCalledWith(0, 0, 800, 500)
    expect(ctx.stroke).toHaveBeenCalledTimes(2)
  })

  it('uses destination-out for eraser strokes', () => {
    const ctx = makeCtx()
    const eraser = { tool: 'eraser', color: '#000', width: 8, points: [{ x: 0, y: 0 }] } as Stroke
    renderStroke(ctx, eraser)
    expect(ctx.globalCompositeOperation).toBe('destination-out')
  })

  it('does nothing for an empty stroke', () => {
    const ctx = makeCtx()
    renderStroke(ctx, { tool: 'pen', color: '#000', width: 2, points: [] } as Stroke)
    expect(ctx.stroke).not.toHaveBeenCalled()
  })

  it('clearCanvas clears the full rect', () => {
    const ctx = makeCtx()
    clearCanvas(ctx, 400, 300)
    expect(ctx.clearRect).toHaveBeenCalledWith(0, 0, 400, 300)
    expect(ctx.restore).toHaveBeenCalled()
  })
})

describe('eventToCanvasPoint', () => {
  it('maps client coordinates to canvas coordinates accounting for scaling', () => {
    const canvas = {
      width: 800,
      height: 500,
      getBoundingClientRect: () => ({ left: 10, top: 20, width: 400, height: 250 }),
    } as unknown as HTMLCanvasElement
    expect(eventToCanvasPoint(canvas, { clientX: 210, clientY: 270 })).toEqual({ x: 400, y: 500 })
  })
})
