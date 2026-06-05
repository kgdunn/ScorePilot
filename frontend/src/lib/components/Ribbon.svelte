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
    <!-- All columns are X by default; only show a count once the user narrows it. -->
    {#if xCount > 0}<span>X: {xCount}</span>{/if}
    {#if yCount > 0}<span>Y: {yCount}</span>{/if}
    {#if excludedRowCount > 0}<span>excluded rows: {excludedRowCount}</span>{/if}
    <span class="sel">{selected ? selected.name : 'no column selected'}</span>
  </div>
</div>

<style>
  /* The ribbon floats: it stays pinned to the top of the viewport so the role and
     type controls remain reachable while scrolling the grid. Kept compact to avoid
     heavy wrapping on narrow screens. */
  .ribbon {
    position: sticky;
    top: 0;
    z-index: 20;
    display: flex;
    align-items: center;
    gap: 0.35rem 0.5rem;
    flex-wrap: wrap;
    padding: 0.3rem 0.5rem;
    background: #f3f4f6;
    border: 1px solid #e2e2e2;
    border-radius: 8px;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08);
  }
  .group {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.1rem;
    border-right: 1px solid #e0e0e0;
    padding-right: 0.5rem;
  }
  .buttons {
    display: flex;
    gap: 0.2rem;
  }
  .label {
    font-size: 0.6rem;
    text-transform: uppercase;
    letter-spacing: 0.02em;
    color: #999;
  }
  button {
    padding: 0.22rem 0.45rem;
    border: 1px solid #cbd5e1;
    background: #fff;
    border-radius: 5px;
    cursor: pointer;
    font-size: 0.76rem;
    white-space: nowrap;
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
    gap: 0.6rem;
    margin-left: auto;
    font-size: 0.74rem;
    color: #555;
  }
  .status .sel {
    font-weight: 600;
    color: #2b6cb0;
  }

  /* On phones, keep the ribbon to a single tight row that scrolls sideways rather
     than wrapping into a tall block; the captions are dropped to save height. */
  @media (max-width: 700px) {
    .ribbon {
      flex-wrap: nowrap;
      overflow-x: auto;
      gap: 0.4rem;
    }
    .group {
      flex: none;
    }
    .label {
      display: none;
    }
    .status {
      flex: none;
      margin-left: 0.4rem;
    }
  }
</style>
