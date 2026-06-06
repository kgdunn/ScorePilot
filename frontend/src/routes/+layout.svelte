<script lang="ts">
  import Toaster from '$lib/components/Toaster.svelte';
  import { getVersion } from '$lib/api';

  let { children } = $props();

  // Surface the running backend version (top-right, faint) so you can always
  // confirm which deploy you are looking at.
  let version = $state<string | null>(null);
  $effect(() => {
    void getVersion()
      .then((v) => (version = v))
      .catch(() => {});
  });
</script>

{@render children()}

{#if version}
  <span class="app-version" title="ScorePilot version">v{version}</span>
{/if}

<Toaster />

<style>
  .app-version {
    position: fixed;
    top: 4px;
    right: 8px;
    /* Below modals (z-index 50+) so it never paints over a dialog. */
    z-index: 40;
    font-size: 0.72rem;
    line-height: 1;
    color: #bcbcbc;
    font-variant-numeric: tabular-nums;
    font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
    /* Purely informational: never intercept clicks. */
    pointer-events: none;
    user-select: text;
  }
</style>
