// Types for the standalone DataGrid. This module is domain-agnostic and has no
// dependencies, so it can be reused in other apps.

export type CellValue = string | number | boolean | null | undefined;

export interface GridColumn {
  /** Stable column identifier. */
  id: string;
  /** Default header text (overridable with the `headerCell` snippet). */
  header?: string;
  /** Column width in pixels. */
  width?: number;
}
