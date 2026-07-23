"""
One command rebuilds everything from /data/raw:

    python -m pipeline.run_all           # fetch (idempotent) -> build -> QA

Exit non-zero if the QA gate fails (blocks downstream Phase 2).
"""
import sys, warnings
warnings.filterwarnings("ignore")
from pipeline import fetch, build_db, qa, seed_nppe, load_preferences


def main(skip_fetch=False):
    if not skip_fetch:
        print("== FETCH ==")
        fetch.fetch_all()
    print("== BUILD DB ==")
    stats = build_db.build()
    for k, v in stats.items():
        print(f"  {k:16} {v}")
    print("== SEED ΝΠΠΕ ==")
    print("  nppe_programs   ", seed_nppe.seed())
    print("== LOAD PREFERENCES (ζήτηση) ==")
    load_preferences.main()
    print("== FORECAST (carry-forward + PI) ==")
    try:
        from pipeline import forecast as _fc
        import duckdb as _dk, pandas as _pd
        _con = _dk.connect(str(build_db.DB))
        _panel = _fc.load_panel(_con)
        _sc, _res = _fc.backtest(_panel)
        _cov = _fc.loo_coverage(_panel)
        _fcast, _pi = _fc.forecast_next(_panel, 2026, regime="post")
        _con.execute("DELETE FROM prediction"); _con.execute("DELETE FROM backtest_score")
        _p = _fcast[["dept_code", "target_year", "point", "lower_80", "upper_80",
                     "lower_95", "upper_95"]].copy()
        _p["category"] = "ΓΕΛ90"; _p["model_name"] = "carry_forward"
        _p["ebe_floor_est"] = None; _p["demand_est"] = _fcast["point"]
        _p["baseline_pred"] = _fcast["point"]; _p["created_at"] = _pd.Timestamp.now()
        _con.register("p_df", _p[["dept_code", "target_year", "category", "model_name",
            "point", "lower_80", "upper_80", "lower_95", "upper_95", "ebe_floor_est",
            "demand_est", "baseline_pred", "created_at"]])
        _con.execute("INSERT INTO prediction SELECT * FROM p_df")
        _b = _sc.copy(); _b["model_name"] = "carry_forward"
        _b["test_year"] = _b["fold"].str[-4:].astype(int); _b["segment"] = _b["break"]
        _b["baseline_mae"] = _b["mae"]; _b["skill"] = 0.0
        _b["coverage_80"] = _cov["coverage_80"].values; _b["coverage_95"] = _cov["coverage_95"].values
        _con.register("b_df", _b[["model_name", "test_year", "segment", "mae",
            "baseline_mae", "skill", "coverage_80", "coverage_95", "n"]])
        _con.execute("INSERT INTO backtest_score SELECT * FROM b_df")
        _con.close()
        print(f"  predictions     {len(_p)} (2026)  |  backtest folds {len(_b)}  "
              f"|  mean MAE {_sc.mae.mean():.0f} μόρια")
    except Exception as e:
        print("  forecast skipped:", e)
    print("== QA GATE ==")
    rc = qa.run()
    return rc


if __name__ == "__main__":
    sys.exit(main(skip_fetch="--skip-fetch" in sys.argv))
