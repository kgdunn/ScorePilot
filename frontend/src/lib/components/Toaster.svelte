<script lang="ts">
  import { getToasts, dismissToast } from '$lib/toast.svelte';
</script>

<div class="toaster" aria-live="assertive" aria-atomic="false">
  {#each getToasts() as t (t.id)}
    <div class="toast {t.kind}" role="alert" data-testid="toast">
      <span class="msg">{t.message}</span>
      <button class="close" aria-label="Dismiss" onclick={() => dismissToast(t.id)}>×</button>
    </div>
  {/each}
</div>

<style>
  .toaster {
    position: fixed;
    top: 0.75rem;
    left: 50%;
    transform: translateX(-50%);
    z-index: 1000;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    width: min(40rem, calc(100% - 1.5rem));
    pointer-events: none;
  }
  .toast {
    pointer-events: auto;
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    padding: 0.6rem 0.75rem;
    border-radius: 8px;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.18);
    font-size: 0.88rem;
    line-height: 1.3;
  }
  .toast.error {
    background: #fdecea;
    border: 1px solid #f5c2c0;
    color: #b3261e;
  }
  .toast.info {
    background: #e8f0fe;
    border: 1px solid #c2d6f5;
    color: #1a4480;
  }
  .msg {
    flex: 1;
    word-break: break-word;
  }
  .close {
    flex: none;
    border: none;
    background: transparent;
    color: inherit;
    font-size: 1.1rem;
    line-height: 1;
    cursor: pointer;
    padding: 0 0.15rem;
    opacity: 0.7;
  }
  .close:hover {
    opacity: 1;
  }
</style>
