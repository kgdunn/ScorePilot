<script lang="ts">
  import type { CrossValidation, CvScheme, SelectionRule } from '$lib/api';

  interface Props {
    /** Current component count; changing it applies live (no Apply button). */
    components: number;
    min?: number;
    max: number;
    recommended: number | null;
    cv: CrossValidation | null;
    /** "PCA" or "PLS" - decides which selection rules / schemes are offered. */
    kind: string;
    /** Selected component-selection rule; changing it re-runs cross-validation. */
    selectionRule: SelectionRule;
    /** PCA cross-validation scheme; ignored for PLS. */
    cvScheme: CvScheme;
    /** A live auto-save of the new count is in flight. */
    saving?: boolean;
  }
  let {
    components = $bindable(),
    min = 1,
    max,
    recommended,
    cv,
    kind,
    selectionRule = $bindable(),
    cvScheme = $bindable(),
    saving = false
  }: Props = $props();

  // Rules each kind supports (PCA has no randomization test), with display labels.
  const RULE_LABELS: Record<SelectionRule, string> = {
    '1se': '1-SE (parsimonious)',
    min: 'Lowest CV error',
    q2_increment: 'Q² increment',
    randomization: 'Randomization test'
  };
  const rules = $derived<SelectionRule[]>(
    kind === 'PLS' ? ['1se', 'min', 'q2_increment', 'randomization'] : ['min', '1se', 'q2_increment']
  );
  const SCHEME_LABELS: Record<CvScheme, string> = {
    ekf: 'Element-wise (ekf)',
    row_wise: 'Row-wise (legacy)'
  };
  // The PLS recommendation can flag whether it was stable across CV repeats.
  const unstable = $derived(cv?.recommended_is_stable === false);

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

<div class="explorer" data-testid="component-explorer">
  <div class="count">
    <span class="label">Components</span>
    <div class="stepper">
      <button type="button" aria-label="Remove a component" disabled={components <= min} onclick={() => step(-1)}>−</button>
      <span class="value" data-testid="component-count" class:busy={saving}>{components}</span>
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
        title={unstable
          ? 'Cross-validation suggests this many components, but the choice varied across CV repeats'
          : 'Cross-validation suggests this many components'}
        onclick={() => (components = clamp(recommended))}
      >
        ✨ Recommended: {recommended}{#if unstable}<span class="warn" title="Unstable across CV repeats">⚠</span>{/if}
      </button>
    {/if}
    <label class="rule" title="How the recommended component count is chosen">
      <span class="k">Rule</span>
      <select bind:value={selectionRule} aria-label="Selection rule">
        {#each rules as r (r)}
          <option value={r}>{RULE_LABELS[r]}</option>
        {/each}
      </select>
    </label>
    {#if kind === 'PCA'}
      <label class="rule" title="PCA cross-validation scheme">
        <span class="k">CV</span>
        <select bind:value={cvScheme} aria-label="Cross-validation scheme">
          {#each Object.keys(SCHEME_LABELS) as s (s)}
            <option value={s}>{SCHEME_LABELS[s as CvScheme]}</option>
          {/each}
        </select>
      </label>
    {/if}
    <span class="saving" class:show={saving}>saving…</span>
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
  .rec .warn {
    margin-left: 0.3rem;
    color: #c05621;
  }
  .rule {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.8rem;
    color: #2b4a66;
  }
  .rule .k {
    font-size: 0.72rem;
    font-weight: 600;
    color: #8a93a0;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .rule select {
    border: 1px solid #cdd7e1;
    border-radius: 6px;
    padding: 0.25rem 0.4rem;
    font-size: 0.8rem;
    background: #fff;
    color: #2b4a66;
    cursor: pointer;
  }
  .saving {
    font-size: 0.78rem;
    color: #999;
    opacity: 0;
    transition: opacity 0.15s;
  }
  .saving.show {
    opacity: 1;
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
