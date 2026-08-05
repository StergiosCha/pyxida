"""
Phase 3 · forecast.py — βάσεις forecasting with an honest backtest.

DATA REALITY: usable ΓΕΛ90 years are 2015-2019 and 2024-2025 (2020-2023 are
absent from official open data). That yields FIVE consecutive-year folds:
    2015→16, 2016→17, 2017→18, 2018→19  (pre-ΕΒΕ)   and   2024→25 (post-ΕΒΕ).
The master prompt's 2022-2025 window is not reconstructable; we backtest on the
folds the data supports and say so.

MODELS TESTED (leave-one-fold-out, no leakage)
  baseline : carry-forward, ŷ_t = y_{t-1}.
  pooled   : ŷ_t = y_{t-1} + λ·(field drift). Tested λ∈[0,1].
  meanrev  : ŷ_t = y_{t-1} + β·(field median − y_{t-1}). Tested β∈[0,0.3].

RESULT: neither pooled drift nor mean-reversion beats carry-forward on any λ/β
(best skill ≈ 0%; positive-looking numbers were an artifact of NaN-field
departments silently dropping out of the model MAE). Per the master prompt's
non-negotiable — "ship a model only if it beats baseline" — we SHIP CARRY-
FORWARD as the point forecast and do NOT ship a demand model. The scores table
records the tested alternatives for transparency.

WHY ΕΒΕ IS NOT CLIPPED ON THE μόρια SCALE: the ΕΒΕ threshold is defined on the
field-average (/20)×1000 scale, not the μόρια (/20000) scale, so a literal
max(ΕΒΕ, demand) in μόρια compares incompatible units and empirically worsened
the 2024→2025 fold. We instead surface the department's ΕΒΕ coefficient and note
that a rise in the field ΕΒΕ would lift its floor — as an annotation, not a clip.

VALUE DELIVERED: carry-forward point forecast + EMPIRICAL prediction intervals
from the pooled residual distribution. Post-ΕΒΕ βάσεις are far more stable
(fold MAE 400 vs ~1000 pre-break), so the 2026 forecast uses POST-BREAK
residuals for a properly-calibrated, regime-appropriate interval.
"""
from __future__ import annotations
from pathlib import Path
import numpy as np, pandas as pd, duckdb

DB = Path(__file__).resolve().parent.parent / "data" / "pyxida.duckdb"
CATEGORY = "ΓΕΛ90"


def load_panel(con) -> pd.DataFrame:
    return con.execute("""
        SELECT a.dept_code, a.year, a.base_last, a.ebe_threshold,
               a.ebe_coefficient, d.scientific_field AS field
        FROM admission a JOIN department d ON d.dept_code=a.dept_code
        WHERE a.category=? AND a.base_last IS NOT NULL""", [CATEGORY]).df()


def _folds(years):
    return [(a, b) for a, b in zip(years, years[1:]) if b - a == 1]


# ── models (for the transparency table) ──────────────────────────────────
def _field_drift(train, y0, y1):
    a = train[train.year == y0][["dept_code", "field", "base_last"]]
    b = train[train.year == y1][["dept_code", "base_last"]]
    m = a.merge(b, on="dept_code", suffixes=("_0", "_1"))
    m["chg"] = m["base_last_1"] - m["base_last_0"]
    return m.groupby("field")["chg"].mean().to_dict()


def _pick_train_transition(train, y0):
    tf = _folds(sorted(train.year.unique()))
    same = [f for f in tf if (f[0] >= 2021) == (y0 >= 2021)]
    pick = same or tf
    return pick[len(pick) // 2] if pick else None


def carry_forward_fold(panel, y0, y1):
    """Carry-forward predictions + errors for one fold."""
    a = panel[panel.year == y0][["dept_code", "base_last", "ebe_coefficient"]]
    b = panel[panel.year == y1][["dept_code", "base_last"]].rename(columns={"base_last": "actual"})
    j = a.merge(b, on="dept_code")
    j["pred"] = j["base_last"]
    j["err"] = j["pred"] - j["actual"]
    return j


def backtest(panel: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    """Carry-forward backtest across all folds. Returns (scores, pooled residuals)."""
    years = sorted(panel.year.unique())
    folds = _folds(years)
    rows, resids = [], []
    for (y0, y1) in folds:
        j = carry_forward_fold(panel, y0, y1)
        resids.append(j["err"].values)
        rows.append({"fold": f"{y0}→{y1}", "n": len(j),
                     "mae": round(j["err"].abs().mean(), 1),
                     "rmse": round(np.sqrt((j["err"] ** 2).mean()), 1),
                     "bias": round(j["err"].mean(), 1),
                     "break": "post-ΕΒΕ" if y0 >= 2021 else "pre-ΕΒΕ"})
    return pd.DataFrame(rows), (np.concatenate(resids) if resids else np.array([]))


def model_comparison(panel: pd.DataFrame) -> pd.DataFrame:
    """Transparency table: carry-forward vs best pooled vs best meanrev.
    Fair MAE — every model scored on the SAME department set per fold."""
    years = sorted(panel.year.unique())
    folds = _folds(years)
    out = []
    for name, kind, grid in [("carry-forward", "cf", [0]),
                             ("pooled-drift", "pooled", [0.1, 0.2, 0.3, 0.6, 1.0]),
                             ("mean-reversion", "meanrev", [0.05, 0.1, 0.15, 0.2])]:
        best = None
        for p in grid:
            maes_m, maes_b = [], []
            for (y0, y1) in folds:
                j = carry_forward_fold(panel, y0, y1).merge(
                    panel[panel.year == y0][["dept_code", "field"]], on="dept_code", how="left")
                if kind == "cf":
                    pred = j["base_last"]
                elif kind == "pooled":
                    train = panel[panel.year.isin([y for f in folds if f != (y0, y1) for y in f])]
                    tt = _pick_train_transition(train, y0)
                    dm = _field_drift(train, *tt) if tt else {}
                    pred = j["base_last"] + p * j["field"].map(dm).fillna(0.0)
                else:  # meanrev
                    fmed = j.groupby("field")["base_last"].transform("median").fillna(j["base_last"])
                    pred = j["base_last"] + p * (fmed - j["base_last"])
                maes_m.append((pred - j["actual"]).abs().mean())
                maes_b.append((j["base_last"] - j["actual"]).abs().mean())
            mae = float(np.mean(maes_m))
            skill = 100 * (1 - mae / float(np.mean(maes_b)))
            if best is None or mae < best["mae"]:
                best = {"model": name, "param": p, "mae": round(mae, 1), "skill_%": round(skill, 2)}
        out.append(best)
    return pd.DataFrame(out)


def pi_from_resid(resid: np.ndarray) -> dict:
    if len(resid) == 0:
        return {k: 0.0 for k in ("lo80", "hi80", "lo95", "hi95")}
    return {"lo80": float(np.quantile(resid, 0.10)), "hi80": float(np.quantile(resid, 0.90)),
            "lo95": float(np.quantile(resid, 0.025)), "hi95": float(np.quantile(resid, 0.975))}


def loo_coverage(panel) -> pd.DataFrame:
    """Leave-one-fold-out PI coverage: build the interval from the OTHER folds'
    residuals, test on the held-out fold."""
    years = sorted(panel.year.unique()); folds = _folds(years)
    fold_res = [carry_forward_fold(panel, y0, y1)["err"].values for (y0, y1) in folds]
    rows = []
    for k, (y0, y1) in enumerate(folds):
        others = np.concatenate([fold_res[i] for i in range(len(folds)) if i != k])
        pi = pi_from_resid(others)
        e = fold_res[k]
        rows.append({"fold": f"{y0}→{y1}", "n": len(e),
                     "coverage_80": round(float(((e >= pi["lo80"]) & (e <= pi["hi80"])).mean()), 3),
                     "coverage_95": round(float(((e >= pi["lo95"]) & (e <= pi["hi95"])).mean()), 3),
                     "break": "post-ΕΒΕ" if y0 >= 2021 else "pre-ΕΒΕ"})
    return pd.DataFrame(rows)


# ── Mechanistic model with damping (shipped from 2026 on) ─────────────────────
# Official per-field ΕΒΕ reference values, /20 scale, as announced each July.
FIELD_REFERENCE = {
    2024: {"1ο": 11.5856, "2ο": 12.2306, "3ο": 11.9880, "4ο": 10.4814},
    2025: {"1ο": 11.4841, "2ο": 12.3476, "3ο": 11.9938, "4ο": 10.5530},
    2026: {"1ο": 11.2000, "2ο": 13.0900, "3ο": 12.3200, "4ο": 10.3300},
}

# Damping factor λ. The ΕΒΕ threshold is a FLOOR, not a price: when demand sits
# well above the floor, a coefficient change barely moves the βάση. The undamped
# form (λ=1) overshoots the realised move by ~2.2× on the departments whose
# coefficient changed, and beats carry-forward by only 6.6% overall (MAE 498.0)
# against 13.0% for the damped form.
#
# λ=0.5 was calibrated on the 2024→2025 transition (MAE 370.6 vs 399.9
# carry-forward, +7.3%, n=449) and then scored OUT OF SAMPLE on the realised
# 2026 bases: MAE 464.3 vs 533.4 carry-forward, +13.0%, winning on 281/451
# departments (80% PI coverage 0.721 against a nominal 0.80). The same optimum
# arises independently in both years, so it is not fitted to the year scored.
#
# All figures above use department.scientific_field as the field key — the
# authoritative value in the DB. An earlier pass keyed off the field of the
# mirror page it was scraped from and reported MAE 446.6 / +16.3% / 296 wins;
# those numbers are superseded. pipeline/score_2026.py reproduces the values
# recorded here and writes them to the backtest_score table.
DAMPING_LAMBDA = 0.5


def mechanistic_damped(base_last, field, coef_from, coef_to,
                       year_from, year_to, lam: float = DAMPING_LAMBDA):
    """base_to = base_from × (1 + λ·(ratio − 1)), ratio = (coef_to/coef_from)
    × (field_reference_to/field_reference_from). Returns NaN when any input is
    missing — never silently falls back to carry-forward, so callers can see
    coverage."""
    rf, rt = FIELD_REFERENCE.get(year_from, {}), FIELD_REFERENCE.get(year_to, {})
    if field not in rf or field not in rt:
        return np.nan
    if not (coef_from and coef_to) or pd.isna(coef_from) or pd.isna(coef_to):
        return np.nan
    if pd.isna(base_last):
        return np.nan
    ratio = (coef_to / coef_from) * (rt[field] / rf[field])
    return round(base_last * (1 + lam * (ratio - 1)))


def forecast_next(panel: pd.DataFrame, target_year: int = 2026,
                  regime: str = "post") -> pd.DataFrame:
    """Carry-forward point forecast for target_year with empirical PIs.
    regime='post' uses only post-ΕΒΕ residuals (recommended: matches the
    current regime and is far tighter); 'all' pools every fold."""
    years = sorted(panel.year.unique()); last = years[-1]
    folds = _folds(years)
    if regime == "post":
        src = [f for f in folds if f[0] >= 2021] or folds
    else:
        src = folds
    resid = np.concatenate([carry_forward_fold(panel, y0, y1)["err"].values for (y0, y1) in src])
    pi = pi_from_resid(resid)
    base = panel[panel.year == last][["dept_code", "field", "base_last", "ebe_coefficient"]].copy()
    base["target_year"] = target_year
    base["point"] = base["base_last"]                         # carry-forward
    base["lower_80"] = base["point"] + pi["lo80"]
    base["upper_80"] = base["point"] + pi["hi80"]
    base["lower_95"] = base["point"] + pi["lo95"]
    base["upper_95"] = base["point"] + pi["hi95"]
    base["model_name"] = "carry_forward"
    base["regime"] = regime
    return base, pi


if __name__ == "__main__":
    con = duckdb.connect(str(DB), read_only=True)
    panel = load_panel(con); con.close()
    scores, resid = backtest(panel)
    comp = model_comparison(panel)
    cov = loo_coverage(panel)
    print("Carry-forward backtest (MAE in μόρια):")
    print(scores.to_string(index=False))
    print(f"\nOverall carry-forward MAE = {scores.mae.mean():.0f} μόρια "
          f"(pre-ΕΒΕ {scores[scores['break']=='pre-ΕΒΕ'].mae.mean():.0f}, "
          f"post-ΕΒΕ {scores[scores['break']=='post-ΕΒΕ'].mae.mean():.0f})")
    print("\nModel comparison (best param per model, fair same-set MAE):")
    print(comp.to_string(index=False))
    print("\nLeave-one-fold-out PI coverage:")
    print(cov.to_string(index=False))
    fc_all, pi_all = forecast_next(panel, 2026, regime="all")
    fc_post, pi_post = forecast_next(panel, 2026, regime="post")
    print(f"\n2026 PI width (μόρια): all-folds 80%=±{(pi_all['hi80']-pi_all['lo80'])/2:.0f}, "
          f"post-only 80%=±{(pi_post['hi80']-pi_post['lo80'])/2:.0f}")

