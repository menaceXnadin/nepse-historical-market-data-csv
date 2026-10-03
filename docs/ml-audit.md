# ML Pipeline Audit (`ml/`)

Audit of the LSTM/XGBoost training code. Companion to
[`pipeline-audit.md`](pipeline-audit.md), which covers data ingestion.

**Method:** every source file read in full, all 47 notebook cells traced, and
numeric claims checked against the saved artifacts and the raw CSVs. The
headline defect below was reproduced empirically, not just by reading.

## Verdict

The fundamentals are mostly right: the split is **chronological**, the scaler and
feature selector are fit on **train only**, the label shift points the correct
way, and every technical indicator is causal. The two classic catastrophic leaks
are **absent**.

But there are four real leaks, and one code bug that makes
`ml/results/model_comparison.csv` **uninterpretable**. That file should not be
quoted until the off-by-one is fixed.

---

## 🔴 1. The LSTM sequence is off by one — `model_comparison.csv` is invalid

`ml/models/lstm_model.py:119-120`:

```python
x_seq = self.X[i - self.seq_length: i].clone()   # rows [i-60 .. i-1]  — i EXCLUDED
y_val = self.y[i]                                # label from close[i], close[i+1]
```

The label at row `i` is `close[i+1] > close[i]` (`preprocessor.py:223-224`), which
is defined in terms of `close[i]` — **but row `i` is not in the input window.** The
model must predict the move *out of* a price it never observes.

Reproduced with a marker array where `X[i] == i`:

```
dataset[0]  (i = 5)   x window rows : [0, 1, 2, 3, 4]
                        label        : 0  (y[5])
                        row 5 in input?  False
                        label depends on close[5]=105 vs close[6]=104
...
dataset[6]  (i = 11)  x window rows : [6, 7, 8, 9, 10]
                        row 11 in input? False
```

XGBoost, on the same row, receives the **full feature vector at row `i`**
(including `close_to_sma_*`, `return_1d`). Both models are then scored against
the same labels.

**Consequence:** the reported `LSTM auc = 0.4495` — *worse than a coin flip* — is
not evidence that attention/LSTM fails on NEPSE. The comparison is not
apples-to-apples; the LSTM is handicapped by construction.

**Fix** (`lstm_model.py:112,119`):

```python
self.indices = list(range(seq_length - 1, len(X), stride))
x_seq = self.X[i - self.seq_length + 1: i + 1].clone()
```

The `- 1`/`+ 1` change the dataset length; the notebook's date slicing must be
reconciled with it (see issue 3).

**Secondary robustness gap:** the class never asserts `len(X) == len(y)`. When they
differ, the final index raises `IndexError` from deep inside `__getitem__`
rather than at construction. In the real pipeline `dropna` on the target aligns
them, but the invariant is unasserted.

## 🔴 2. Threshold tuning on the test set

Notebook cells 35 and 61 sweep the decision threshold by maximising F1 **on the
test labels**, then report those same test labels as the result:

```python
for t in np.arange(0.30, 0.70, 0.01):
    f1_t = f1_score(lstm_t.astype(int), (lstm_p > t).astype(int), zero_division=0)
```

Cell 29's `optimize_threshold(X_val_lstm, y_val)` is done correctly. Every
"improved" number in the later cells is inflated relative to that honest baseline.

**Fix:** tune on the validation split, report on test once.

## 🔴 3. The backtest does not correspond to the reported best model

Cell 41 picks the winner with `comparison_df["accuracy"].idxmax()` and writes
`model_comparison.csv`. The winner is `Ensemble(0.7XGB+0.3LSTM)` at 0.6294.

Cell 44 then backtests a **hardcoded** `best_weights = {"xgboost": 0.5, "lstm": 0.5}`.

So the P&L in `backtest_NABIL.csv` corresponds to no row in the comparison table.

Related: the confusion matrices total **313** samples while the backtest consumes
**312**. Cell 44 slices with `test_dates[seq_len + 1 : seq_len + 1 + len(y_test_aligned)]`
— an extra `+1` in one place and not the other, so one evaluation day is counted in
the metrics but dropped from the P&L.

## 🔴 4. The reported alpha is cash exposure, not skill

Measured on `results/backtest_NABIL.csv`:

```
days in market        : 76 / 312 = 24.4 %
strategy final        : 90972.53
buy & hold final      : 87658.45
alpha (shipped)       : +0.0235
```

`metrics.py:110` assumes cash earns exactly 0%:

```python
strategy_returns = signals * actual_returns - trade_costs
```

The strategy is flat **75.6%** of the time. NABIL fell ~12.3% over the window, so
*any* mostly-cash strategy beats it regardless of whether the model has signal.
There is no cash benchmark, and the 0.2% per-side cost has no slippage, market
impact, or NEPSE circuit-band modelling.

### 4a. `total_return` for buy & hold is computed wrong

`metrics.py:151-152`:

```python
total_return_bh = bt_df["buyhold_cumulative"].iloc[-1] / bt_df["buyhold_cumulative"].iloc[0] - 1
```

`buyhold_cumulative[0]` is `initial_capital * (1 + r₀)`, not `initial_capital`.
Verified against the shipped artifact:

```
true total return = -0.1234   shipped = -0.1188   → 0.465pp too flattering
```

The strategy's own figure happens to be unaffected (`r₀ = -0.0`), but the
**benchmark** — the denominator of the alpha claim — is wrong in the flattering
direction. Correct form is `.iloc[-1] / initial_capital - 1`.

## 🟠 5. `win_rate` is not a trade win rate

`metrics.py:167`:

```python
win_rate = np.mean(strat_ret[bt_df["signal"] == 1] > 0)
```

This is the fraction of **invested days** that were positive — a daily hit rate —
printed next to `n_trades` (a trade count) under the label `"Win Rate"`. The two
are not commensurable.

There are also **two conflicting Sharpe definitions**: `metrics.py:160` uses
`ann_return / vol` with no risk-free rate; `helpers.py:64-68` uses
`(mean*252 - rf) / vol`. Same name, different formula.

## 🟠 6. Dead-zone filtering conditions the sample on the future

Notebook cell 57:

```python
df_imp["future_return"] = (df_imp["future_close"] - df_imp["close"]) / df_imp["close"]
mask_clear = df_imp["future_return"].abs() >= DEAD_ZONE
df_filtered = df_imp[mask_clear].copy()
```

Row inclusion is decided by **tomorrow's return**. This is selection on the
outcome: a 0.3% dead zone is precisely the region where the direction label is
near a coin flip, so it inflates apparent accuracy while making the model useless
on real trading days. Measured on NABIL: **3364 → 2462 rows, 26.8% of days removed.**

Worse, cells 60/61 then build `StockSequenceDataset` windows over that filtered
frame, which are no longer contiguous:

> mean gap between surviving rows = **2.19 trading days**, max **51 calendar days**
> ⇒ a `sequence_length=30` window spans **≈66 calendar days**, not 30 trading days

Every `t-{seq_len}` attention label in those runs is wrong.

## 🟠 7. Training without validation silently keeps epoch 1

`lstm_model.py:575-597`: with `X_val=None`, `val_loss` is pinned at `0`.

```
epoch 1 : 0 < inf          → save best state
epochs 2+: 0 < 0 - 1e-4    → patience_counter += 1
```

Verified: `epochs saving best state = [1] | patience counter = 2 / 99`. The model
reverts to its epoch-1 weights, `patience=30` never fires so all 200 epochs are
wasted, and there is no warning.

`xgboost_model.py:121-129` has the same footgun — with no val set it early-stops
on the **training** set, which never triggers, and silently grows all 1000 trees.

**Fix:** raise if no validation data is supplied.

## 🟠 8. Train and validation losses measure different objectives

`lstm_model.py:553-556` (train) vs `:646` (validate):

```python
loss = criterion(logits, y_smooth)   # y_smooth = y*(1-0.05) + 0.5*0.05
loss = criterion(logits, y_batch)    # RAW labels
```

With `label_smoothing=0.05`, training minimises a smoothed BCE while checkpoint
selection minimises an unsmoothed one. The "Train Loss vs Val Loss" plots put two
different objectives on one axis. Same defect in notebook cells 34, 38, 60.

Additionally `lstm_model.py:655-658` averages **per-batch means** without
`drop_last` on the val loader, so the val loss that drives early stopping is
biased toward the trailing partial batch.

## 🟠 9. `predict()` has incompatible contracts in the two model files

```python
# xgboost_model.py:161-165
def predict(self, X) -> np.ndarray:
    return self.model.predict(X)          # hard 0/1 LABELS

# lstm_model.py:674-719
def predict(self, X) -> Tuple[np.ndarray, np.ndarray]:
    return predictions, attention         # PROBABILITIES + weights
```

`metrics.py:213-239` `ensemble_predictions` does a plain weighted sum over them.
Passing XGBoost labels averages **labels with probabilities**, producing numbers
whose 0.5 threshold is meaningless. The notebook happens to pass probabilities
everywhere so the shipped numbers survive, but the API invites the bug.

## 🟠 10. Saved artifacts cannot be reproduced by the committed code

Two independent proofs of drift:

| | `meta.json` records | `config.py` says |
|---|---|---|
| XGBoost `max_depth` | 6 | 5 |
| LSTM `sequence_length` | 60 | 30 |
| LSTM `dropout` | 0.4 | 0.25 |

And the data moved: the test split now runs `2024-07-01 → 2026-10-02` (516 rows),
but `backtest_NABIL.csv` ends at **2026-02-26** with 312 rows.

**Worse, `lstm_model.py:867-883` `load()` reconstructs the architecture from the
live global `config.py`, never from the `meta.json` it just wrote.** Loading
`lstm_NABIL_20260301_053143` today builds 30-row windows for a model trained on
60 — **silently wrong predictions, no error.**

## 🟠 11. `meta.json` is missing everything needed to reproduce

XGBoost records 4 of ~16 hyperparameters. LSTM records 5 fields. Missing from
both:

| Gap | Consequence |
|---|---|
| **Seed** | nothing records that `set_seed(42)` ran; `random_state=42` is hardcoded at `xgboost_model.py:64,81` so `config.py:196 seed` is **dead** |
| **Split boundaries** | no train/val/test date ranges |
| **Scaler params** | only in an opaque `.pkl` — `center_`/`scale_` should be in the JSON |
| **Test metrics** | `training_history` holds train+val only; the model ships with **no record of out-of-sample performance** |
| **`scale_pos_weight`** | the value that makes the probabilities uncalibrated |
| **`optimal_threshold`** | `lstm_model.py:793` sets it; `save()` never writes it — **the tuned threshold is lost** |
| **Data provenance** | no CSV name, row count, hash, or git commit |
| **Library versions** | XGBoost JSON is not forward-compatible across majors |
| **Row counts** | the 2504→2289 `dropna` loss is invisible |

## 🟡 12. Feature-engineering defects

| Location | Defect |
|---|---|
| `technical.py:183-184` | RSI returns `NaN` instead of **100** when `avg_loss == 0` (`replace(0, np.nan)`), and `dropna()` then **deletes the row**. **340 rows repo-wide** across illiquid names — a stock-dependent selection bias. |
| `technical.py:356-362` | `close_change_lag_N` is an **exact duplicate** of `return_lag_N` (`return_1d` *is* `close.pct_change()`, line 95). Verified identical at lags 1,2,3,5. **8 of 157 features are copies** — which is why the `|r|>0.95` correlation filter exists as a band-aid. |
| `technical.py:165` | Bollinger uses `std(ddof=1)`; the standard (and TA-Lib) definition is `ddof=0`. Bands are **~2.6% off** by the std term, so `bb_upper/lower/position/width` are all systematically wrong. |
| `technical.py:190-191` | `rsi_divergence = np.sign(a) != np.sign(b)` — `NaN != NaN` is `True`, so the flag is **unconditionally 1** during warm-up. Currently masked only because `dropna` removes those rows. |
| `technical.py:266` | `dist_from_{w}d_low` is always ≥ 0 (distance *above* the low) and is **collinear with `price_pos_{w}d`** (line 264). Three names, one signal. |
| `technical.py:293,313` | raw `obv`/`vpt` are **non-stationary cumulative levels** fed to a scaler. `obv` ranges −6,589,598 → 4,994,684 on NABIL, so the value is a proxy for *absolute time since inception*. It is among the top-10 features (`obv_sma_20` #5, `vpt` #6) — the likely cause of XGBoost's `train_accuracy 0.9969` vs `val_accuracy 0.5160`. |
| `technical.py:295` | `obv_slope` divides by `obv.shift(5).abs().replace(0, nan)` — a quantity that legitimately crosses zero, producing the ±123 outliers. |
| `technical.py:111,115` | `(close - sma) / sma` is unguarded against `sma == 0` → `inf`. Zero occurrences on real data, no guard in code. |

Correct and worth preserving: `technical.py:202,217` (`stoch_k`, `williams_r`) guard
their denominators; `:228` correctly uses `axis=1` for the row-wise max of the
three TR candidates; `:340-348` consecutive-run logic is right; `:113-115` uses
the correct `ewm(adjust=False)` EMA convention. All indicators are causal — no
`center=True`, no `bfill`, no `shift(-n)` anywhere.

## 🟡 13. Reproducibility gaps

- `helpers.py:23` sets `os.environ["PYTHONHASHSEED"]` **in-process — a no-op.**
  CPython reads it once at startup. It gives the *appearance* of determinism.
- `torch.use_deterministic_algorithms(True)` is never set.
  `cudnn.deterministic=True` does not cover the fused CUDA RNN backward used by
  `nn.LSTM`. Run-to-run bit-reproducibility on GPU is not guaranteed — and
  `config.py:197 device: str = "auto"` is **dead** (see issue 15), so you cannot
  force CPU to get it.
- `n_jobs=-1` (`xgboost_model.py:65,82`): XGBoost is deterministic only for a
  fixed thread count.

## 🟡 14. Dead config and dead code

**Config fields never read by any code path:** `fillna_method` (`config.py:53` —
**no forward-fill is ever performed despite the comment**),
`use_feature_importance_filter` + `top_n_features`, `warmup_epochs`,
`use_time_masking` + `mask_ratio` (**"Data Augmentation" is half-implemented**;
only Gaussian noise exists), `use_ensemble` + `ensemble_weights`,
`walk_forward_step/train_min/n_splits` (`walk_forward_splits` re-declares its own
defaults instead of reading them), `n_cv_splits` (hardcoded `5`),
`TrainingConfig.seed`, `device`.

**Never called:** `get_eligible_stocks` (so `target_stocks`, `min_rows`,
`min_avg_volume` are dead), `walk_forward_splits`, `regression_metrics`,
`directional_accuracy`, `reduce_memory`, `calculate_sharpe`,
`calculate_max_drawdown`.

**Silently ignored:** `l2_reg` is accepted at `config.py:161`, plumbed through
`lstm_model.py:495`, given a parameter default at `:201` — and then **never used**.
Verified: no `kernel_regularizer` anywhere in the file. The declared L2 penalty is
zero; the only weight decay is `AdamW(weight_decay=5e-4)`.

**Unreachable:** `lstm_model.py:428` `elif self.cfg.optimizer == "radam"` —
`"radam"` appears nowhere in `config.py`.

**`_get_device` has two identical branches** (`lstm_model.py:345-348`) and both
ignore `TrainingConfig.device`. Same in `helpers.py:26-34`. Every run silently
used the GPU.

**Dead imports:** `os` (`lstm_model.py:13`, `xgboost_model.py:8`,
`preprocessor.py:7`), `pandas as pd` (`lstm_model.py:16` — zero `pd.` uses),
`pickle` (`xgboost_model.py:10`), `classification_report` (`metrics.py:16`).

**Import side effect:** `config.py:21-22` creates three directories at import time.
Importing the config from a test or read-only process silently writes to disk.

**`get_feature_names()` will leak the target** if called on a frame that has it:
`technical.py:443` excludes `{time, symbol, category, open, high, low, close,
volume}` but **not** `target` or `sector`. Verified:
`get_feature_names() after create_target includes 'target': True`. Currently masked
only because the notebook calls it before `create_target`.

## 🟡 15. Unvalidated metrics that activate on a config flip

`metrics.py:58` MAPE on a target that crosses zero:

```
returns targets  -> MAPE = 65.3 %   (a 0.1% return error reads as 65%)
price targets    -> MAPE = 0.69 %
```

`target_type="regression"` produces `(close[t+h]-close[t])/close[t]`
(`preprocessor.py:227`), so `1e-8` instead of a mask makes this explode. Dormant
only because `regression_metrics` is never called. Flip `target_type` and it is
silently reported.

`metrics.py:62-66` `directional_accuracy` uses `np.sign`, which returns `0` for a
zero return — so a flat day with a "flat" prediction counts as a **correct**
directional call.

`metrics.py:207` `compare_models` = `pd.DataFrame(results).T`, which unions keys
across heterogeneous metric dicts and produces silent NaN columns — a NaN then
propagates into the `idxmax()` that picks the "best" model (issue 3).

## 🟡 16. Class-imbalance handling is inconsistent and never reported

XGBoost gets `scale_pos_weight = n_neg/n_pos` (`xgboost_model.py:110`); the LSTM
gets `pos_weight` on `BCEWithLogitsLoss` **plus** `label_smoothing=0.05`
(`lstm_model.py:521,555`); the pooled LSTM uses `label_smooth = 0.1`. Two
mechanisms pulling in opposite directions with no calibration step. The artifact
shows XGBoost recall 0.40 / specificity 0.75 — so `predict_proba > 0.5` on that
model is **not** a 50%-probability event, yet both models are scored against a
shared 0.5 threshold.

`xgboost_model.py:174-200` `_evaluate` calls `self.model.predict()` directly,
bypassing the "not trained" and "classification only" guards in the wrapper, so a
`target_type` mismatch raises a raw xgboost error instead of the intended message.

---

## Fix order

**Do these first — they invalidate published numbers:**

1. `lstm_model.py:119` — include row `i` in the window. **Until then, discard
   `model_comparison.csv`.**
2. Notebook cells 35/61 — move all threshold tuning to validation.
3. Notebook cell 44 — derive `best_weights` from the actual argmax; reconcile the
   313/312 sample mismatch.
4. `metrics.py:151-152` — divide by `initial_capital`; add a cash benchmark to
   `metrics.py:110`; re-report alpha and Sharpe honestly.
5. Notebook cell 57 — drop the dead-zone filter, or re-frame every downstream
   number as "conditional on |next-day return| ≥ 0.3%".
6. Cells 60/61 — don't window over dead-zone-filtered rows.

**Then, correctness:**

7. `technical.py:183` — RSI = 100 when `avg_loss == 0`.
8. `technical.py:356-362` — delete the 8 duplicate columns.
9. `technical.py:165` — `ddof=0` for Bollinger.
10. `lstm_model.py:646` — smoothed labels in `_validate`.
11. `lstm_model.py:591` — raise when `val_loader is None`.
12. `metrics.py:167` — rename `win_rate` to `hit_rate`, or compute a real trade win rate.

**Then, deployability:**

13. `lstm_model.py:867` — `load()` must read `meta.json` and assert architecture,
    `sequence_length`, and `n_features` against the state dict.
14. Persist seed, split boundaries, scaler params, full hyperparameters,
    `scale_pos_weight`, `optimal_threshold`, library versions, and a data hash.
15. `helpers.py:23` — drop the no-op `PYTHONHASHSEED`; add
    `torch.use_deterministic_algorithms(True)`; route `random_state` and `device`
    through the config.
16. Reconcile the artifacts with the repo, or delete them — they cannot currently
    be reproduced by running the committed code.

**Then cleanup:** wire up or delete the 11 dead config fields and 7 dead
functions; remove the 6 dead imports, the `_get_device` dead branches, the
`"radam"` dead branch, and the `mkdir` side effect in `config.py:21`; add
`target`/`sector` to the `get_feature_names()` exclusion set.

## A note on the honest signal

`xgb_NABIL_20260301_053142_feature_importance.csv` has 157 rows with the top
feature at **1.9%** and the 157th at ~0.03%. That near-uniform spread is itself
evidence that the directional signal is weak — and it means the
`get_top_features(50)` filter is selecting close to arbitrarily. Combined with
issues 1, 2, 4 and 6, the reported 0.63 ensemble accuracy should be treated as an
upper bound until the evaluation is rebuilt on clean splits.