# Ideas extracted from the 2009 design notebooks

Three scanned notebooks (2 June 2009, July 2009, and 11–18 September 2009)
contain the design for an earlier workflow-based chemometrics tool: data
tables organised as blocks × stacks (train / test / check), transformation
chains, lazily-copied workflow DAGs, triggers/alarms, multiblock models, and a
worked treatment of latent-variable model inversion for product design. This
document records what in those notes is superseded by ScorePilot's current
architecture and what is worth building on.

## What the notes describe (condensed)

### June 2009 notebook

- **Model inversion for new product/process design** (after Jaeckle &
  MacGregor, AIChE J 1998, v44) — nine pages of worked math. Direct OLS
  inversion of `Y = XB` fails (collinearity, more variables than runs), so:
  build PCA/PCR on X, regress quality variables Y onto the scores
  (`B = (TᵀT)⁻¹TᵀY`), then invert a desired spec `y_des → t_des → x_new =
  P_A t_des` — an "on-the-model-plane" inversion with SPE = 0. Three cases by
  the count of quality specs K vs components A: K > A (least squares),
  K = A (direct), K < A (generalised inverse; a **null space** of equivalent
  solutions — move along it to enumerate candidate operating conditions that
  all predict the same Y). Validity checks throughout: `t_des` inside the T²
  limit; and a **Phase A feasibility pre-check** — PCA on the Y-space of
  previous runs, requiring `y_des` to show low T² and low SPE there ("have we
  made something like this before?") before attempting inversion.
- **v1 release checklist / course outlines**: preprocessing including MSC,
  SNV, smoothing, trimming, winsorising; robust PCA; EDA aids (scatter-plot
  matrix, correlation map, sparklines, colour-coded score plots); SIMCA /
  PLS-DA; multiblock; "Tools: Inversion, Contributions, Optimization";
  adaptive model update / model maintenance; data import (Excel/CSV/XML,
  OPC/PI connectivity).
- Website/app-store/business planning (not relevant here).

### July and September 2009 notebooks

- **DT data model**: a data table = blocks (X, Y, Z…) × stacks (train /
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
   set on each variant, recorded in the Logbook. This is the strongest
   workflow idea in the notes and directly serves the Logbook's "validation
   history" promise.

2. **Named test sets + a predict endpoint** (the train/test/check "stacks").
   ScorePilot currently has no out-of-sample mechanism — only
   cross-validation during fitting. Supporting one or more named validation
   datasets per model, with results logged per variant, is the largest
   functional gap the notes point at, and item 1 falls out of the same core
   function.

3. **Model inversion for product/process design** (June notebook). Given a
   desired quality spec `y_des`, invert a fitted PLS/PCR model to propose
   operating conditions `x_new`, with the Phase A feasibility pre-check
   (`y_des` must show low T²/SPE in a Y-space PCA of past products) and
   null-space exploration when specs are fewer than components. A
   distinctive, high-value analysis tool that builds directly on the
   projection function from items 1–2. The numerics belong upstream in
   `process_improve` per the CLAUDE.md rule.

4. **The tools-vs-transformations invariant**: "transformations never alter
   shape; tools may (lag, batch feature extraction, DOE)." A clean design
   rule for evolving `PreprocessingSpec`: current operations are all
   shape-preserving; shape-changing steps (lagged variables for dynamic PLS,
   batch unfolding) should be a distinct, explicitly ordered stage.

5. **Preprocessing breadth from the v1 checklist**: MSC and SNV (spectral
   data), smoothing, trimming, winsorising. Natural `VariableTransform` /
   spec extensions once spectral datasets matter; robust PCA sits behind the
   same door as a model-kind option.

6. **Monitoring triggers/notifiers**: condition functions with nested AND/OR
   over model outputs (`model.output['T2'][-1] > limit → notify`). Out of
   scope for the core analysis loop, but a coherent future "monitoring mode"
   that maps directly onto the T²/SPE limits already computed.

7. **Adaptive model update / model maintenance** (June notebook). Refitting
   an existing model on newly accumulated data is already expressible as "new
   dataset + same `PreprocessingSpec` → child variant"; the missing piece is
   a one-step "refresh this model on dataset D" action that preserves lineage
   in the Hangar.

8. **Model-kind roadmap**: MB-PCA / MB-PLS, SIMCA / PLS-DA, L-shaped data,
   missing-data-tolerant fitting (today missing cells are only flagged in the
   quality report). Per CLAUDE.md, the numerics belong upstream in
   `process_improve`, not bespoke in `core/`.

9. **Small UX wins**: variable-range selection by name pattern
   (`Var001-099`), `<odd>`/`<even>` row splits (venetian-blind style test
   sets), and EDA aids from the course notes — scatter-plot matrix,
   correlation map, sparklines — all natural additions to the linked-plots
   library.

## Design note worth recording

July 6 entry: "easier to track *included* rather than excluded, because
future data sets are arbitrarily sourced." ScorePilot already implements the
right split: `x_columns` / `y_columns` are allow-lists (the model's contract
with any future data), while row exclusions are deny-lists (provenance: what
was removed and why). Keep it that way.
