<script lang="ts">
  import { page } from '$app/stores';
  import Explorer from '$lib/components/Explorer.svelte';

  const datasetId = $derived($page.params.id ?? '');
</script>

<main>
  <p class="nav"><a href="/">← Datasets</a></p>
  {#key datasetId}
    {#if datasetId}<Explorer {datasetId} />{/if}
  {/key}
</main>

<style>
  :global(body) {
    margin: 0;
    font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
    color: #1c1c1c;
    background: #fafafa;
  }
  main {
    max-width: 96rem;
    margin: 1rem auto;
    padding: 0 1.25rem;
  }
  .nav {
    margin: 0 0 0.5rem;
    font-size: 0.85rem;
  }
</style>
