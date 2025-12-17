/**
 * @file types.ts
 * @description TypeScript type definitions for manual-capture-cell
 */

export interface ManualCaptureCellData {
  category: string
  icon: string
  placeholder: string
}

export interface CellInstance {
  id: string
  notebook_item_type_id: string
  assignee_id: string
  initial_data: ManualCaptureCellData
  status: string
  fragments: unknown[]
}

export interface CellType {
  id: string
  name: string
  description: string
  version: string
  category: string
  can_render_dynamically: boolean
  default_refs: {
    view: string[]
    docs: string[]
    composables: string[]
  }
  default_initial_data: ManualCaptureCellData
  allow_instance_override_refs: boolean
  properties_schema: Record<string, unknown>
}

export interface CellProps {
  cell: {
    id: string
    cellId?: string
    type?: string
    initial_data?: ManualCaptureCellData
    state?: {
      cellInstance?: CellInstance
      cellType?: CellType
      initial_data?: ManualCaptureCellData
    }
  }
}
