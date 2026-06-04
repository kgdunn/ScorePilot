<script lang="ts">
  import { goto } from '$app/navigation';
  import {
    fitModel,
    getDataset,
    getGridAll,
    getQuality,
    patchColumn,
    type ColumnMeta,
    type ColumnType,
    type DatasetDetail,
    type GridWindow,
    type IdentifierRole,
    type QualityReport,
    type TransformKind
  } from '$lib/api';
  import { DataGrid, type CellValue, type GridColumn } from '$lib/grid';
  import { emptyDraft, toApiSpec, toggle, toggleNumber, type DraftSpec } from '$lib/spec';
  import Ribbon from './Ribbon.svelte';
  import VariableInspector from './VariableInspector.svelte';
  import QualityPanel from './QualityPanel.svelte';

  interface Props {
    datasetId: string;
  }
  let { datasetId }: Props = $props();

  let detail = $state<DatasetDetail | null>(null);
  let grid = $state<GridWindow | null>(null);
  let quality = $state<QualityReport | null>(null);
  let draft = $state<DraftSpec>(emptyDraft());
  let selected = $state<string | null>(null);
  let form = $state<'raw' | 'scaled'>('raw');
  let error = $state<string | null>(null);
  let loading = $state(true);

  let fitKind = $state<'PCA' | 'PLS'>('PCA');
  let fitComponents = $state(2);
  let fitName = $state('');
  let fitting = $state(false);

  async function loadAll() {
    loading = true;
    error = null;
    try {
      detail = await getDataset(datasetId);
      grid = await getGridAll(datasetId, form);
      quality = await getQuality(datasetId);
    } catch (e) {
      error = (e as Error).message;
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    void datasetId;
    void loadAll();
  });

  const metaByName = $derived.by(() => {
    const map = new Map<string, ColumnMeta>();
    detail?.columns.forEach((c) => map.set(c.name, c));
    return map;
  });

  const colIndex = $derived.by(() => {
    const map = new Map<string, number>();
    grid?.column_names.forEach((name, i) => map.set(name, i));
    return map;
  });

  const invalidByColumn = $derived.by(() => {
    const map = new Map<string, Set<number>>();
    quality?.columns.forEach((c) => {
      if (c.invalid_rows.length) map.set(c.name, new Set(c.invalid_rows));
    });
    return map;
  });

  const gridColumns = $derived.by<GridColumn[]>(() => {
    if (!grid) return [];
    const cols: GridColumn[] = [{ id: '__id', header: detail?.primary_id ?? '#', width: 150 }];
    for (const name of grid.column_names) cols.push({ id: name, header: name, width: 130 });
    return cols;
  });

  function getCell(row: number, columnId: string): CellValue {
    if (!grid) return '';
    if (columnId === '__id') return grid.row_identifiers[row];
    const idx = colIndex.get(columnId);
    return idx === undefined ? '' : grid.cells[row]?.[idx];
  }

  function headerClass(columnId: string): string {
    if (columnId === '__id') return 'h-id';
    const classes: string[] = [];
    if (selected === columnId) classes.push('h-selected');
    if (draft.excludedColumns.includes(columnId)) classes.push('h-excluded');
    if (draft.xColumns.includes(columnId)) classes.push('h-x');
    else if (draft.yColumns.includes(columnId)) classes.push('h-y');
    else if (metaByName.get(columnId)?.identifier_role !== 'none') classes.push('h-id-role');
    return classes.join(' ');
  }

  function cellClass(row: number, columnId: string): string {
    const classes: string[] = [];
    if (draft.excludedRows.includes(row)) classes.push('c-excluded-row');
    if (columnId === '__id') {
      classes.push('c-id');
      return classes.join(' ');
    }
    if (draft.excludedColumns.includes(columnId)) classes.push('c-excluded-col');
    if (invalidByColumn.get(columnId)?.has(row)) classes.push('c-invalid');
    return classes.join(' ');
  }

  function onHeaderClick(columnId: string) {
    selected = columnId === '__id' ? null : columnId;
  }

  function onCellClick(row: number, columnId: string) {
    if (columnId === '__id') {
      draft = { ...draft, excludedRows: toggleNumber(draft.excludedRows, row) };
    } else {
      selected = columnId;
    }
  }

  const selectedMeta = $derived(selected ? (metaByName.get(selected) ?? null) : null);

  async function setIdentifier(role: IdentifierRole) {
    if (!selected) return;
    try {
      detail = await patchColumn(datasetId, selected, { identifier_role: role });
    } catch (e) {
      error = (e as Error).message;
    }
  }

  async function setType(type: ColumnType) {
    if (!selected) return;
    try {
      detail = await patchColumn(datasetId, selected, { column_type: type });
      grid = await getGridAll(datasetId, form);
    } catch (e) {
      error = (e as Error).message;
    }
  }

  function setRole(role: 'x' | 'y') {
    if (!selected) return;
    if (role === 'x') {
      draft = {
        ...draft,
        xColumns: toggle(draft.xColumns, selected),
        yColumns: draft.yColumns.filter((c) => c !== selected)
      };
    } else {
      draft = {
        ...draft,
        yColumns: toggle(draft.yColumns, selected),
        xColumns: draft.xColumns.filter((c) => c !== selected)
      };
    }
  }

  function toggleExcludeColumn() {
    if (!selected) return;
    draft = { ...draft, excludedColumns: toggle(draft.excludedColumns, selected) };
  }

  async function toggleForm() {
    form = form === 'raw' ? 'scaled' : 'raw';
    grid = await getGridAll(datasetId, form);
  }

  function applyTransform(column: string, transform: TransformKind) {
    const transforms = { ...draft.transforms };
    if (transform === 'none') delete transforms[column];
    else transforms[column] = { kind: transform, c1: 0, c2: 1 };
    draft = { ...draft, transforms };
  }

  function effectiveXColumns(): string[] {
    if (draft.xColumns.length > 0) return draft.xColumns;
    if (!detail) return [];
    return detail.columns
      .filter((c) => c.column_type === 'quantitative' && !draft.excludedColumns.includes(c.name))
      .map((c) => c.name);
  }

  async function onFit() {
    if (!detail) return;
    fitting = true;
    error = null;
    try {
      const spec = toApiSpec(draft) as Record<string, unknown>;
      spec.x_columns = effectiveXColumns();
      const result = await fitModel({
        dataset_id: datasetId,
        kind: fitKind,
        n_components: fitComponents,
        name: fitName || null,
        spec
      });
      await goto(`/models/${result.summary.id}`);
    } catch (e) {
      error = (e as Error).message;
    } finally {
      fitting = false;
    }
  }
</script>

<div class="explorer" data-testid="explorer">
  {#if error}<p class="error">{error}</p>{/if}
  {#if loading}<p class="hint">Loading…</p>{/if}

  {#if detail}
    <Ribbon
      selected={selectedMeta}
      isX={selected ? draft.xColumns.includes(selected) : false}
      isY={selected ? draft.yColumns.includes(selected) : false}
      isExcludedColumn={selected ? draft.excludedColumns.includes(selected) : false}
      {form}
      xCount={draft.xColumns.length}
      yCount={draft.yColumns.length}
      excludedRowCount={draft.excludedRows.length}
      onIdentifier={setIdentifier}
      onRole={setRole}
      onType={setType}
      onToggleExcludeColumn={toggleExcludeColumn}
      onToggleForm={toggleForm}
    />

    <div class="legend">
      <span class="chip x">X</span><span class="chip y">Y</span>
      <span class="chip idr">identifier</span><span class="chip ex">excluded</span>
      <span class="chip inv">invalid</span>
      <span class="muted">Click a header to select a column; click a row id to exclude it.</span>
    </div>

    <div class="main">
      <div class="grid-area">
        {#if grid}
          <DataGrid
            columns={gridColumns}
            rowCount={detail.n_rows}
            {getCell}
            frozenColumns={1}
            headerHeight={58}
            {cellClass}
            {headerClass}
            onheaderclick={onHeaderClick}
            oncellclick={onCellClick}
          >
            {#snippet headerCell(col)}
              {#if col.id === '__id'}
                <div class="hc" data-col="__id"><strong>{col.header}</strong></div>
              {:else}
                {@const meta = metaByName.get(col.id)}
                <div class="hc" data-col={col.id}>
                  <strong>{col.id}</strong>
                  <span class="badge">{meta?.column_type ?? ''}</span>
                </div>
              {/if}
            {/snippet}
          </DataGrid>
        {/if}
      </div>

      <aside class="side">
        {#if selected}
          <VariableInspector {datasetId} column={selected} onApplyTransform={applyTransform} />
        {:else}
          <p class="hint">Select a column to inspect it.</p>
        {/if}
      </aside>
    </div>

    <section class="quality-area">
      <h3>Data quality</h3>
      <QualityPanel report={quality} />
    </section>

    <section class="build-area">
      <h3>Build a model</h3>
      <div class="build-row">
        <label>
          Type
          <select bind:value={fitKind}>
            <option value="PCA">PCA</option>
            <option value="PLS">PLS</option>
          </select>
        </label>
        <label>Components <input type="number" min="1" max="20" bind:value={fitComponents} /></label>
        <label>Name <input type="text" placeholder="optional" bind:value={fitName} /></label>
        <button data-testid="fit-model" onclick={onFit} disabled={fitting}>
          {fitting ? 'Fitting…' : 'Fit model'}
        </button>
        <a class="hangar-link" href="/models">Hangar →</a>
      </div>
      <p class="hint">
        X: {effectiveXColumns().length} variables{draft.xColumns.length === 0
          ? ' (all quantitative)'
          : ''}{fitKind === 'PLS' ? `, Y: ${draft.yColumns.length}` : ''}. Excluded rows:
        {draft.excludedRows.length}.
        {#if fitKind === 'PLS' && draft.yColumns.length === 0}
          <span class="warn">Choose Y variables for PLS.</span>
        {/if}
      </p>
    </section>
  {/if}
</div>

<style>
  .explorer {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }
  .main {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 360px;
    gap: 0.75rem;
    align-items: stretch;
  }
  .grid-area {
    height: 60vh;
    min-height: 360px;
  }
  .side {
    border: 1px solid #e2e2e2;
    border-radius: 8px;
    padding: 0.75rem;
    overflow: auto;
    height: 60vh;
  }
  .legend {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.78rem;
  }
  .chip {
    padding: 1px 8px;
    border-radius: 10px;
    color: #fff;
  }
  .chip.x {
    background: #2b6cb0;
  }
  .chip.y {
    background: #2f855a;
  }
  .chip.idr {
    background: #805ad5;
  }
  .chip.ex {
    background: #999;
  }
  .chip.inv {
    background: #c53030;
  }
  .muted {
    color: #888;
  }
  .quality-area {
    border: 1px solid #e2e2e2;
    border-radius: 8px;
    padding: 0.5rem 0.75rem;
  }
  .quality-area h3 {
    margin: 0 0 0.4rem;
    font-size: 0.95rem;
  }
  .hc {
    display: flex;
    flex-direction: column;
    line-height: 1.2;
  }
  .badge {
    font-size: 0.68rem;
    color: #777;
  }
  .error {
    color: #b3261e;
  }
  .hint {
    color: #777;
  }
  /* Header role colours, applied via headerClass. */
  .explorer :global(.dg-hcell.h-selected) {
    outline: 2px solid #2b6cb0;
    outline-offset: -2px;
  }
  .explorer :global(.dg-hcell.h-x) {
    background: #e6eff7;
  }
  .explorer :global(.dg-hcell.h-y) {
    background: #e6f2ea;
  }
  .explorer :global(.dg-hcell.h-id-role) {
    background: #efe9f9;
  }
  .explorer :global(.dg-hcell.h-excluded) {
    background: #eee;
    color: #999;
    text-decoration: line-through;
  }
  .explorer :global(.dg-cell.c-id) {
    cursor: pointer;
    color: #555;
    background: #fafafa;
  }
  .explorer :global(.dg-cell.c-excluded-row) {
    background: #f3f3f3;
    color: #aaa;
    text-decoration: line-through;
  }
  .explorer :global(.dg-cell.c-excluded-col) {
    background: #f3f3f3;
    color: #aaa;
  }
  .explorer :global(.dg-cell.c-invalid) {
    background: #fdecea;
    color: #b3261e;
  }
  .build-area {
    border: 1px solid #e2e2e2;
    border-radius: 8px;
    padding: 0.5rem 0.75rem;
  }
  .build-area h3 {
    margin: 0 0 0.4rem;
    font-size: 0.95rem;
  }
  .build-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }
  .build-row label {
    display: flex;
    align-items: center;
    gap: 0.3rem;
    font-size: 0.85rem;
  }
  .build-row input[type='number'] {
    width: 4rem;
    padding: 0.25rem;
  }
  .build-row input[type='text'] {
    padding: 0.25rem;
  }
  .build-row button {
    padding: 0.35rem 0.8rem;
    border: 1px solid #2b6cb0;
    background: #2b6cb0;
    color: #fff;
    border-radius: 6px;
    cursor: pointer;
  }
  .build-row button:disabled {
    opacity: 0.5;
  }
  .hangar-link {
    margin-left: auto;
    font-size: 0.85rem;
  }
  .warn {
    color: #b3261e;
  }
</style>
