/**
 * @file canvas.ts
 * @description Pure drawing utilities for the party-game canvas.
 *
 * Follows the **Buffer Local Pattern** (REACTIVITY_ISOLATION.md): the stroke
 * being drawn lives in a local `Stroke` object (never in the store) and is
 * committed to the distributed `strokes` branch ONLY on `pointerup`
 * (`commitStroke` → backend `append_stroke`).
 *
 * All functions are pure / take an explicit `CanvasRenderingContext2D`, so they
 * are unit-testable without a DOM.
 */

import type { Point2D, Stroke } from './gameStore'

// ── Stroke lifecycle (Buffer Local) ────────────────────────────────────────

/**
 * Begin a new local stroke at *point* with the given style.
 * The returned stroke is kept in a local ref by the caller and extended on
 * pointermove; it is NOT published until `commitStroke`.
 */
export function createStroke(tool: Stroke['tool'], color: string, width: number, point: Point2D): Stroke {
  return { tool, color, width, points: [{ x: point.x, y: point.y }] }
}

/**
 * Extend *stroke* to *point* and draw the new segment on *ctx*.
 * Mutates the local stroke (Buffer Local) — no store writes here.
 */
export function extendStroke(ctx: CanvasRenderingContext2D, stroke: Stroke, point: Point2D): void {
  const last = stroke.points[stroke.points.length - 1]
  stroke.points.push({ x: point.x, y: point.y })
  drawSegment(ctx, stroke, last, stroke.points[stroke.points.length - 1])
}

/**
 * Finalize a stroke for publishing.  Assigns an id and returns the value that
 * should be appended to the distributed `strokes` branch (via the backend).
 */
export function commitStroke(stroke: Stroke): Stroke {
  if (!stroke.id) {
    stroke.id = `stroke-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
  }
  return { ...stroke, points: stroke.points.map((p) => ({ ...p })) }
}

// ── Rendering ───────────────────────────────────────────────────────────────

/** Clear the full canvas. */
export function clearCanvas(ctx: CanvasRenderingContext2D, width: number, height: number): void {
  ctx.save()
  ctx.setTransform(1, 0, 0, 1, 0, 0)
  ctx.clearRect(0, 0, width, height)
  ctx.restore()
}

/** Render the committed stroke list (drawer and guessers both use this). */
export function renderStrokes(
  ctx: CanvasRenderingContext2D,
  strokes: Stroke[],
  width: number,
  height: number,
): void {
  clearCanvas(ctx, width, height)
  for (const stroke of strokes) {
    renderStroke(ctx, stroke)
  }
}

/** Render a single stroke (polyline). */
export function renderStroke(ctx: CanvasRenderingContext2D, stroke: Stroke): void {
  const pts = stroke.points
  if (pts.length === 0) return
  ctx.save()
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  ctx.strokeStyle = stroke.color
  ctx.lineWidth = stroke.width
  if (stroke.tool === 'eraser') {
    ctx.globalCompositeOperation = 'destination-out'
  }
  ctx.beginPath()
  ctx.moveTo(pts[0].x, pts[0].y)
  for (let i = 1; i < pts.length; i += 1) {
    ctx.lineTo(pts[i].x, pts[i].y)
  }
  ctx.stroke()
  ctx.restore()
}

// ── Coordinate helpers ──────────────────────────────────────────────────────

/** Convert a pointer event to canvas coordinates (accounting for scaling). */
export function eventToCanvasPoint(
  canvas: HTMLCanvasElement,
  event: { clientX: number; clientY: number },
): Point2D {
  const rect = canvas.getBoundingClientRect()
  const scaleX = canvas.width / Math.max(1, rect.width)
  const scaleY = canvas.height / Math.max(1, rect.height)
  return {
    x: (event.clientX - rect.left) * scaleX,
    y: (event.clientY - rect.top) * scaleY,
  }
}

// ── Internal ────────────────────────────────────────────────────────────────

function drawSegment(ctx: CanvasRenderingContext2D, stroke: Stroke, from: Point2D, to: Point2D): void {
  ctx.save()
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  ctx.strokeStyle = stroke.color
  ctx.lineWidth = stroke.width
  if (stroke.tool === 'eraser') {
    ctx.globalCompositeOperation = 'destination-out'
  }
  ctx.beginPath()
  ctx.moveTo(from.x, from.y)
  ctx.lineTo(to.x, to.y)
  ctx.stroke()
  ctx.restore()
}
