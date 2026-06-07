// A Svelte action that replays a short, attention-drawing animation on an
// element whenever a tracked value changes. Used to give the component explorer
// tactile feedback: the model is recomputed live, often instantly on small
// datasets, so without an explicit cue a click can look like it did nothing.
//
// Uses the Web Animations API rather than CSS classes so the animation replays
// reliably on every change (no reflow juggling) and so there is nothing for
// Svelte's scoped-CSS pruner to strip. Degrades to a no-op where `animate` is
// unavailable (e.g. jsdom in unit tests).

export type PulseKind = 'bg' | 'pop';

export interface PulseParam {
  /** Replays the animation whenever this value changes. */
  key: unknown;
  /** 'pop' scales the element briefly; 'bg' flashes its background. */
  kind?: PulseKind;
  /** Flash colour for the 'bg' kind. */
  color?: string;
}

const DEACTIVATED = (v: unknown): boolean => v === null || v === undefined || v === false;

function play(node: HTMLElement, p: PulseParam): void {
  if (typeof node.animate !== 'function') return;
  if (p.kind === 'pop') {
    node.animate(
      [{ transform: 'scale(1)' }, { transform: 'scale(1.28)' }, { transform: 'scale(1)' }],
      { duration: 260, easing: 'cubic-bezier(0.22, 1, 0.36, 1)' }
    );
  } else {
    node.animate(
      [{ backgroundColor: p.color ?? 'rgba(43, 108, 176, 0.22)' }, { backgroundColor: 'transparent' }],
      { duration: 650, easing: 'ease-out' }
    );
  }
}

export function pulse(node: HTMLElement, param: PulseParam) {
  let prev = param.key;
  return {
    update(p: PulseParam) {
      if (p.key === prev) return;
      const enteringDeactivated = DEACTIVATED(p.key);
      prev = p.key;
      // Skip transitions *into* a deactivated state (e.g. a table row losing the
      // "current" marker) so only the newly-active element flashes.
      if (enteringDeactivated) return;
      play(node, p);
    }
  };
}
