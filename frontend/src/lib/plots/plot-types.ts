// Domain-agnostic types for the standalone plotting library.
//
// This module knows nothing about chemometrics, ScorePilot, scores, loadings,
// observations or variables. A plot is fed a list of `PlotPoint`s, each carrying
// opaque identities for row-wise and/or column-wise linking. Callers map their
// own domain ids (an observation name, a variable name, ...) onto `rowId` /
// `colId` and react to selection through a `LinkGroup`. Copy the `plots/` folder
// into another app and it works unchanged.

/** Marker shape for a point. Only `circle`/`square` are wired today; the rest are
 * reserved for the forthcoming shape-encoding channel. */
export type PlotSymbol = 'circle' | 'square' | 'triangle' | 'diamond';

/** A single mark (a scatter point, a bar, a line vertex).
 *
 * Identity is carried on two independent dimensions so a selection can link by
 * row, by column, or by both:
 * - `rowId` links "observations" (e.g. a sample): brushing a score point selects
 *   that row everywhere.
 * - `colId` links "variables" (e.g. a measurement): brushing a loadings point
 *   selects that column everywhere.
 * A mark may set either, both, or neither (neither = not linkable). */
export interface PlotPoint {
  /** Stable id for row-wise linking. */
  rowId?: string;
  /** Stable id for column-wise linking. */
  colId?: string;
  /** X position. A category label for bar/line plots, a number for scatters. */
  x: number | string;
  /** Y position. */
  y: number;
  /** Text drawn beside the mark (e.g. an identifier). */
  label?: string;
  // --- Forward-looking encoding channels: declared now, wired later. ---
  /** Per-point colour (coming). */
  color?: string;
  /** Per-point marker size (coming). */
  size?: number;
  /** Per-point marker shape (coming). */
  shape?: PlotSymbol;
}

/** Which identity dimension a plot links/selects on. */
export type LinkDim = 'row' | 'col' | 'both';

/** An option in an axis drop-down. The `value` is opaque to the library; the
 * caller maps it back to whatever it means (a component index, "seq", ...). */
export interface AxisOption {
  value: string;
  label: string;
}

/** Axis drop-down wiring. When supplied to a plot, the plot renders the selectors
 * and calls `onchange`; the caller re-projects its points in response. */
export interface AxisControl {
  options: AxisOption[];
  x: string;
  y: string;
  onchange: (x: string, y: string) => void;
}

/** A straight or poly-line drawn over a scatter (origin guides, a confidence
 * ellipse, a trend line). Purely decorative; never linkable. */
export interface OverlayLine {
  points: [number, number][];
  color?: string;
  dashed?: boolean;
}

/** A horizontal reference line on a bar/line plot (a control limit, VIP = 1). */
export interface LimitLine {
  value: number;
  label?: string;
  color?: string;
  dashed?: boolean;
}
