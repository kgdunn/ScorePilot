<script lang="ts">
  import type { ColumnMeta, ColumnType, IdentifierRole } from '$lib/api';

  interface Props {
    selected: ColumnMeta | null;
    isX: boolean;
    isY: boolean;
    isExcludedColumn: boolean;
    form: 'raw' | 'scaled';
    xCount: number;
    yCount: number;
    excludedRowCount: number;
    onIdentifier: (role: IdentifierRole) => void;
    onRole: (role: 'x' | 'y') => void;
    onType: (type: ColumnType) => void;
    onToggleExcludeColumn: () => void;
    onToggleForm: () => void;
  }
  let {
    selected,
    isX,
    isY,
    isExcludedColumn,
    form,
    xCount,
    yCount,
    excludedRowCount,
    onIdentifier,
    onRole,
    onType,
    onToggleExcludeColumn,
    onToggleForm
  }: Props = $props();

  const none = $derived(selected === null);
</script>

<div class="ribbon">
  <div class="group">
    <div class="buttons">
      <button disabled={none} onclick={() => onIdentifier('primary')}>Primary</button>
      <button disabled={none} onclick={() => onIdentifier('secondary')}>Secondary</button>
      <button disabled={none} onclick={() => onIdentifier('class')}>Class</button>
    </div>
    <span class="label">Identifiers</span>
  </div>

  <div class="group">
    <div class="buttons">
      <button class:active={isX} disabled={none} onclick={() => onRole('x')}>X</button>
      <button class:active={isY} disabled={none} onclick={() => onRole('y')}>Y</button>
    </div>
    <span class="label">Variable roles</span>
  </div>

  <div class="group">
    <div class="buttons">
      <button disabled={none} onclick={() => onType('quantitative')}>Quantitative</button>
      <button disabled={none} onclick={() => onType('qualitative')}>Qualitative</button>
      <button disabled={none} onclick={() => onType('datetime')}>Date/Time</button>
    </div>
    <span class="label">Data types</span>
  </div>

  <div class="group">
    <div class="buttons">
      <button class:active={isExcludedColumn} disabled={none} onclick={onToggleExcludeColumn}>
        {isExcludedColumn ? 'Include' : 'Exclude'} column
      </button>
    </div>
    <span class="label">Exclude</span>
  </div>

  <div class="group">
    <div class="buttons">
      <button class:active={form === 'scaled'} onclick={onToggleForm}>
        {form === 'scaled' ? 'Scaled' : 'Raw'}
      </button>
    </div>
    <span class="label">View</span>
  </div>

  <div class="status" data-testid="ribbon-status">
    <span>X: {xCount}</span>
    <span>Y: {yCount}</span>
    <span>excluded rows: {excludedRowCount}</span>
    <span class="sel">{selected ? selected.name : 'no column selected'}</span>
  </div>
</div>

<style>
  .ribbon {
    display: flex;
    align-items: stretch;
    gap: 0.75rem;
    flex-wrap: wrap;
    padding: 0.5rem 0.75rem;
    background: #f3f4f6;
    border: 1px solid #e2e2e2;
    border-radius: 8px;
  }
  .group {
    display: flex;
    flex-direction: column;
    align-items: center;
    border-right: 1px solid #e0e0e0;
    padding-right: 0.75rem;
  }
  .buttons {
    display: flex;
    gap: 0.3rem;
  }
  .label {
    font-size: 0.7rem;
    color: #888;
    margin-top: 0.25rem;
  }
  button {
    padding: 0.3rem 0.55rem;
    border: 1px solid #cbd5e1;
    background: #fff;
    border-radius: 5px;
    cursor: pointer;
    font-size: 0.8rem;
  }
  button:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
  button.active {
    background: #2b6cb0;
    color: #fff;
    border-color: #2b6cb0;
  }
  .status {
    display: flex;
    align-items: center;
    gap: 0.8rem;
    margin-left: auto;
    font-size: 0.78rem;
    color: #555;
  }
  .status .sel {
    font-weight: 600;
    color: #2b6cb0;
  }
</style>
