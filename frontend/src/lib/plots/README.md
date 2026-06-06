# Plots

A standalone, domain-agnostic collection of **linked** plots for Svelte 5,
rendered with ECharts.

Like the sibling `grid/` library it is intentionally domain-agnostic: it knows
nothing about your data model. You hand each plot a list of `PlotPoint`s - each
carrying opaque `rowId` / `colId` identities - share a `LinkGroup` between plots
to brush-and-link them, and control styling, labels and tooltips through props.
This keeps the collection reusable across projects: copy the `plots/` folder and
go. Its only dependencies are Svelte 5 and ECharts (the rendering engine, the way
`grid/` depends on Svelte alone).

## The idea: brushing and linking

Every mark is a `PlotPoint` with two optional identities:

- `rowId` - links "observations" (a sample, a record). Brushing a point in one
  plot selects that **row** in every plot and view sharing the `LinkGroup`.
- `colId` - links "variables" (a measurement, a feature). Brushing selects that
  **column** everywhere.

A plot declares which dimension it links on with `linkBy="row" | "col" | "both"`.
A scatter of observations links by row; a scatter of variables links by column; a
bar chart of per-variable values links by column. Selections made anywhere show
up everywhere as the same red-square marker.

```svelte
<script lang="ts">
  import { ScatterPlot, BarPlot, createLinkGroup, type PlotPoint } from '$lib/plots';

  const link = createLinkGroup();

  const scores: PlotPoint[] = rows.map((r) => ({ rowId: r.id, x: r.t1, y: r.t2, label: r.id }));
  const loadings: PlotPoint[] = vars.map((v) => ({ colId: v.name, x: v.p1, y: v.p2, label: v.name }));
</script>

<ScatterPlot points={scores}   {link} linkBy="row" selectable xName="t1" yName="t2" />
<ScatterPlot points={loadings} {link} linkBy="col" selectable xName="p1" yName="p2" />
```

Anything else - a data grid, a raw-data panel - can read the same `link` and
highlight `link.rows` / `link.cols`, completing the linked-views picture.

## Components

| Component     | Purpose                                                            |
| ------------- | ----------------------------------------------------------------- |
| `ScatterPlot` | 2-D scatter with selection modes, lasso, labels, axis drop-downs.  |
| `BarPlot`     | Categorical bars with optional limit lines; selectable / linkable. |
| `LinePlot`    | One or more line series with an optional supplied x-axis.          |
| `Histogram`   | Frequency bars from counts + bin edges.                           |
| `PlotChart`   | Low-level ECharts host (zoom, activation, resize); rarely used directly. |

### `ScatterPlot` props

| Prop          | Type                       | Default | Description                                       |
| ------------- | -------------------------- | ------- | ------------------------------------------------- |
| `points`      | `PlotPoint[]`              | -       | The marks to draw.                                |
| `link`        | `LinkGroup`                | -       | Shared brushing context (selection + hover).      |
| `linkBy`      | `'row' \| 'col' \| 'both'` | `'row'` | Identity dimension to select on.                  |
| `selectable`  | `boolean`                  | `false` | Show the default / arrow / lasso toolbar.         |
| `xName`/`yName` | `string`                 | `''`    | Axis titles.                                      |
| `overlays`    | `OverlayLine[]`            | `[]`    | Decorative poly-lines (origin guides, an ellipse).|
| `axes`        | `AxisControl`              | -       | Renders X/Y drop-downs and reports changes.       |
| `showLabels`  | `boolean`                  | `true`  | Draw each point's `label`.                        |
| `tooltipHtml` | `(p) => string`            | -       | Custom tooltip body.                              |
| `onactivate`  | `(a) => void`              | -       | Double-click / long-press a point (drill-down).   |

`BarPlot` and `LinePlot` take the analogous `points` / `series`, `limits`, and
`link` props (see their `Props` interfaces).

## Selection modes (`selectable`)

A three-icon control appears at the top-right of a `ScatterPlot`:

- **default** - pan / zoom only (no selection).
- **arrow** - click a point to toggle it in / out of the selection.
- **lasso** - drag a faint grey dashed loop; everything enclosed is added.

Both write into the `LinkGroup` (`link.rows` / `link.cols`). Clear a selection
with `link.clearRows()` / `link.clearCols()` / `link.reset()`.

## The `LinkGroup`

```ts
const link = createLinkGroup();
link.rows;            // SvelteSet<string> of selected row ids (reactive)
link.cols;            // SvelteSet<string> of selected column ids (reactive)
link.toggleRow(id);   link.addRows(ids);   link.clearRows();
link.toggleCol(id);   link.addCols(ids);   link.clearCols();
link.hoveredRow;      link.hoveredCol;     // hover echoed across views
link.size;            link.reset();
```

It is plain reactive state - read it anywhere (plots, grids, summaries) and your
UI stays in sync.

## Coming soon

The `PlotPoint` model already reserves per-point encoding channels so adding
them later is non-breaking:

- `color` - colour-coding by a field.
- `size` - marker-size encoding.
- `shape` - marker-shape encoding (`PlotSymbol`).

These are accepted today but not yet rendered.
