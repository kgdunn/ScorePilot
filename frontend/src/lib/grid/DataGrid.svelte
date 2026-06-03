<script lang="ts">
  // A standalone, dependency-free, row-virtualized data grid.
  //
  // It is deliberately domain-agnostic: it knows nothing about roles, data types,
  // or quality. Styling and header/cell content are injected by the caller through
  // class callbacks and snippets, and interaction is reported through events. This
  // keeps the component reusable across apps.
  import type { Snippet } from 'svelte';
  import type { CellValue, GridColumn } from './grid-types';

  interface Props {
    columns: GridColumn[];
    rowCount: number;
    /** Return the value for a cell. */
    getCell: (row: number, columnId: string) => CellValue;
    rowHeight?: number;
    headerHeight?: number;
    /** Number of leftmost columns to freeze (sticky). */
    frozenColumns?: number;
    /** Extra rows rendered above/below the viewport. */
    overscan?: number;
    cellClass?: (row: number, columnId: string) => string;
    headerClass?: (columnId: string) => string;
    headerCell?: Snippet<[GridColumn]>;
    cell?: Snippet<[number, GridColumn, CellValue]>;
    oncellclick?: (row: number, columnId: string, event: MouseEvent) => void;
    onheaderclick?: (columnId: string, event: MouseEvent) => void;
  }

  let {
    columns,
    rowCount,
    getCell,
    rowHeight = 28,
    headerHeight = 66,
    frozenColumns = 0,
    overscan = 6,
    cellClass,
    headerClass,
    headerCell,
    cell,
    oncellclick,
    onheaderclick
  }: Props = $props();

  const DEFAULT_WIDTH = 120;

  let viewport = $state<HTMLDivElement | null>(null);
  let scrollTop = $state(0);
  let viewportHeight = $state(400);

  const widths = $derived(columns.map((c) => c.width ?? DEFAULT_WIDTH));
  const leftOffsets = $derived.by(() => {
    const out: number[] = [];
    let x = 0;
    for (let i = 0; i < columns.length; i++) {
      out.push(x);
      x += widths[i];
    }
    return out;
  });
  const totalWidth = $derived(widths.reduce((a, b) => a + b, 0));

  const firstRow = $derived(Math.max(0, Math.floor(scrollTop / rowHeight) - overscan));
  const visibleRows = $derived(Math.ceil(viewportHeight / rowHeight) + overscan * 2);
  const lastRow = $derived(Math.min(rowCount, firstRow + visibleRows));
  const rows = $derived.by(() => {
    const out: number[] = [];
    for (let r = firstRow; r < lastRow; r++) out.push(r);
    return out;
  });

  function onScroll() {
    if (viewport) scrollTop = viewport.scrollTop;
  }

  $effect(() => {
    if (!viewport) return;
    const observer = new ResizeObserver(() => {
      if (viewport) viewportHeight = viewport.clientHeight;
    });
    observer.observe(viewport);
    viewportHeight = viewport.clientHeight;
    return () => observer.disconnect();
  });

  const isFrozen = (index: number) => index < frozenColumns;
</script>

<div class="dg-viewport" bind:this={viewport} onscroll={onScroll}>
  <div class="dg-content" style="width:{totalWidth}px;">
    <div class="dg-header" style="height:{headerHeight}px;">
      {#each columns as col, i (col.id)}
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <div
          class="dg-hcell {headerClass?.(col.id) ?? ''}"
          class:frozen={isFrozen(i)}
          style="width:{widths[i]}px;{isFrozen(i) ? ` left:${leftOffsets[i]}px;` : ''}"
          role="columnheader"
          tabindex="-1"
          onclick={(e) => onheaderclick?.(col.id, e)}
        >
          {#if headerCell}{@render headerCell(col)}{:else}{col.header ?? col.id}{/if}
        </div>
      {/each}
    </div>

    <div class="dg-body" style="height:{rowCount * rowHeight}px;">
      {#each rows as r (r)}
        <div class="dg-row" style="top:{r * rowHeight}px; height:{rowHeight}px;">
          {#each columns as col, i (col.id)}
            {@const value = getCell(r, col.id)}
            <!-- svelte-ignore a11y_click_events_have_key_events -->
            <div
              class="dg-cell {cellClass?.(r, col.id) ?? ''}"
              class:frozen={isFrozen(i)}
              style="width:{widths[i]}px;{isFrozen(i) ? ` left:${leftOffsets[i]}px;` : ''}"
              role="gridcell"
              tabindex="-1"
              onclick={(e) => oncellclick?.(r, col.id, e)}
            >
              {#if cell}{@render cell(r, col, value)}{:else}{value ?? ''}{/if}
            </div>
          {/each}
        </div>
      {/each}
    </div>
  </div>
</div>

<style>
  .dg-viewport {
    overflow: auto;
    position: relative;
    height: 100%;
    width: 100%;
    border: 1px solid #e2e2e2;
    border-radius: 6px;
    background: #fff;
    font-variant-numeric: tabular-nums;
  }
  .dg-content {
    position: relative;
  }
  .dg-header {
    position: sticky;
    top: 0;
    z-index: 3;
    display: flex;
    background: #f7f7f8;
    border-bottom: 1px solid #ddd;
  }
  .dg-hcell {
    position: relative;
    flex: 0 0 auto;
    box-sizing: border-box;
    padding: 4px 8px;
    border-right: 1px solid #ececec;
    overflow: hidden;
    background: #f7f7f8;
  }
  .dg-hcell.frozen {
    position: sticky;
    z-index: 4;
  }
  .dg-body {
    position: relative;
  }
  .dg-row {
    position: absolute;
    left: 0;
    display: flex;
  }
  .dg-cell {
    flex: 0 0 auto;
    box-sizing: border-box;
    padding: 4px 8px;
    border-right: 1px solid #f0f0f0;
    border-bottom: 1px solid #f0f0f0;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    background: #fff;
    cursor: default;
  }
  .dg-cell.frozen {
    position: sticky;
    z-index: 2;
  }
</style>
