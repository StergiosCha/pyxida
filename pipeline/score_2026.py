#!/usr/bin/env python3
"""Βαθμολογεί το μοντέλο στις πραγματικές βάσεις 2026 και γράφει τα αποτελέσματα.

Τι κάνει:
  1. Υπολογίζει τις προβλέψεις 2026 με το μηχανιστικό μοντέλο με απόσβεση
     (forecast.mechanistic_damped, λ=0.5) από τα δεδομένα 2025.
  2. Τις γράφει στον πίνακα prediction με model_name='mechanistic_damped',
     δίπλα στη γραμμή baseline_pred (περσινή βάση) για άμεση σύγκριση.
  3. Γράφει τη γραμμή επίδοσης στον backtest_score.

Τα διαστήματα πρόβλεψης προκύπτουν από τα υπόλοιπα της μετάβασης 2024->2025,
δηλαδή ΕΚΤΟΣ του έτους που βαθμολογείται. Η πραγματική κάλυψη στο 2026
καταγράφεται όπως μετρήθηκε (80%: 0.745), χωρίς εκ των υστέρων διόρθωση.

Χρήση: σταμάτα το uvicorn, μετά:  python pipeline/score_2026.py
"""

import datetime
import pathlib
import sys

import duckdb
import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from forecast import DAMPING_LAMBDA, mechanistic_damped

ROOT = pathlib.Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "pyxida.duckdb"
CAT = "ΓΕΛ90"


def _transition(con, y0, y1):
    """Ζεύγη (βάση, συντελεστής) για δύο διαδοχικά έτη, μόνο πλήρεις γραμμές."""
    return con.execute("""
        SELECT a0.dept_code, d.scientific_field AS field,
               a0.base_last AS b0, a0.ebe_coefficient AS c0,
               a1.base_last AS b1, a1.ebe_coefficient AS c1
        FROM admission a0
        JOIN admission a1 ON a1.dept_code = a0.dept_code
                         AND a1.year = ? AND a1.category = ?
        JOIN department d ON d.dept_code = a0.dept_code
        WHERE a0.year = ? AND a0.category = ?
          AND a0.base_last IS NOT NULL AND a1.base_last IS NOT NULL
          AND a0.ebe_coefficient IS NOT NULL AND a1.ebe_coefficient IS NOT NULL
    """, [y1, CAT, y0, CAT]).fetchdf()


def main():
    con = duckdb.connect(str(DB))

    # ── διαστήματα από τη ΠΡΟΗΓΟΥΜΕΝΗ μετάβαση (εκτός δείγματος για το 2026) ──
    cal = _transition(con, 2024, 2025)
    cal["pred"] = [mechanistic_damped(r.b0, r.field, r.c0, r.c1, 2024, 2025)
                   for r in cal.itertuples()]
    cal = cal.dropna(subset=["pred"])
    resid = (cal.pred - cal.b1).values
    lo80, hi80 = np.percentile(resid, [10, 90])
    lo95, hi95 = np.percentile(resid, [2.5, 97.5])
    print(f"διαστήματα από 2024->2025 (n={len(cal)}): "
          f"80% [{lo80:.0f}, {hi80:.0f}], 95% [{lo95:.0f}, {hi95:.0f}]")

    # ── προβλέψεις 2026 ──
    cur = _transition(con, 2025, 2026)
    cur["point"] = [mechanistic_damped(r.b0, r.field, r.c0, r.c1, 2025, 2026)
                    for r in cur.itertuples()]
    cur = cur.dropna(subset=["point"])
    assert len(cur), "καμία πρόβλεψη — λείπουν συντελεστές ή βάσεις"

    cur["lower_80"] = cur.point - hi80
    cur["upper_80"] = cur.point - lo80
    cur["lower_95"] = cur.point - hi95
    cur["upper_95"] = cur.point - lo95
    cur["baseline_pred"] = cur.b0          # περσινή βάση
    cur["actual"] = cur.b1

    err_model = (cur.point - cur.actual).abs()
    err_base = (cur.baseline_pred - cur.actual).abs()
    cov80 = float(((cur.lower_80 <= cur.actual) & (cur.actual <= cur.upper_80)).mean())
    cov95 = float(((cur.lower_95 <= cur.actual) & (cur.actual <= cur.upper_95)).mean())
    mae, bmae = float(err_model.mean()), float(err_base.mean())

    print(f"\n2026, n={len(cur)}:")
    print(f"  μοντέλο (λ={DAMPING_LAMBDA}): MAE {mae:.1f}, διάμεσος {err_model.median():.0f}")
    print(f"  περσινή βάση:         MAE {bmae:.1f}, διάμεσος {err_base.median():.0f}")
    print(f"  βελτίωση {100*(1-mae/bmae):+.1f}%, νίκες {(err_model < err_base).sum()}/{len(cur)}")
    print(f"  κάλυψη: 80% -> {cov80:.3f} (ονομαστικό 0.80), 95% -> {cov95:.3f}")

    try:
        con.execute("BEGIN")
        con.execute("DELETE FROM prediction WHERE target_year=2026 AND category=?", [CAT])
        con.register("pr", cur[["dept_code", "point", "lower_80", "upper_80",
                                "lower_95", "upper_95", "baseline_pred"]])
        con.execute("""INSERT INTO prediction
            (dept_code,target_year,category,model_name,point,lower_80,upper_80,
             lower_95,upper_95,ebe_floor_est,demand_est,baseline_pred,created_at)
            SELECT dept_code, 2026, ?, 'mechanistic_damped', point,
                   lower_80, upper_80, lower_95, upper_95,
                   NULL, NULL, baseline_pred, ?
            FROM pr""", [CAT, datetime.datetime.now()])

        con.execute("DELETE FROM backtest_score WHERE test_year=2026")
        con.execute("""INSERT INTO backtest_score
            (model_name,test_year,segment,mae,baseline_mae,skill,
             coverage_80,coverage_95,n) VALUES (?,?,?,?,?,?,?,?,?)""",
            ["mechanistic_damped", 2026, "post-ΕΒΕ", round(mae, 1), round(bmae, 1),
             round(1 - mae / bmae, 4), round(cov80, 3), round(cov95, 3), len(cur)])
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise

    print("\nbacktest_score:")
    print(con.execute("SELECT * FROM backtest_score ORDER BY test_year").fetchdf().to_string(index=False))
    con.close()


if __name__ == "__main__":
    main()
