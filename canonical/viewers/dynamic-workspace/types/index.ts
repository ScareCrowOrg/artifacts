/**
 * types/index.ts
 *
 * Shared type definitions for DynamicWorkspace v2 viewer.
 * Used across composables, components, and App.vue.
 */

import type { Component } from 'vue'

// ── CellTypeDefinition ──────────────────────────────────────────────────────

/**
 * A cell type as loaded from HybridDatabase (canonical type.json).
 * Uses semantic `id` (e.g. "planet-chat-cell") as the primary identifier for dynamic imports.
 * The `name` field is human-readable display name (may contain spaces).
 */
export interface CellTypeDefinition {
  /** Semantic identifier (kebab-case) — used for dynamic imports and artifact paths */
  id: string
  /** Human-readable display name (may contain spaces) */
  name: string
  /** Human-readable description */
  description: string
  /** Semantic version */
  version: string
  /** Category for grouping in AddCellModal */
  category?: string
  /** Emoji or URL icon */
  icon?: string
  /** Whether this cell type can be loaded dynamically in a browser */
  can_render_dynamically?: boolean
  /** File refs from type.json (e.g. view, basecell) */
  default_refs?: {
    view?: string[]
    basecell?: string[]
    [key: string]: string[] | undefined
  }
  /** JSON Schema for cell inputs (used by GeneratedFormView) */
  properties_schema?: Record<string, any>
}

// ── ViewSpec ────────────────────────────────────────────────────────────────

/**
 * The result of resolveViewSpec().
 * Returned by useCellViewProvider after calling cellInstance.show().
 * The parent grid is agnostic — it only needs component + props.
 */
export interface ViewSpec {
  /** Vue component to render (custom View.vue or GeneratedFormView) */
  component: Component
  /** Props to pass to the component */
  props: Record<string, any>
}

// ── GridCell ────────────────────────────────────────────────────────────────

/**
 * A cell instance tracked in the grid.
 * useGridLayout manages a reactive list of GridCell objects.
 */
export interface GridCell {
  /** UUID — unique per instance, used for keying in v-for */
  cellId: string
  /** Semantic type name — used for loading, never UUID */
  cellTypeName: string
  /** BaseCell instance (or null while loading) */
  cellInstance: any | null
  /** ViewSpec returned by resolveViewSpec — null while loading */
  viewSpec: ViewSpec | null
  /** Loading flag (true between add and viewSpec resolution) */
  isLoading: boolean
  /** Error message if loading failed */
  error: string | null
  /** Whether this cell is minimized */
  isMinimized: boolean
  /** Whether this cell is maximized */
  isMaximized: boolean
  /** Grid position for GridContainer */
  position: GridPosition
  /** Cell type definition (for title, icon, etc.) */
  cellType: CellTypeDefinition | null
}

// ── GridPosition ────────────────────────────────────────────────────────────

/** Grid position/size for a cell in the layout */
export interface GridPosition {
  /** Column (0-based) */
  x: number
  /** Row (0-based) */
  y: number
  /** Width in columns */
  w: number
  /** Height in rows */
  h: number
}

// ── LayoutBook ──────────────────────────────────────────────────────────────

/** A saved workspace layout (used by LayoutBookSelector component) */
export interface LayoutBook {
  id: string
  name: string
  description?: string
  cells: SavedCell[]
  createdAt?: string
  updatedAt?: string
}

/** Serialized cell data inside a LayoutBook */
export interface SavedCell {
  cellTypeName: string
  position: GridPosition
}

// ── API Models for Layout Books endpoints ──────────────────────────────────

/** Grid configuration stored with a layout book */
export interface GridConfig {
  cols: number
  rowHeight: number
  margin: [number, number]
}

/** Serialized cell reference stored inside a Book's initial_data */
export interface CellReference {
  cellId?: string
  category: 'persistent' | 'ephemeral'
  type: string
  title: string
  position: GridPosition
  state: {
    isMinimized: boolean
    isMaximized: boolean
  }
  initialization_data?: Record<string, any>
}

/** Metadata tracked for a layout book */
export interface LayoutBookMetadata {
  layout_version: string
  created_from_layout?: string
  last_applied?: string
}

/** Full Book response object from the backend */
export interface Book {
  id: string
  assignee_id: string
  notebook_item_type_id: string
  name: string
  description: string
  type: string
  initial_data: {
    layout_version: string
    cells: CellReference[]
    grid_config: GridConfig
    metadata: LayoutBookMetadata
  }
  created_at: string
  updated_at: string
}

/** A single item in the layout book list */
export interface LayoutBookListItem {
  id: string
  name: string
  description: string
  cell_count: number
  created_at: string
  updated_at: string
}

/** Paginated response from GET /api/layout-books */
export interface LayoutBookListResponse {
  items: LayoutBookListItem[]
  total: number
  skip: number
  limit: number
}
