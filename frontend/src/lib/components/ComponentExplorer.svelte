<script lang="ts">
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

  // Cumulative totals at the current count (shown prominently up top).
  const totalR2 = $derived(cv?.r2[components - 1]);
  const totalQ2 = $derived(cv?.q2[components - 1]);
  const fmtPct = (v: number | undefined): string => (v == null ? '–' : `${(v * 100).toFixed(1)}%`);

  // Marginal gain of the current component, and of the one that would come next.
  const thisR2 = $derived(cv?.r2_per_component[components - 1]);
  const thisQ2 = $derived(cv?.q2_per_component[components - 1]);
  const nextR2 = $derived(cv ? cv.r2_per_component[components] : undefined);
  const nextQ2 = $derived(cv ? cv.q2_per_component[components] : undefined);

  function clamp(n: number): number {
    return Math.max(min, Math.min(max, n));
  }
  const step = (delta: number) => (components = clamp(components + delta));
</script>

<div class="explorer" class:dirty>
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

  {#if cv}
    <div class="totals" title="Cumulative fit (R²) and cross-validated prediction (Q²) at this count">
      <span class="stat r2"><span class="k">R²</span> {fmtPct(totalR2)}</span>
      <span class="stat q2"><span class="k">Q²</span> {fmtPct(totalQ2)}</span>
    </div>
  {/if}

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

<style>
  .explorer {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.6rem 1.2rem;
    border: 1px solid #e6e6e6;
    border-radius: 10px;
    background: linear-gradient(180deg, #f7fbff, #ffffff);
    padding: 0.7rem 1rem;
    transition: box-shadow 0.2s, border-color 0.2s;
    /* Pin the control to the top of the viewport so the slider stays reachable
     * while scrolling down to the plots that change most with the component
     * count (SPE, T²) - they update live beneath it. The diagnostics section is
     * the containing block, so it unpins once the plots are scrolled past.
     * Kept compact (no curve) so it never eats much of a phone screen. */
    position: sticky;
    top: 0;
    z-index: 30;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.07);
  }
  .explorer.dirty {
    border-color: #2b6cb0;
    box-shadow: 0 0 0 1px #2b6cb0 inset;
  }
  .count {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    flex: 1 1 260px;
    min-width: 220px;
  }
  .label {
    font-size: 0.78rem;
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
    font-size: 1.6rem;
    font-weight: 700;
    color: #1c3b5a;
    transition: opacity 0.15s;
  }
  .value.busy {
    opacity: 0.45;
  }
  .slider {
    flex: 1;
    min-width: 110px;
    accent-color: #2b6cb0;
  }
  .totals {
    display: flex;
    align-items: baseline;
    gap: 0.9rem;
  }
  .stat {
    font-size: 1.05rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
  }
  .stat .k {
    font-size: 0.72rem;
    font-weight: 600;
    color: #8a93a0;
    margin-right: 0.15rem;
  }
  .stat.r2 {
    color: #2b6cb0;
  }
  .stat.q2 {
    color: #2f855a;
  }
  .actions {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    flex-wrap: wrap;
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
    margin: 0;
    flex: 1 1 100%;
    font-size: 0.8rem;
    color: #555;
    line-height: 1.4;
  }
  .gain .next {
    color: #888;
  }
</style>
