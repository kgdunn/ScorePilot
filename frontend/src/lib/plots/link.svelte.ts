// The brushing / linking context shared between plots.
//
// A `LinkGroup` holds the current selection (and hover) on two independent
// dimensions - rows and columns - as opaque id strings. Any view that reads the
// group reflects selections made in any other view that writes to it: scatter
// plots, bar plots, a data grid, a raw-data panel. The group is domain-agnostic;
// it never learns what a row or column id means.

import { SvelteSet } from 'svelte/reactivity';

export class LinkGroup {
  /** Selected row ids (e.g. observations). */
  readonly rows = new SvelteSet<string>();
  /** Selected column ids (e.g. variables). */
  readonly cols = new SvelteSet<string>();
  /** Row currently hovered in some view, echoed to the others (or null). */
  hoveredRow = $state<string | null>(null);
  /** Column currently hovered in some view (or null). */
  hoveredCol = $state<string | null>(null);

  hasRow(id: string): boolean {
    return this.rows.has(id);
  }
  hasCol(id: string): boolean {
    return this.cols.has(id);
  }

  toggleRow(id: string): void {
    if (this.rows.has(id)) this.rows.delete(id);
    else this.rows.add(id);
  }
  toggleCol(id: string): void {
    if (this.cols.has(id)) this.cols.delete(id);
    else this.cols.add(id);
  }

  addRows(ids: Iterable<string>): void {
    for (const id of ids) this.rows.add(id);
  }
  addCols(ids: Iterable<string>): void {
    for (const id of ids) this.cols.add(id);
  }

  clearRows(): void {
    this.rows.clear();
  }
  clearCols(): void {
    this.cols.clear();
  }
  /** Clear every selection on both dimensions. */
  reset(): void {
    this.rows.clear();
    this.cols.clear();
    this.hoveredRow = null;
    this.hoveredCol = null;
  }

  /** Total number of selected marks across both dimensions. */
  get size(): number {
    return this.rows.size + this.cols.size;
  }
}

/** Create an independent linking context (one per page / linked-views cluster). */
export function createLinkGroup(): LinkGroup {
  return new LinkGroup();
}
