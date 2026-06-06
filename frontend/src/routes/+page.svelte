<script lang="ts">
  import { goto } from '$app/navigation';
  import {
    listDatasets,
    listSamples,
    loadSample,
    openDatasetFromUrl,
    uploadDataset,
    type DatasetDetail,
    type SampleInfo
  } from '$lib/api';
  import { showError } from '$lib/toast.svelte';

  let datasets = $state<DatasetDetail[]>([]);
  let samples = $state<SampleInfo[]>([]);
  let busy = $state(false);
  let url = $state('');

  async function refresh() {
    // Load independently: a failure listing the user's datasets must not also
    // hide the bundled demo datasets (and vice versa).
    void listDatasets()
      .then((d) => (datasets = d))
      .catch((e) => showError((e as Error).message));
    void listSamples()
      .then((s) => (samples = s))
      .catch((e) => showError((e as Error).message));
  }

  $effect(() => {
    void refresh();
  });

  async function onLoadSample(name: string) {
    busy = true;
    try {
      const dataset = await loadSample(name);
      await goto(`/datasets/${dataset.dataset_id}`);
    } catch (e) {
      showError((e as Error).message);
    } finally {
      busy = false;
    }
  }

  async function onFile(event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    busy = true;
    try {
      const dataset = await uploadDataset(file);
      await goto(`/datasets/${dataset.dataset_id}`);
    } catch (e) {
      showError((e as Error).message);
    } finally {
      busy = false;
    }
  }

  async function onOpenUrl() {
    if (!url.trim()) return;
    busy = true;
    try {
      const dataset = await openDatasetFromUrl(url.trim());
      await goto(`/datasets/${dataset.dataset_id}`);
    } catch (e) {
      showError((e as Error).message);
    } finally {
      busy = false;
    }
  }
</script>

<main>
  <h1>ScorePilot</h1>
  <p class="tagline">PCA / PLS model analysis for chemometrics.</p>

  <section class="panel">
    <h2>Open a dataset</h2>
    <p class="hint">Import a CSV or Excel file to explore it.</p>
    <input
      type="file"
      data-testid="file-input"
      accept=".csv,.xlsx,.xls"
      onchange={onFile}
      disabled={busy}
    />
    <p class="hint or">or open from a URL (max 5 MB):</p>
    <form class="url-row" onsubmit={(e) => { e.preventDefault(); void onOpenUrl(); }}>
      <input
        type="url"
        data-testid="url-input"
        placeholder="https://example.com/data.csv"
        bind:value={url}
        disabled={busy}
      />
      <button type="submit" disabled={busy || !url.trim()}>Open</button>
    </form>
    {#if busy}<span class="hint">Loading…</span>{/if}
  </section>

  {#if samples.length}
    <section class="panel">
      <h2>Try a sample dataset</h2>
      <ul class="samples">
        {#each samples as s (s.name)}
          <li>
            <button data-testid={`sample-${s.name}`} onclick={() => onLoadSample(s.name)} disabled={busy}>
              Load
            </button>
            <strong>{s.title}</strong>
            <span class="meta">{s.description}</span>
            <a class="src" href={s.source_url} target="_blank" rel="noreferrer">source ↗</a>
          </li>
        {/each}
      </ul>
    </section>
  {/if}

  <section class="panel">
    <h2>Datasets</h2>
    {#if datasets.length === 0}
      <p class="hint">No datasets yet.</p>
    {:else}
      <ul>
        {#each datasets as d (d.dataset_id)}
          <li>
            <a href={`/datasets/${d.dataset_id}`}>{d.name}</a>
            <span class="meta">{d.n_rows} × {d.n_columns}</span>
          </li>
        {/each}
      </ul>
    {/if}
  </section>

  <p class="foot"><a href="/models">Hangar (models) →</a> &nbsp;·&nbsp; <a href="/playground">PCA scores playground →</a></p>
</main>

<style>
  :global(body) {
    margin: 0;
    font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
    color: #1c1c1c;
    background: #fafafa;
  }
  main {
    max-width: 60rem;
    margin: 2rem auto;
    padding: 0 1.5rem;
  }
  h1 {
    margin-bottom: 0.1rem;
  }
  .tagline {
    margin-top: 0;
    color: #666;
  }
  .panel {
    background: #fff;
    border: 1px solid #e6e6e6;
    border-radius: 10px;
    padding: 1rem 1.25rem;
    margin: 1rem 0;
  }
  .panel h2 {
    margin-top: 0;
    font-size: 1.05rem;
  }
  .or {
    margin-bottom: 0.35rem;
  }
  .url-row {
    display: flex;
    gap: 0.5rem;
    max-width: 32rem;
  }
  .url-row input {
    flex: 1;
    padding: 0.35rem 0.5rem;
  }
  .url-row button {
    padding: 0.35rem 0.8rem;
  }
  ul {
    margin: 0;
    padding-left: 1rem;
  }
  li {
    margin: 0.25rem 0;
  }
  .meta {
    color: #888;
    font-size: 0.85rem;
    margin-left: 0.5rem;
  }
  .hint {
    color: #777;
    font-size: 0.9rem;
  }
  .foot {
    margin-top: 1.5rem;
    font-size: 0.85rem;
  }
  ul.samples {
    list-style: none;
    padding: 0;
  }
  ul.samples li {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    flex-wrap: wrap;
    padding: 0.35rem 0;
    border-bottom: 1px solid #f0f0f0;
  }
  ul.samples button {
    padding: 0.25rem 0.7rem;
    border: 1px solid #2b6cb0;
    background: #2b6cb0;
    color: #fff;
    border-radius: 6px;
    cursor: pointer;
  }
  ul.samples button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .src {
    font-size: 0.8rem;
  }
</style>
