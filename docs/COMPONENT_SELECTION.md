# Component selection (cross-validation)

How ScorePilot decides, and lets the user decide, how many components a PCA or
PLS model should keep. This is the feature delivered on the
`claude/scorepilot-cv-criterion-lDKvV` branch (PRs #84 and the Phase 2 follow-up).

## Background: the bug this fixed

ScorePilot was pinned to `process-improve==1.27.1`. That release's component
selector used Wold's PRESS-ratio (PCA) and the lowest RMSECV / argmin (PLS), both
of which routinely ran the recommendation up to (or near) the **maximum**
component count. Users saw "every cross-validation goes to the maximum".

The fix landed upstream in `process-improve` (>= 1.28, refined through 1.38) and
is now the published default:

- **PCA** cross-validates with **element-wise k-fold (ekf)** (Bro et al. 2008),
  which does not let a held-out row leak back into its own prediction. The legacy
  whole-row scheme (`row_wise`) is the one that shrank PRESS monotonically and
  over-selected; it is still available but `process-improve` emits a
  `SpecificationWarning` when you ask for it.
- **PLS** uses the **one-standard-error rule** on **repeated, shuffled K-fold**,
  scaling **inside each fold**.

ScorePilot now depends on `process-improve>=1.38,<2` and adopts this directly.

## Architecture

All of the chemometrics math lives in `process_improve`; ScorePilot never
reimplements cross-validation, PRESS, Q², or the selection rules. The only local
code is a thin adapter:

`core/cross_validation.py` -> `cross_validate(x_block, y_block, kind, ...)`

It calls `PCA.select_n_components` / `PLS.select_n_components`, then adapts their
`Bunch` output into one serialization-friendly `CrossValidation` dataclass:

| field | meaning |
| --- | --- |
| `r2` / `q2` | cumulative calibration R² and cross-validated R² (Q²) per component |
| `q2_se` | half-width of the ±1 SE band around the Q² curve (from the selector's `q2_se`) |
| `r2_per_component` / `q2_per_component` | marginal (per-component) gains |
| `selection_rule` | rule used to pick `recommended` |
| `cv_scheme` | PCA scheme (`ekf` / `row_wise`); `null` for PLS |
| `n_splits` / `n_repeats` | fold count and repeat count actually used |
| `recommended` | component count the selector recommends |
| `recommended_is_stable` | PLS: did the modal choice clear the stability threshold? (`null` for PCA) |
| `recommended_vote_share` | PLS: fraction of repeats that voted for `recommended` (`null` for PCA) |

For PCA the target of R²/Q² is the X block; for PLS it is the Y block (the
`"total"` column of the selector's `r2y_validated`).

### Selection rules

Passed straight through to `process-improve` (which validates them):

| rule | PCA | PLS | meaning |
| --- | :-: | :-: | --- |
| `min` | default | yes | lowest cross-validated error |
| `1se` | yes | default | one-standard-error / most parsimonious within 1 SE |
| `q2_increment` | yes | yes | stop when the marginal Q² gain drops below `min_q2_increase` |
| `randomization` | - | yes | Van der Voet randomization test |

`randomization` is **PLS only**; requesting it for PCA returns a 422.

## API

`GET /api/models/{id}/cross-validation` accepts query params
`max_components`, `selection_rule`, `cv_scheme`, `n_repeats`, `min_q2_increase`
and returns the `CrossValidationModel` (the fields above). `POST /api/models`
(`FitModelRequest`) accepts the same controls for `auto_components` fitting:
cross-validation picks the count freely up to the UI ceiling.

Errors map to **422** with a clean message: an unsupported rule for the kind, a
PLS request with no Y columns, a block with no variance, or rank-deficient /
collinear folds (the `numpy.linalg.LinAlgError` from the PLS weight inversion is
caught and surfaced rather than escaping as a 500).

## Frontend

`ComponentExplorer.svelte` (the sticky control above the diagnostics) exposes:

- a **rule** dropdown (the rules valid for the model kind),
- for PCA, a **cv_scheme** dropdown (`ekf` / `row_wise`),
- the recommendation button, flagged **unstable** (⚠) when PLS reports the choice
  varied across repeats.

Changing the rule or scheme re-runs cross-validation server-side (the model page
keeps the controls in state and refetches). The R²/Q² card draws the two curves
with a **shaded ±1 SE band** around the Q² line and a caption naming the rule and,
for PLS, the vote share / stability.

The band is a generic capability added to the reusable plot library
(`lib/plots`): `LineSeries.band?` renders a shaded ±band via the canonical
stacked-area ECharts pair, so it stays free of ScorePilot concepts.

## Where `q2_se` comes from

`process-improve` plots / reports the cross-validated error on the **PRESS /
RMSECV** scale, but it also exposes a per-component **`q2_se`** (>= 1.39) - the
standard error already mapped onto the **Q²** scale (the half-width of a ±1 SE
band around the validated Q² curve). ScorePilot reads that field directly
(`core/cross_validation.py::_q2_se_list`); there is no local Q²-SE statistics
code. This was originally a flagged local adapter here; it was upstreamed in
`process-improve` PR #410 and the adapter was deleted.

## Open items / TODO

- [ ] **Surface the randomization p-values** (`randomization_pvalues`) in the UI
      when the PLS `randomization` rule is selected - the adapter currently drops
      them; they would make a useful per-component significance annotation.
- [ ] **Show the full vote distribution** (`selection_distribution`), not just the
      modal vote share, e.g. as a small bar under the recommendation so an
      unstable choice shows *where* the alternatives landed.
- [ ] **Persist the chosen rule / scheme per variant.** Today the controls reset
      to the per-kind defaults on every model load; they are not stored on the
      `Model`. If we want a variant to remember "this model was chosen with
      `q2_increment`", that needs a column / preprocessing field.
- [ ] **Performance:** PLS defaults to `n_repeats=10`, so the endpoint refits
      `10 · n_splits` models per rule change. Fine for the current dataset sizes;
      revisit (caching by `(model, rule, scheme, ceiling)`, or a lower default for
      large blocks) if it gets sluggish.
- [ ] **Multi-Y PLS Q²:** only the aggregate (`"total"`) Q²Y curve is shown. A
      per-response Q²Y breakdown (the selector already returns per-column columns)
      could be offered for multi-target models.
- [ ] **The ±1 SE band is symmetric** on the Q² scale (the PRESS SE is symmetric).
      If a future upstream Q² SE is asymmetric, revisit the band rendering.
