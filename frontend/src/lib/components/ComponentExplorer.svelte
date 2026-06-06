<script lang="ts">
  import { LinePlot } from '$lib/plots';
  import type { CrossValidation } from '$lib/api';

  interface Props {
    /** Currently-explored component count (live-previewed). */
    components: number;
    /** The count actually persisted on the model. */
    stored: number;
    min?: number;
    max: number;
    recommended: number | null;
    cv: CrossValidation | null;
    /** A preview fetch for the current count is in flight. */
    previewing?: boolean;
    /** An "apply" (persist) is in flight. */
    applying?: boolean;
    onapply: () => void;
  }
  let {
    components = $bindable(),
    stored,
    min = 1,
    max,
    recommended,
    cv,
    previewing = false,
    applying = false,
    onapply
  }: Props = $props();

  const dirty = $derived(components !== stored);
  const pct = (v: number | undefined): string =>
    v == null ? '–' : `${v >= 0 ? '+' : ''}${(v * 100).toFixed(1)}%`;

  // Marginal gain of the current component, and of the one that would come next.
  const thisR2 = $derived(cv?.r2_per_component[components - 1]);
  const thisQ2 = $derived(cv?.q2_per_component[components - 1]);
  const nextR2 = $derived(cv ? cv.r2_per_component[components] : undefined);
  const nextQ2 = $derived(cv ? cv.q2_per_component[components] : undefined);

  function clamp(n: number): number {
    return Math.max(min, Math.min(max, n));
  }
  const step = (delta: number) => (components = clamp(components + delta));

  // The R²/Q² curve, with the current count marked (solid) and the
  // cross-validation recommendation marked (dashed) when they differ.
  const xMarks = $derived(
    cv
      ? [
          { value: String(components), label: `${components}`, color: '#2b6cb0' },
          ...(recommended && recommended !== components
            ? [{ value: String(recommended), label: 'rec', color: '#dd6b20', dashed: true }]
            : [])
        ]
      : []
  );
</script>

<div class="explorer" class:dirty>
  <div class="controls">
    <div class="count">
      <span class="label">Components</span>
      <div class="stepper">
        <button type="button" aria-label="Remove a component" disabled={components <= min} onclick={() => step(-1)}>−</button>
        <span class="value" class:busy={previewing}>{components}</span>
        <button type="button" aria-label="Add a component" disabled={components >= max} onclick={() => step(1)}>+</button>
      </div>
      <input
        class="slider"
        type="range"
        {min}
        {max}
        step="1"
        bind:value={components}
        aria-label="Number of components"
      />
    </div>

    <div class="actions">
      {#if recommended}
        <button
          type="button"
          class="rec"
          class:active={components === recommended}
          title="Cross-validation suggests this many components"
          onclick={() => (components = clamp(recommended))}
        >
          ✨ Recommended: {recommended}
        </button>
      {/if}
      {#if dirty}
        <button type="button" class="apply" disabled={applying} onclick={onapply}>
          {applying ? 'Applying…' : `Apply ${components} component${components === 1 ? '' : 's'}`}
        </button>
        <span class="from">was {stored}</span>
      {:else}
        <span class="saved">✓ current model</span>
      {/if}
    </div>

    {#if cv}
      <p class="gain">
        Component <strong>{components}</strong> adds <strong>{pct(thisR2)}</strong> fit (R²),
        <strong>{pct(thisQ2)}</strong> predicted (Q²).
        {#if components < max}
          <span class="next">Next would add {pct(nextR2)} / {pct(nextQ2)}.</span>
        {:else}
          <span class="next">This is the maximum.</span>
        {/if}
      </p>
    {/if}
  </div>

  {#if cv}
    <div class="curve">
      <LinePlot
        series={[
          { name: `R² (${cv.target})`, values: cv.r2, color: '#2b6cb0' },
          { name: `Q² (${cv.target})`, values: cv.q2, color: '#2f855a' }
        ]}
        labels={cv.component_numbers}
        xName="components"
        yName="cumulative"
        legend
        {xMarks}
        height="200px"
      />
    </div>
  {/if}
</div>

<style>
  .explorer {
    display: grid;
    grid-template-columns: minmax(240px, 1fr) minmax(280px, 1.4fr);
    gap: 1rem;
    align-items: center;
    border: 1px solid #e6e6e6;
    border-radius: 10px;
    background: linear-gradient(180deg, #f7fbff, #ffffff);
    padding: 0.9rem 1rem;
    transition: box-shadow 0.2s, border-color 0.2s;
  }
  .explorer.dirty {
    border-color: #2b6cb0;
    box-shadow: 0 0 0 1px #2b6cb0 inset;
  }
  .count {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    flex-wrap: wrap;
  }
  .label {
    font-size: 0.8rem;
    color: #666;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .stepper {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
  }
  .stepper button {
    width: 30px;
    height: 30px;
    border: 1px solid #2b6cb0;
    background: #fff;
    color: #2b6cb0;
    border-radius: 50%;
    font-size: 1.2rem;
    line-height: 1;
    cursor: pointer;
  }
  .stepper button:disabled {
    opacity: 0.4;
    cursor: default;
  }
  .value {
    min-width: 1.6ch;
    text-align: center;
    font-size: 1.8rem;
    font-weight: 700;
    color: #1c3b5a;
    transition: opacity 0.15s;
  }
  .value.busy {
    opacity: 0.45;
  }
  .slider {
    flex: 1;
    min-width: 120px;
    accent-color: #2b6cb0;
  }
  .actions {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    flex-wrap: wrap;
    margin-top: 0.6rem;
  }
  .actions button {
    border-radius: 999px;
    padding: 0.3rem 0.8rem;
    font-size: 0.82rem;
    cursor: pointer;
    border: 1px solid #cdd7e1;
    background: #fff;
    color: #2b4a66;
  }
  .rec.active {
    border-color: #dd6b20;
    color: #b85c14;
    background: #fff7ed;
  }
  .apply {
    border-color: #2b6cb0 !important;
    background: #2b6cb0 !important;
    color: #fff !important;
    font-weight: 600;
  }
  .apply:disabled {
    opacity: 0.6;
    cursor: default;
  }
  .from {
    font-size: 0.78rem;
    color: #999;
  }
  .saved {
    font-size: 0.82rem;
    color: #2f855a;
  }
  .gain {
    margin: 0.6rem 0 0;
    font-size: 0.82rem;
    color: #555;
    line-height: 1.4;
  }
  .gain .next {
    color: #888;
  }
  .curve {
    min-width: 0;
  }
  @media (max-width: 760px) {
    .explorer {
      grid-template-columns: 1fr;
    }
  }
</style>
