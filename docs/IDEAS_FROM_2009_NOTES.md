# Ideas extracted from the 2009 design notebooks

Two scanned notebooks (July 2009 and 11–18 September 2009) contain the design
for an earlier workflow-based chemometrics tool: data tables organised as
blocks × stacks (train / test / check), transformation chains, lazily-copied
workflow DAGs, triggers/alarms, and multiblock models. This document records
what in those notes is superseded by ScorePilot's current architecture and
what is worth building on.

## What the notes describe (condensed)

- **Data-table (DT) model**: a table = blocks (X, Y, Z…) × stacks (train /
  test / check) × arrays; a `split()` operation with rule dicts and wildcards
  (`<rest>`, `<odd>`, `<even>`); variable-label range parsing (`Var001-099`).
- **Workflow DAG**: data → t₀…tₙ → model → plot nodes, where t₀ is always an
  include/exclude filter; the rule "transformations never alter shape; tools
  may (lags, batch features, DOE)"; coroutine/generator push execution over a
  hand-rolled digraph.
- **Copy semantics**: many pages on cheap workflow copies — lazy/deferred deep
  copy, copy-on-change, weakrefs, traits notification — so that
  `wf2 = wf1.copy()` duplicates no data until something changes.
- **Excluded data**: stored, never discarded, in specially named stacks
  (`excluded_0`, `Validation_0`); "move to validation rather than exclude";
  excluded rows re-offered as validation sets; track *included* rather than
  excluded; missing-data masks distinguishing missing vs manually excluded vs
  previously excluded.
- **Triggers / timers / notifiers**: condition functions over model outputs
  (e.g. `T² > 99 % limit AND grade == 4279-A → alarm/email`), nested dict
  AND/OR conditions, file-change notification.
- **Model kinds**: MB-PCA, MB-PLS, SIMCA, PLS-DA, L-shaped data; the rule
  "all models handle missing data".

## Superseded — do not reintroduce

The copy-semantics machinery (lazy deepcopy, traits, weakrefs), the custom
digraph, the coroutine pipeline engine, masked-array exclusion bookkeeping,
and the storage layer notes. ScorePilot's **immutable dataset + per-variant
`PreprocessingSpec` + `parent_id` lineage** solves the same problem — cheap
variants, zero data duplication, rebuildable models — far more simply: a
variant *is* a recipe diff, so there is nothing to lazily copy. The 2009
design needed extensive mechanism that `apply_spec(df, spec)` makes
unnecessary. The notes are a useful validation of the current architecture,
not a source of mechanism.

## Worth building on (ranked)

1. **Excluded samples become evidence, not waste.** The notes store excluded
   rows in named stacks (`Validation_0`) and use "move to validation" rather
   than plain exclusion. Today `excluded_rows` simply vanish from a fit;
   there is no way to score them against the resulting model. Add a core
   "apply model to data" function (project rows → scores, T², SPE,
   predictions) and surface excluded rows as an automatic pseudo-validation
   set on each variant, recorded in the Logbook. This is the strongest idea
   in the notes and directly serves the Logbook's "validation history"
   promise.

2. **Named test sets + a predict endpoint** (the train/test/check "stacks").
   ScorePilot currently has no out-of-sample mechanism — only
   cross-validation during fitting. Supporting one or more named validation
   datasets per model, with results logged per variant, is the largest
   functional gap the notes point at, and item 1 falls out of the same core
   function.

3. **The tools-vs-transformations invariant**: "transformations never alter
   shape; tools may (lag, batch feature extraction, DOE)." A clean design
   rule for evolving `PreprocessingSpec`: current operations are all
   shape-preserving; shape-changing steps (lagged variables for dynamic PLS,
   batch unfolding) should be a distinct, explicitly ordered stage.

4. **Monitoring triggers/notifiers**: condition functions with nested AND/OR
   over model outputs (`model.output['T2'][-1] > limit → notify`). Out of
   scope for the core analysis loop, but a coherent future "monitoring mode"
   that maps directly onto the T²/SPE limits already computed.

5. **Model-kind roadmap**: MB-PCA / MB-PLS, SIMCA / PLS-DA, L-shaped data,
   missing-data-tolerant fitting (today missing cells are only flagged in the
   quality report). Per CLAUDE.md, the numerics belong upstream in
   `process_improve`, not bespoke in `core/`.

6. **Small UX wins**: variable-range selection by name pattern
   (`Var001-099`), and `<odd>`/`<even>` row splits (venetian-blind style test
   sets) in the grid / variant-creation flow.

## Design note worth recording

July 6 entry: "easier to track *included* rather than excluded, because
future data sets are arbitrarily sourced." ScorePilot already implements the
right split: `x_columns` / `y_columns` are allow-lists (the model's contract
with any future data), while row exclusions are deny-lists (provenance: what
was removed and why). Keep it that way.
