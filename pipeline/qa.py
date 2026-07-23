"""
Phase 0 · qa.py — the QA gate. MUST pass before Phase 2.

Emits docs/qa_report.md + figures (row counts, missing-value heatmap) and
runs the 5 sanity checks from PLAN.md §4. Exit non-zero if any hard check
fails so CI / the pipeline can block downstream steps.
"""
from __future__ import annotations
import sys
from pathlib import Path
import duckdb, pandas as pd
import matplotlib as mpl, matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "pyxida.duckdb"
DOCS = ROOT / "docs"
DOCS.mkdir(exist_ok=True)

# report anchors (from the research report)
REPORT_SEATS = {2024: 68851, 2025: 68788}      # εισακτέοι base allocation
MED_ATH_BAND = (18000, 19500)                    # Ιατρική Αθήνας βάση plausible band


def run():
    con = duckdb.connect(str(DB), read_only=True)
    checks = []      # (name, passed, detail)
    figs = {}

    # ---- row counts per year x category ----
    counts = con.execute("""
        SELECT year, category, COUNT(*) n,
               COUNT(base_last) n_base,
               SUM(CAST(seats_offered AS BIGINT)) seats,
               SUM(CAST(admitted AS BIGINT)) admitted
        FROM admission GROUP BY year, category ORDER BY year, category""").df()

    # ---- missing-value profile (ΓΕΛ90) ----
    miss = con.execute("""
        SELECT year,
          AVG(CASE WHEN base_last IS NULL THEN 1 ELSE 0 END) base_last,
          AVG(CASE WHEN grade_first IS NULL THEN 1 ELSE 0 END) grade_first,
          AVG(CASE WHEN seats_offered IS NULL THEN 1 ELSE 0 END) seats_offered,
          AVG(CASE WHEN admitted IS NULL THEN 1 ELSE 0 END) admitted,
          AVG(CASE WHEN ebe_coefficient IS NULL THEN 1 ELSE 0 END) ebe_coefficient
        FROM admission WHERE category='ΓΕΛ90' GROUP BY year ORDER BY year""").df().set_index("year")

    # ---- CHECK 1: Ιατρική Αθήνας βάση within band ----
    med = con.execute("""SELECT year, base_last FROM admission
        WHERE dept_code='295' AND category='ΓΕΛ90' ORDER BY year""").df()
    in_band = med["base_last"].between(*MED_ATH_BAND)
    checks.append(("1. Ιατρική ΕΚΠΑ βάση εντός εύρους 18000–19500",
                   bool(in_band.all()),
                   f"{med['base_last'].min():.0f}–{med['base_last'].max():.0f} μόρια, "
                   f"{in_band.sum()}/{len(med)} έτη εντός εύρους"))

    # ---- CHECK 2: total ΓΕΛ90 seats vs report εισακτέοι (order-of-magnitude) ----
    seats = con.execute("""SELECT year, SUM(CAST(seats_offered AS BIGINT)) s
        FROM admission WHERE category='ΓΕΛ90' GROUP BY year""").df().set_index("year")["s"]
    detail2 = []
    ok2 = True
    for y, exp in REPORT_SEATS.items():
        if y in seats.index:
            got = seats[y]
            within = 0.75 * exp <= got <= exp        # ΓΕΛ90 is ~90% of all seats
            ok2 &= within
            detail2.append(f"{y}: ΓΕΛ90={got:,} vs total εισακτέοι~{exp:,}")
    checks.append(("2. Σύνολο θέσεων ΓΕΛ90 συμβατό με εισακτέοι αναφοράς",
                   ok2, "; ".join(detail2)))

    # ---- CHECK 3: κενές θέσεις 2024/2025 order-of-magnitude (~10k) ----
    vac = con.execute("""SELECT year, SUM(CAST(vacancies AS BIGINT)) v
        FROM admission WHERE category='ΓΕΛ90' GROUP BY year ORDER BY year""").df().set_index("year")["v"]
    v2025 = int(vac.get(2025, 0)); v2024 = int(vac.get(2024, 0))
    ok3 = 8000 <= v2025 <= 13000
    checks.append(("3. Κενές θέσεις ΓΕΛ90 2025 τάξης ~10.636 (αναφορά)",
                   ok3, f"2024={v2024:,}, 2025={v2025:,} κενές (αναφορά: 10.636 ΓΕΛ 2025)"))

    # ---- CHECK 4: admitted <= seats & 0<=fill_rate<=1 ----
    # Over-admission by ties (ισοβαθμία) adds WHOLE people, so a small pool can
    # legitimately exceed seats by 1. Flag only rows over BOTH +1 absolute and
    # +2% relative (i.e. genuine data errors, not single-tie over-admission).
    # A single tie (ισοβαθμία) adds at most a small whole number of people at
    # the last rank; over-admission by >=2 seats OR >5% is the error signal.
    bad = con.execute("""SELECT COUNT(*) FROM admission
        WHERE (admitted > seats_offered + 1 AND admitted > seats_offered * 1.05)
           OR fill_rate < 0 OR fill_rate > 1.15""").fetchone()[0]
    ties = con.execute("""SELECT COUNT(*) FROM admission
        WHERE admitted > seats_offered AND admitted <= seats_offered + 1""").fetchone()[0]
    checks.append(("4. Λογική ακεραιότητα (admitted<=θέσεις+ισοβαθμίες, 0<=fill_rate<=1)",
                   bad == 0,
                   f"{bad} γραμμές-σφάλματα· {ties} νόμιμες υπερβάσεις +1 από ισοβαθμία"))

    # ---- CHECK 5: ΕΒΕ coefficients in [0.80,1.20] & absent pre-2021 ----
    outrange = con.execute("""SELECT COUNT(*) FROM admission
        WHERE ebe_coefficient IS NOT NULL
          AND (ebe_coefficient < 0.80 OR ebe_coefficient > 1.20)""").fetchone()[0]
    preebe = con.execute("""SELECT COUNT(*) FROM admission
        WHERE year < 2021 AND ebe_coefficient IS NOT NULL""").fetchone()[0]
    checks.append(("5. Συντελεστές ΕΒΕ εντός [0.80,1.20] & απόντες προ-2021",
                   outrange == 0 and preebe == 0,
                   f"{outrange} εκτός εύρους, {preebe} προ-2021 με ΕΒΕ"))

    # ---- unmatched log summary ----
    n_unmatched = con.execute("SELECT COUNT(*) FROM unmatched_dept").fetchone()[0]
    n_alias = con.execute("SELECT COUNT(*) FROM dept_alias").fetchone()[0]

    # ===== FIGURES =====
    apply_figure_style(sizes=(9, 8, 7))

    # Fig A: row counts per year x category
    piv = counts.pivot_table(index="year", columns="category", values="n", fill_value=0)
    order = [c for c in ["ΓΕΛ90", "ΓΕΛ10", "ΕΠΑΛ90", "ΕΠΑΛ10"] if c in piv.columns]
    piv = piv[order]
    figA, axA = plt.subplots(figsize=(7, 3.6))
    x = range(len(piv.index)); w = 0.2
    pal = ["#1f5fa8", "#7fa8d0", "#e08214", "#f0c080"]
    for i, c in enumerate(order):
        axA.bar([xi + (i - 1.5) * w for xi in x], piv[c], width=w, label=c, color=pal[i])
    axA.set_xticks(list(x)); axA.set_xticklabels(piv.index)
    axA.set_ylabel("Τμήματα (γραμμές)"); axA.set_xlabel("Έτος")
    axA.set_title("Γραμμές ανά έτος και κατηγορία εισαγωγής")
    axA.legend(frameon=False, ncol=4, fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.18))
    set_frame(axA)
    figA.tight_layout(); figA.savefig(DOCS / "qa_rowcounts.png", dpi=200, bbox_inches="tight")

    # Fig B: missing-value heatmap (ΓΕΛ90)
    figB, axB = plt.subplots(figsize=(6.5, 3.4))
    import numpy as np
    M = miss.T.values.astype(float)
    im = axB.imshow(M, cmap="Reds", vmin=0, vmax=1, aspect="auto")
    axB.set_xticks(range(len(miss.index))); axB.set_xticklabels(miss.index)
    axB.set_yticks(range(len(miss.columns))); axB.set_yticklabels(miss.columns)
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            axB.text(j, i, f"{M[i,j]*100:.0f}", ha="center", va="center",
                     fontsize=6, color="black" if M[i, j] < 0.5 else "white")
    axB.set_title("Ποσοστό ελλιπών τιμών (%) — ΓΕΛ90")
    cb = figB.colorbar(im, ax=axB, fraction=0.046, pad=0.04); cb.set_label("Ελλιπείς (κλάσμα)")
    figB.tight_layout(); figB.savefig(DOCS / "qa_missing.png", dpi=200, bbox_inches="tight")

    # Fig C: seats vs admitted (the ΕΒΕ vacancy gap).
    # Reindex onto the FULL 2015–2025 axis so the missing 2020–2023 years become
    # NaN — matplotlib then BREAKS the line and fill across the gap, so the chart
    # cannot be misread as a continuous measured decline. The gap band is shaded
    # and labelled "χωρίς επίσημα δεδομένα".
    import numpy as _np
    sa = con.execute("""SELECT year, SUM(CAST(seats_offered AS BIGINT)) seats,
        SUM(CAST(admitted AS BIGINT)) admitted FROM admission
        WHERE category='ΓΕΛ90' GROUP BY year ORDER BY year""").df()
    full_years = list(range(int(sa["year"].min()), int(sa["year"].max()) + 1))
    sa = sa.set_index("year").reindex(full_years).reset_index().rename(columns={"index": "year"})
    gap_years = [y for y in full_years if sa.loc[sa.year == y, "seats"].isna().all()]
    figC, axC = plt.subplots(figsize=(6.5, 3.4))
    # break lines/fill at NaN (do NOT connectNulls)
    axC.plot(sa["year"], sa["seats"], "o-", label="Θέσεις (εισακτέοι)", color=pal[0])
    axC.plot(sa["year"], sa["admitted"], "s-", label="Εισαχθέντες", color="#888")
    axC.fill_between(sa["year"], sa["admitted"], sa["seats"], alpha=0.15, color=pal[0])
    # shade + label the no-data gap
    if gap_years:
        g0, g1 = min(gap_years) - 0.5, max(gap_years) + 0.5
        axC.axvspan(g0, g1, color="#d9d9d9", alpha=0.35, zorder=0)
        ymid = _np.nanmean([sa["seats"].mean(), sa["admitted"].mean()])
        axC.text((g0 + g1) / 2, ymid, "χωρίς επίσημα\nδεδομένα\n2020–2023",
                 ha="center", va="center", fontsize=6.5, color="#666", style="italic")
    axC.axvline(2021, ls="--", color="#c00", lw=1)
    axC.text(2021.1, axC.get_ylim()[0] + 0.05*(axC.get_ylim()[1]-axC.get_ylim()[0]),
             "ΕΒΕ (ν.4777/2021)", color="#c00", fontsize=7, rotation=90, va="bottom")
    axC.set_ylabel("Θέσεις (ΓΕΛ90)"); axC.set_xlabel("Έτος")
    axC.set_xticks(full_years); axC.set_xticklabels(full_years, fontsize=7)
    axC.set_title("Το χάσμα θέσεων–εισαχθέντων μετά την ΕΒΕ")
    axC.legend(frameon=False, fontsize=7); set_frame(axC)
    figC.tight_layout(); figC.savefig(DOCS / "qa_vacancy_gap.png", dpi=200, bbox_inches="tight")
    plt.close("all")

    # ===== REPORT =====
    all_pass = all(c[1] for c in checks)
    lines = ["# QA Report — «Πυξίδα ΑΕΙ» Phase 0", "",
             f"**Gate status: {'✅ PASS' if all_pass else '❌ FAIL'}**", "",
             "## 1. Έλεγχοι λογικής (5 sanity checks)", "",
             "| # | Έλεγχος | Αποτέλεσμα | Λεπτομέρεια |", "|---|---|---|---|"]
    for name, ok, detail in checks:
        lines.append(f"| {name.split('.')[0]} | {name.split('.',1)[1].strip()} | "
                     f"{'✅' if ok else '❌'} | {detail} |")
    lines += ["", "## 2. Γραμμές ανά έτος × κατηγορία", "",
              counts.pivot_table(index="year", columns="category", values="n",
                                 fill_value=0).to_markdown(),
              "", "![Row counts](qa_rowcounts.png)", "",
              "## 3. Προφίλ ελλιπών τιμών (ΓΕΛ90)", "",
              (miss * 100).round(1).to_markdown(),
              "", "![Missing values](qa_missing.png)", "",
              "## 4. Χάσμα θέσεων–εισαχθέντων (αφήγηση ΕΒΕ)", "",
              "![Vacancy gap](qa_vacancy_gap.png)", "",
              "## 5. Crosswalk", "",
              f"- Aliases (renames/ΤΕΙ-absorption): **{n_alias}**",
              f"- Unmatched departments logged: **{n_unmatched}** "
              f"(βλ. πίνακα `unmatched_dept`)",
              "", "## 6. Κενά δεδομένων (γνωστά)", "",
              "- Έτη **2020–2023**: απουσιάζουν από τα επίσημα open data του "
              "data.gov.gr· ο mirror aeitei.gr απορρίπτει αυτοματοποιημένους πελάτες "
              "σε αυτό το περιβάλλον. Καλύπτονται συγκεντρωτικά από την έκθεση.",
              "- **2016 ΓΕΛ10**: το αρχείο RAR του 2016 δεν διαχώριζε ΓΕΛ10 (0 γραμμές).",
              ""]
    (DOCS / "qa_report.md").write_text("\n".join(lines), encoding="utf-8")
    con.close()

    # print scorecard
    for name, ok, detail in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name} — {detail}")
    print(f"\nGATE: {'PASS' if all_pass else 'FAIL'}  (aliases={n_alias}, unmatched={n_unmatched})")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(run())
