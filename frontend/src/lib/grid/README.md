# DataGrid

A standalone, dependency-free, row-virtualized data grid for Svelte 5.

It is intentionally domain-agnostic: it knows nothing about your data model. You
supply columns, a row count, and a cell accessor; you control all styling and
header/cell content through class callbacks and snippets; and you react to
interaction through events. This keeps the component reusable across projects -
copy the `grid/` folder and go. It has no third-party dependencies.

## Usage

```svelte
<script lang="ts">
  import { DataGrid, type GridColumn } from '$lib/grid';

  const columns: GridColumn[] = [
    { id: 'name', header: 'Name', width: 160 },
    { id: 'value', header: 'Value', width: 100 }
  ];
  const data = [{ name: 'a', value: 1 }, { name: 'b', value: 2 }];
</script>

<div style="height: 480px">
  <DataGrid
    {columns}
    rowCount={data.length}
    getCell={(row, columnId) => data[row][columnId]}
    frozenColumns={1}
    oncellclick={(row, columnId) => console.log(row, columnId)}
  />
</div>
```

## Props

| Prop            | Type                                                       | Default | Description                                  |
| --------------- | ---------------------------------------------------------- | ------- | -------------------------------------------- |
| `columns`       | `GridColumn[]`                                             | -       | Column descriptors (`id`, `header`, `width`).|
| `rowCount`      | `number`                                                   | -       | Total number of rows.                        |
| `getCell`       | `(row, columnId) => CellValue`                             | -       | Cell value accessor.                         |
| `rowHeight`     | `number`                                                   | `28`    | Row height in pixels.                        |
| `headerHeight`  | `number`                                                   | `66`    | Header height in pixels.                     |
| `frozenColumns` | `number`                                                   | `0`     | Number of leftmost columns to freeze.        |
| `overscan`      | `number`                                                   | `6`     | Extra rows rendered above/below the viewport.|
| `cellClass`     | `(row, columnId) => string`                                | -       | Extra CSS classes per cell.                  |
| `headerClass`   | `(columnId) => string`                                     | -       | Extra CSS classes per header cell.           |
| `headerCell`    | `Snippet<[GridColumn]>`                                    | -       | Custom header content.                       |
| `cell`          | `Snippet<[number, GridColumn, CellValue]>`                 | -       | Custom cell content.                         |
| `oncellclick`   | `(row, columnId, event) => void`                           | -       | Cell click handler.                          |
| `onheaderclick` | `(columnId, event) => void`                                | -       | Header click handler.                        |

The grid virtualizes rows (only the visible window is rendered), supports frozen
columns and a sticky header, and sizes itself to its container - give the parent
a height.
