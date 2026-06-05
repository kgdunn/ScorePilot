// A tiny global toast store. Errors are surfaced as dismissible toasts pinned to
// the viewport so they stay visible regardless of scroll position. Toasts auto
// dismiss after `durationMs` (at least 5 seconds) but can also be closed manually.

export type ToastKind = 'error' | 'info';

export interface Toast {
  id: number;
  message: string;
  kind: ToastKind;
}

const MIN_DURATION_MS = 5000;

let toasts = $state<Toast[]>([]);
let nextId = 0;

/** Reactive accessor for the current toasts (read inside markup to track it). */
export function getToasts(): Toast[] {
  return toasts;
}

export function dismissToast(id: number): void {
  toasts = toasts.filter((t) => t.id !== id);
}

export function pushToast(message: string, kind: ToastKind = 'error', durationMs = 6000): number {
  const id = nextId++;
  toasts = [...toasts, { id, message, kind }];
  const ttl = Math.max(durationMs, MIN_DURATION_MS);
  if (ttl > 0 && typeof setTimeout !== 'undefined') {
    setTimeout(() => dismissToast(id), ttl);
  }
  return id;
}

/** Convenience for the common case: surface an error message. */
export function showError(message: string): number {
  return pushToast(message, 'error');
}
