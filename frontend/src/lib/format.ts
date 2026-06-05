// Shared display formatting helpers, so dates and similar values render the
// same way everywhere.

/** Format an ISO timestamp as e.g. "05 June 2026 07:36:30" (day month-name year,
 * 24-hour time). Falls back to the raw string if it is not a valid date. */
export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const day = String(d.getDate()).padStart(2, '0');
  const month = d.toLocaleString('en-GB', { month: 'long' });
  const time = d.toLocaleTimeString('en-GB', { hour12: false });
  return `${day} ${month} ${d.getFullYear()} ${time}`;
}
