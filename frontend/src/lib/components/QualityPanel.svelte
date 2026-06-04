<script lang="ts">
  import type { QualityReport } from '$lib/api';

  interface Props {
    report: QualityReport | null;
  }
  let { report }: Props = $props();

  const flaggedColumns = $derived(
    report ? report.columns.filter((c) => c.n_invalid > 0 || c.exceeds_tolerance) : []
  );
</script>

<div class="quality" data-testid="quality">
  {#if report}
    <div class="summary">
      <span class:bad={!report.primary_id_unique}>
        Primary id {report.primary_id_unique ? 'unique' : 'NOT unique'}
      </span>
      <span class:bad={report.n_missing_cells > 0}>
        {report.n_missing_cells} missing cells ({report.pct_missing.toFixed(1)}%)
      </span>
      <span class:bad={flaggedColumns.length > 0}>{flaggedColumns.length} flagged columns</span>
    </div>

    {#if report.duplicate_primary_ids.length}
      <p class="issue">
        Duplicate identifiers:
        {report.duplicate_primary_ids.map((d) => `${d.value} (rows ${d.rows.join(', ')})`).join('; ')}
      </p>
    {/if}

    {#if flaggedColumns.length}
      <table>
        <thead>
          <tr><th>Column</th><th>Missing</th><th>Invalid</th></tr>
        </thead>
        <tbody>
          {#each flaggedColumns as c (c.name)}
            <tr>
              <td>{c.name}</td>
              <td>{c.n_missing} ({c.pct_missing.toFixed(1)}%)</td>
              <td class:bad={c.n_invalid > 0}>{c.n_invalid}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {:else}
      <p class="ok">No invalid values or columns over tolerance.</p>
    {/if}
  {/if}
</div>

<style>
  .quality {
    font-size: 0.82rem;
  }
  .summary {
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
    margin-bottom: 0.4rem;
  }
  .summary span {
    padding: 2px 8px;
    border-radius: 10px;
    background: #eef6ef;
    color: #237a3a;
  }
  .summary span.bad {
    background: #fdecea;
    color: #b3261e;
  }
  table {
    border-collapse: collapse;
    width: 100%;
  }
  th,
  td {
    text-align: left;
    padding: 2px 8px;
    border-bottom: 1px solid #eee;
  }
  td.bad {
    color: #b3261e;
    font-weight: 600;
  }
  .issue {
    color: #b3261e;
  }
  .ok {
    color: #237a3a;
  }
</style>
