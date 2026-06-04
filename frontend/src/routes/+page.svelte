<script lang="ts">
  import { goto } from '$app/navigation';
  import { listDatasets, uploadDataset, type DatasetDetail } from '$lib/api';

  let datasets = $state<DatasetDetail[]>([]);
  let busy = $state(false);
  let error = $state<string | null>(null);

  async function refresh() {
    try {
      datasets = await listDatasets();
    } catch (e) {
      error = (e as Error).message;
    }
  }

  $effect(() => {
    void refresh();
  });

  async function onFile(event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    busy = true;
    error = null;
    try {
      const dataset = await uploadDataset(file);
      await goto(`/datasets/${dataset.dataset_id}`);
    } catch (e) {
      error = (e as Error).message;
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
    {#if busy}<span class="hint">Uploading…</span>{/if}
    {#if error}<p class="error">{error}</p>{/if}
  </section>

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
  .error {
    color: #b3261e;
    font-weight: 600;
  }
  .foot {
    margin-top: 1.5rem;
    font-size: 0.85rem;
  }
</style>
