<script lang="ts">
  import type { LinkGroup } from '$lib/plots';
  import VariableInspector from './VariableInspector.svelte';

  interface Props {
    datasetId: string;
    column: string;
    /** Shared brushing context: selected rows are highlighted in the raw plot. */
    link?: LinkGroup;
    onclose: () => void;
  }
  let { datasetId, column, link, onclose }: Props = $props();

  function onKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape') onclose();
  }
</script>

<svelte:window onkeydown={onKeydown} />

<!-- svelte-ignore a11y_click_events_have_key_events -->
<div class="backdrop" role="presentation" onclick={onclose}>
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <div
    class="modal"
    role="dialog"
    aria-modal="true"
    aria-label="Raw variable data"
    tabindex="-1"
    onclick={(e) => e.stopPropagation()}
  >
    <header>
      <h3>Raw data · {column}</h3>
      <button type="button" class="close" aria-label="Close" onclick={onclose}>×</button>
    </header>
    <VariableInspector {datasetId} {column} {link} />
  </div>
</div>

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.4);
    display: flex;
    align-items: center;
    justify-content: center;
    /* Above the contribution modal (z-index 50) it opens from. */
    z-index: 60;
    padding: 1rem;
  }
  .modal {
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.25);
    width: min(640px, 100%);
    max-height: 90vh;
    overflow: auto;
    padding: 1rem 1.25rem 1.25rem;
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    margin-bottom: 0.5rem;
  }
  h3 {
    margin: 0;
    font-size: 1.05rem;
  }
  .close {
    border: none;
    background: none;
    font-size: 1.6rem;
    line-height: 1;
    cursor: pointer;
    color: #555;
  }
  .close:hover {
    color: #000;
  }
</style>
