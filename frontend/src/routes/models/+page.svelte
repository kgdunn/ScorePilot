<script lang="ts">
  import { listModels, type ModelSummary } from '$lib/api';

  let models = $state<ModelSummary[]>([]);
  let error = $state<string | null>(null);

  $effect(() => {
    void (async () => {
      try {
        models = await listModels();
        error = null;
      } catch (e) {
        error = (e as Error).message;
      }
    })();
  });

  const byId = $derived.by(() => {
    const map = new Map<number, ModelSummary>();
    models.forEach((m) => map.set(m.id, m));
    return map;
  });

  function depth(model: ModelSummary): number {
    let d = 0;
    let current: ModelSummary | undefined = model;
    while (current && current.parent_id != null) {
      current = byId.get(current.parent_id);
      d += 1;
      if (d > 50) break;
    }
    return d;
  }
</script>

<main>
  <p class="nav"><a href="/">← Home</a></p>
  <h1>Hangar</h1>
  <p class="tagline">All model variants you have built.</p>

  {#if error}<p class="error">{error}</p>{/if}

  {#if models.length === 0}
    <p class="hint">No models yet. Open a dataset and fit one.</p>
  {:else}
    <ul class="models">
      {#each models as m (m.id)}
        <li style="margin-left:{depth(m) * 1.5}rem">
          <a href={`/models/${m.id}`}>
            <span class="kind {m.kind.toLowerCase()}">{m.kind}</span>
            <strong>{m.name ?? `Model ${m.id}`}</strong>
          </a>
          <span class="meta">
            {m.n_components} comp{m.parent_id != null ? ` · variant of #${m.parent_id}` : ''}
          </span>
        </li>
      {/each}
    </ul>
  {/if}
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
    margin: 1.5rem auto;
    padding: 0 1.5rem;
  }
  .nav {
    font-size: 0.85rem;
  }
  .tagline {
    margin-top: 0;
    color: #666;
  }
  ul.models {
    list-style: none;
    padding: 0;
  }
  li {
    padding: 0.35rem 0;
    border-bottom: 1px solid #eee;
  }
  .kind {
    display: inline-block;
    padding: 1px 7px;
    border-radius: 10px;
    color: #fff;
    font-size: 0.72rem;
    margin-right: 0.4rem;
  }
  .kind.pca {
    background: #2b6cb0;
  }
  .kind.pls {
    background: #2f855a;
  }
  .meta {
    color: #888;
    font-size: 0.82rem;
    margin-left: 0.5rem;
  }
  .hint {
    color: #777;
  }
  .error {
    color: #b3261e;
  }
</style>
