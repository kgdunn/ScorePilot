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
    /** Fired when the focused cell changes (keyboard navigation or click). */
    oncellfocus?: (row: number, columnId: string) => void;
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
    onheaderclick,
    oncellfocus
  }: Props = $props();

  const DEFAULT_WIDTH = 120;

  let viewport = $state<HTMLDivElement | null>(null);
  let scrollTop = $state(0);
  let viewportHeight = $state(400);
  // The focused cell (for keyboard navigation); null until first interaction.
  let focusedRow = $state<number | null>(null);
  let focusedCol = $state<number | null>(null);

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
  const frozenWidth = $derived(
    leftOffsets.slice(0, frozenColumns).reduce((sum, _, i) => sum + widths[i], 0)
  );

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

  /** Scroll so cell (row, colIndex) is fully visible, allowing for the sticky
   * header and any frozen columns. Only adjusts the axes that need it. */
  function ensureVisible(row: number, colIndex: number) {
    if (!viewport) return;
    const vh = viewport.clientHeight;
    const top = row * rowHeight;
    // Keep the row clear of the sticky header (top) and within the bottom edge.
    if (viewport.scrollTop > top) {
      viewport.scrollTop = top;
    } else if (viewport.scrollTop < headerHeight + (row + 1) * rowHeight - vh) {
      viewport.scrollTop = headerHeight + (row + 1) * rowHeight - vh;
    }
    if (colIndex >= frozenColumns) {
      const vw = viewport.clientWidth;
      const left = leftOffsets[colIndex];
      const right = left + widths[colIndex];
      // Keep the column clear of the frozen columns (left) and the right edge.
      if (viewport.scrollLeft > left - frozenWidth) {
        viewport.scrollLeft = Math.max(0, left - frozenWidth);
      } else if (viewport.scrollLeft < right - vw) {
        viewport.scrollLeft = right - vw;
      }
    }
  }

  function focusCell(row: number, colIndex: number, emit = true) {
    const r = Math.max(0, Math.min(rowCount - 1, row));
    const c = Math.max(0, Math.min(columns.length - 1, colIndex));
    focusedRow = r;
    focusedCol = c;
    ensureVisible(r, c);
    if (emit) oncellfocus?.(r, columns[c].id);
  }

  function onKeydown(event: KeyboardEvent) {
    if (rowCount === 0 || columns.length === 0) return;
    const row = focusedRow ?? 0;
    const col = focusedCol ?? 0;
    const pageRows = Math.max(1, Math.floor(viewportHeight / rowHeight) - 1);
    switch (event.key) {
      case 'ArrowRight':
        focusCell(row, col + 1);
        break;
      case 'ArrowLeft':
        focusCell(row, col - 1);
        break;
      case 'ArrowDown':
        focusCell(row + 1, col);
        break;
      case 'ArrowUp':
        focusCell(row - 1, col);
        break;
      case 'Home':
        focusCell(row, 0);
        break;
      case 'End':
        focusCell(row, columns.length - 1);
        break;
      case 'PageDown':
        focusCell(row + pageRows, col);
        break;
      case 'PageUp':
        focusCell(row - pageRows, col);
        break;
      default:
        return;
    }
    // Arrow keys etc. would otherwise scroll the viewport natively; we move the
    // focused cell (and scroll it into view) instead.
    event.preventDefault();
  }
</script>

<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
<div
  class="dg-viewport"
  bind:this={viewport}
  onscroll={onScroll}
  onkeydown={onKeydown}
  role="grid"
  tabindex="0"
>
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
              class:focused={r === focusedRow && i === focusedCol}
              style="width:{widths[i]}px;{isFrozen(i) ? ` left:${leftOffsets[i]}px;` : ''}"
              role="gridcell"
              tabindex="-1"
              onclick={(e) => {
                focusCell(r, i, false);
                viewport?.focus();
                oncellclick?.(r, col.id, e);
              }}
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
  .dg-cell.focused {
    outline: 2px solid #2b6cb0;
    outline-offset: -2px;
    z-index: 1;
  }
  .dg-viewport:focus {
    outline: none;
  }
  .dg-viewport:focus-visible {
    outline: 2px solid #2b6cb0;
    outline-offset: -2px;
  }
</style>
