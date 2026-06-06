<script lang="ts">
  import type { Contributions } from '$lib/api';
  import { BarPlot, type LinkGroup, type PlotPoint } from '$lib/plots';

  interface Props {
    contributions: Contributions;
    /** Which diagnostic the contributions explain. */
    metric: 't2' | 'spe';
    onclose: () => void;
    /** Shared brushing context, so selected variables stay highlighted here. */
    link?: LinkGroup;
    /** Fired when a contribution bar is clicked, with that variable's name. */
    onVariableClick?: (variable: string) => void;
  }
  let { contributions, metric, onclose, link, onVariableClick }: Props = $props();

  const label = $derived(metric === 'spe' ? 'SPE' : "Hotelling's T²");
  const values = $derived(metric === 'spe' ? contributions.spe : contributions.t2);
  const points = $derived<PlotPoint[]>(
    contributions.variable_names.map((name, i) => ({ colId: name, x: name, y: values[i] }))
  );

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
    aria-label="Contribution plot"
    tabindex="-1"
    onclick={(e) => e.stopPropagation()}
  >
    <header>
      <h3>Contributions to {label} · {contributions.observation_name}</h3>
      <button type="button" class="close" aria-label="Close" onclick={onclose}>×</button>
    </header>
    <p class="hint">
      Per-variable contribution of this observation to its {label}. Click a bar to
      see that variable's raw data.
    </p>
    <BarPlot
      {points}
      yName={`${label} contribution`}
      xName="variable"
      {link}
      linkBy="col"
      height="340px"
      onitemclick={(a) => onVariableClick?.(contributions.variable_names[a.dataIndex])}
    />
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
    z-index: 50;
    padding: 1rem;
  }
  .modal {
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.25);
    width: min(760px, 100%);
    max-height: 90vh;
    overflow: auto;
    padding: 1rem 1.25rem 1.25rem;
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
  }
  h3 {
    margin: 0;
    font-size: 1.05rem;
  }
  .hint {
    margin: 0.25rem 0 0.5rem;
    color: #666;
    font-size: 0.85rem;
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
