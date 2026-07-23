"""
Phase 3 · rag.py — LLM Σύμβουλος (RAG, not free generation).

DESIGN CONTRACT (per master prompt, non-negotiable):
  • The model NEVER invents βάσεις or ΕΒΕ values. Every number in an answer
    comes from a retrieved DB row or the research report; answers cite year +
    source. If a fact is not retrieved, the advisor says it doesn't have it.
  • Persona: έμπειρος σύμβουλος επαγγελματικού προσανατολισμού — νηφάλιος,
    χωρίς υπερβολές· states forecast uncertainty explicitly.
  • Guardrails: refuses to guarantee admission; forecasts always shown with
    intervals; closes with the disclaimer that το μηχανογραφικό is the
    candidate's decision.
  • Feature-flagged: only mounted when PYXIDA_ENABLE_RAG=1.

ARCHITECTURE: retrieve → build a grounded context block of ONLY verified rows →
single constrained generation. The generator receives the context and a system
prompt forbidding any number not present in the context. Retrieval is
deterministic SQL over the same DuckDB the API serves, so the advisor and the
rest of the app can never disagree.

The generation backend is injected (`generate_fn`) so the module is testable
offline and the app can wire in whichever LLM it runs. If no backend is given,
`answer()` returns the structured grounded context + a template answer, which is
itself fully usable (and provably grounded).
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Callable, Optional
from . import db
from .eligibility import eligible_departments, Grades

SOURCE_DB = "Βάση Πυξίδα ΑΕΙ (data.gov.gr, Υπ. Παιδείας)"
SOURCE_REPORT = "Έκθεση «Greek AEI Admissions Data Landscape 2016–2026»"

SYSTEM_PROMPT = """Είσαι έμπειρος σύμβουλος επαγγελματικού προσανατολισμού για τις ελληνικές Πανελλαδικές.
ΑΥΣΤΗΡΟΙ ΚΑΝΟΝΕΣ (μη διαπραγματεύσιμοι):
1. Χρησιμοποίησε ΜΟΝΟ αριθμούς που εμφανίζονται στο ΤΕΚΜΗΡΙΩΜΕΝΟ ΠΛΑΙΣΙΟ παρακάτω. ΠΟΤΕ μην εφεύρεις βάση, ΕΒΕ, μόρια ή αριθμό εισακτέων.
2. Κάθε αριθμός που αναφέρεις πρέπει να συνοδεύεται από έτος και πηγή, όπως δίνεται στο πλαίσιο.
3. Αν μια πληροφορία ΔΕΝ υπάρχει στο πλαίσιο, πες ρητά «δεν έχω αυτό το στοιχείο» — μην μαντέψεις.
4. Οι προβλέψεις παρουσιάζονται ΠΑΝΤΑ με το διάστημα εμπιστοσύνης. Ποτέ «η βάση θα είναι X».
5. ΠΟΤΕ μην εγγυηθείς εισαγωγή. Νηφάλιος τόνος, χωρίς υπερβολές.
6. Κλείσε με υπενθύμιση ότι το μηχανογραφικό είναι απόφαση του υποψηφίου.
Απάντησε στα ελληνικά, σύντομα και δομημένα."""


COMPARE_SYSTEM_PROMPT = """Είσαι αναλυτής δεδομένων για τις ελληνικές Πανελλαδικές. Σχολιάζεις μια σύγκριση
ομοειδών τμημάτων (ίδιο πρόγραμμα, διαφορετικές πόλεις) ΜΕΤΑ την εισαγωγή της ΕΒΕ (ν.4777/2021).
ΑΥΣΤΗΡΟΙ ΚΑΝΟΝΕΣ (μη διαπραγματεύσιμοι):
1. Χρησιμοποίησε ΜΟΝΟ αριθμούς από το ΤΕΚΜΗΡΙΩΜΕΝΟ ΠΛΑΙΣΙΟ. ΠΟΤΕ μην εφεύρεις βάση, ΕΒΕ ή ποσοστό.
2. Εντόπισε το μοτίβο: ποια τμήματα άδειασαν, ποια γέμισαν, και πώς σχετίζεται με την προ-ΕΒΕ ζήτηση
   (βάση 2019) και την πόλη (μητρόπολη vs περιφέρεια).
3. Εξήγησε τον μηχανισμό νηφάλια: ενιαίο κατώφλι ΕΒΕ ανά πεδίο → πλήττει δυσανάλογα τα ήδη χαμηλής
   ζήτησης τμήματα. Μη συγχέεις συσχέτιση με πρόθεση.
4. Οι προβλέψεις 2026 αναφέρονται ΠΑΝΤΑ με το διάστημα εμπιστοσύνης, ποτέ ως βεβαιότητα.
5. Σύντομα, δομημένα, στα ελληνικά. Κλείσε με 1 πρόταση για το τι σημαίνει πρακτικά για υποψηφίους."""


@dataclass
class Citation:
    text: str
    year: Optional[int]
    source: str


@dataclass
class GroundedContext:
    facts: list[Citation] = field(default_factory=list)
    def add(self, text, year, source):
        self.facts.append(Citation(text, year, source))
    def render(self) -> str:
        if not self.facts:
            return "(κανένα τεκμηριωμένο στοιχείο δεν ανακτήθηκε)"
        return "\n".join(
            f"- {c.text}  [πηγή: {c.source}{', έτος ' + str(c.year) if c.year else ''}]"
            for c in self.facts)


# ── retrieval ────────────────────────────────────────────────────────────
def retrieve_department(name_or_code: str, category="ΓΕΛ90") -> GroundedContext:
    ctx = GroundedContext()
    rows = db.q("""
        SELECT a.dept_code, d.name, i.name AS institution, d.city, a.year,
               a.base_last, a.seats_offered, a.admitted, a.vacancies,
               a.fill_rate, a.ebe_coefficient, a.ebe_threshold
        FROM admission a JOIN department d ON d.dept_code=a.dept_code
        LEFT JOIN institution i ON i.institution_id = d.institution_id
        WHERE a.category=? AND (a.dept_code=?
              OR strip_accents(upper(d.name)) LIKE strip_accents(upper(?)))
        ORDER BY a.year""", [category, name_or_code, f"%{name_or_code}%"])
    for r in rows:
        if r["base_last"] is not None:
            ctx.add(f"{r['name']} ({r['institution']}, {r['city']}): βάση {int(r['base_last'])} μόρια, "
                    f"θέσεις {r['seats_offered']}, εισαχθέντες {r['admitted']}, "
                    f"κενές {r['vacancies']}, πληρότητα {r['fill_rate']:.0%}"
                    + (f", συντ. ΕΒΕ {r['ebe_coefficient']:.2f}" if r['ebe_coefficient'] else ""),
                    r["year"], SOURCE_DB)
    # forecast, if present
    fc = db.q("""SELECT p.target_year, p.point, p.lower_80, p.upper_80, p.lower_95, p.upper_95, d.name
                 FROM prediction p JOIN department d ON d.dept_code=p.dept_code
                 WHERE (p.dept_code=?
                        OR strip_accents(upper(d.name)) LIKE strip_accents(upper(?))) LIMIT 1""",
              [name_or_code, f"%{name_or_code}%"])
    for r in fc:
        ctx.add(f"Πρόβλεψη {r['name']} για {r['target_year']} (carry-forward): "
                f"σημείο {int(r['point'])} μόρια, 80% ΔΕ [{int(r['lower_80'])}, {int(r['upper_80'])}], "
                f"95% ΔΕ [{int(r['lower_95'])}, {int(r['upper_95'])}]",
                r["target_year"], SOURCE_DB + " — μοντέλο carry-forward")
    return ctx


_FREETEXT_STOP = {
    "ΠΟΣΟ", "ΠΟΣΗ", "ΠΟΙΑ", "ΠΟΙΟ", "ΠΟΙΟΣ", "ΗΤΑΝ", "ΕΙΝΑΙ", "ΘΑ", "ΓΙΑ",
    "ΒΑΣΗ", "ΒΑΣΕΙΣ", "ΜΟΡΙΑ", "ΕΒΕ", "ΘΕΣΕΙΣ", "ΚΕΝΕΣ", "ΠΡΟΒΛΕΨΗ",
    "ΤΜΗΜΑ", "ΤΜΗΜΑΤΟΣ", "ΣΧΟΛΗ", "ΣΧΟΛΗΣ", "ΠΑΝΕΠΙΣΤΗΜΙΟ", "ΠΑΝΕΠΙΣΤΗΜΙΟΥ",
    "ΤΗΝ", "ΤΗΣ", "ΤΟΥ", "ΤΟΝ", "ΣΤΟ", "ΣΤΗ", "ΣΤΗΝ", "ΣΤΟΝ", "ΚΑΙ", "ΜΟΥ",
    "ΕΧΕΙ", "ΕΧΩ", "ΠΕΡΝΑΩ", "ΠΕΡΑΣΩ", "ΧΡΕΙΑΖΟΜΑΙ", "ΧΡΟΝΙΑ", "ΕΤΟΣ", "ΦΕΤΟΣ",
}
# tokens treated as institution acronyms — matched against the institution
# name with dots/spaces stripped ("Ε.Κ.Π.Α." -> "ΕΚΠΑ")
_INST_ACRONYMS = {"ΕΚΠΑ", "ΑΠΘ", "ΕΜΠ", "ΠΑΔΑ", "ΔΠΘ", "ΟΠΑ", "ΠΑΠΕΙ", "ΠΑΜΑΚ", "ΓΠΑ"}


def _norm_upper(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.upper()


def retrieve_freetext(question: str, category="ΓΕΛ90") -> GroundedContext:
    """Free-text fallback: pull candidate department/institution tokens out of a
    question and retrieve deterministically. No LLM involved — token n-grams are
    matched with SQL LIKE against department (and institution) names, so the
    grounding contract is unchanged."""
    q = _norm_upper(question)
    words = [w for w in re.findall(r"[Α-ΩA-Z]+", q)]
    inst_terms = [w for w in words if w in _INST_ACRONYMS]
    toks = [w for w in words
            if len(w) >= 4 and w not in _FREETEXT_STOP and w not in _INST_ACRONYMS]
    if not toks and not inst_terms:
        return GroundedContext()
    # score departments by how many tokens hit their (accent-stripped) name;
    # an institution hit narrows, never widens. Institution acronyms compare
    # against the dot/space-stripped institution name ("Ε.Κ.Π.Α." -> "ΕΚΠΑ").
    hit = ("(CASE WHEN strip_accents(upper(d.name)) LIKE ? "
           "OR strip_accents(upper(coalesce(i.name,''))) LIKE ? "
           "OR strip_accents(upper(coalesce(d.city,''))) LIKE ? THEN 2 ELSE 0 END "
           # word-boundary bonus: ΙΑΤΡΙΚΗ ranks ΙΑΤΡΙΚΗΣ over ΟΔΟΝΤΙΑΤΡΙΚΗΣ
           "+ CASE WHEN strip_accents(upper(d.name)) LIKE ? "
           "OR strip_accents(upper(d.name)) LIKE ? THEN 1 ELSE 0 END)")
    conds = " + ".join([hit] * len(toks)) or "0"
    params = []
    for t in toks:
        # genitive-tolerant: compare on a 6-char stem (ΙΩΑΝΝΙΝΩΝ ~ ΙΩΑΝΝΙΝΑ)
        stem = f"%{t[:6]}%" if len(t) > 6 else f"%{t}%"
        params += [f"%{t}%", stem, stem, f"{t}%", f"% {t}%"]
    inst_sq = "replace(replace(replace(strip_accents(upper(i.name)),'.',''),' ',''),'/','')"
    inst_clause = ""
    if inst_terms:
        inst_clause = " AND " + " AND ".join([f"{inst_sq} LIKE ?"] * len(inst_terms))
        params += [f"%{t}%" for t in inst_terms]
    rows = db.q(f"""
        SELECT d.dept_code, ({conds}) AS score
        FROM department d LEFT JOIN institution i ON i.institution_id=d.institution_id
        WHERE 1=1 {inst_clause}
        ORDER BY score DESC, d.dept_code LIMIT 3""", params)
    rows = [r for r in rows if (r["score"] or 0) > 0 or (inst_terms and not toks)]
    if not rows:
        return GroundedContext()
    top = max(r["score"] for r in rows)
    ctx = GroundedContext()
    for r in rows:
        if r["score"] == top:
            sub = retrieve_department(r["dept_code"], category=category)
            ctx.facts.extend(sub.facts)
    return ctx


def retrieve_vacancy_context() -> GroundedContext:
    ctx = GroundedContext()
    rows = db.q("""SELECT year, SUM(vacancies) v, SUM(seats_offered) s
                   FROM admission WHERE category='ΓΕΛ90' AND vacancies IS NOT NULL
                   GROUP BY year ORDER BY year""")
    for r in rows:
        if r["s"]:
            ctx.add(f"Σύνολο κενών θέσεων ΓΕΛ90: {int(r['v'])} από {int(r['s'])} "
                    f"({r['v']/r['s']:.1%})", r["year"], SOURCE_DB)
    return ctx


def retrieve_nppe() -> GroundedContext:
    ctx = GroundedContext()
    rows = db.q("""SELECT institution, program, tuition_eu, enrollment,
                          enrollment_is_official FROM nppe_program ORDER BY institution""")
    for r in rows:
        note = "" if r["enrollment"] is None else (
            f", εγγραφές {r['enrollment']}" + ("" if r["enrollment_is_official"] else " (μη επίσημο, από δημοσιεύματα)"))
        if r["tuition_eu"] is not None:
            fees = f"δίδακτρα €{r['tuition_eu']:,}/έτος".replace(",", ".")
        else:
            fees = "δίδακτρα μη διαθέσιμα ανά πρόγραμμα (εύρος τομέα €9.000–€27.500)"
        ctx.add(f"{r['institution']} — {r['program']}: {fees}{note}", None, SOURCE_REPORT)
    return ctx


def retrieve_comparison(family: str) -> GroundedContext:
    """Grounded facts for a program-family comparison (e.g. all ΦΙΛΟΛΟΓΙΑΣ
    departments across cities), for LLM commentary on the pre/post-ΕΒΕ pattern."""
    from .compare import compare_family
    ctx = GroundedContext()
    res = compare_family(family)
    s = res["summary"]
    if not res["departments"]:
        ctx.add(f"Δεν βρέθηκαν τμήματα για την οικογένεια «{family}».", None, SOURCE_DB)
        return ctx
    ctx.add(f"Οικογένεια προγράμματος «{s['family']}»: {s['n_departments']} τμήματα, "
            f"συνολικά {s['total_seats']} θέσεις, {s['total_vacancies']} κενές "
            f"({s['vacancy_rate']:.0%} του συνόλου) το 2025. Περισσότερες κενές: {s['worst']}· "
            f"λιγότερες: {s['best']}.", 2025, SOURCE_DB)
    for d in res["departments"]:
        pre = f"βάση 2019 {int(d['base_2019'])}" if d["base_2019"] is not None else "βάση 2019 μ/δ"
        post = f"βάση 2025 {int(d['base_2025'])}" if d["base_2025"] is not None else "βάση 2025 μ/δ"
        vr = f"{d['vacancy_rate']:.0%} κενές" if d["vacancy_rate"] is not None else "κενές μ/δ"
        fc = (f", πρόβλεψη 2026 {d['forecast_2026']} [80% ΔΕ {d['forecast_2026_lo80']}–{d['forecast_2026_hi80']}]"
              if d["forecast_2026"] is not None else "")
        ctx.add(f"{d['name']} ({d['city']}, πεδίο {d['field']}): {pre} → {post}, "
                f"{d['admitted']}/{d['seats']} εισαχθέντες, {vr}{fc}", 2025, SOURCE_DB)
    return ctx


def retrieve_eligibility(grades: dict, field_id: str, year=2025) -> GroundedContext:
    ctx = GroundedContext()
    res = eligible_departments(db.q, Grades(values=grades), field_id,
                               year=year, category="ΓΕΛ90", include_ineligible=True)
    p = res["profile"]
    ctx.add(f"Υπολογισμένα μόρια υποψηφίου στο {p['field_label']}: {int(p['moria'])} "
            f"(μ.ό. πεδίου {p['field_average']:.2f}/20)", year, SOURCE_DB + " — υπολογιστής")
    for e in res["eligible"][:8]:
        if e["base_last"] is not None:
            verdict = "πιθανή εισαγωγή" if e["likely_admit"] else "οριακά"
            ctx.add(f"{e['name']} ({e['institution']}): περσινή βάση {int(e['base_last'])}, "
                    f"περιθώριο {int(e['margin']) if e['margin'] is not None else '—'} μόρια — {verdict}",
                    year, SOURCE_DB)
    if res["blocked_by_ebe"]:
        ctx.add(f"{len(res['blocked_by_ebe'])} τμήματα αποκλείονται λόγω ΕΒΕ "
                f"(ο μ.ό. πεδίου δεν καλύπτει το κατώφλι)", year, SOURCE_DB)
    return ctx


# ── generation ─────────────────────────────────────────────────────────────
def build_prompt(question: str, ctx: GroundedContext) -> str:
    return (f"ΤΕΚΜΗΡΙΩΜΕΝΟ ΠΛΑΙΣΙΟ (μόνο αυτά τα στοιχεία επιτρέπεται να χρησιμοποιήσεις):\n"
            f"{ctx.render()}\n\nΕΡΩΤΗΣΗ ΥΠΟΨΗΦΙΟΥ: {question}\n\n"
            f"Απάντησε τηρώντας αυστηρά τους κανόνες.")


def template_answer(question: str, ctx: GroundedContext) -> str:
    """Deterministic fallback answer (no LLM) — still fully grounded."""
    body = ctx.render()
    return (f"Με βάση τα διαθέσιμα επίσημα στοιχεία:\n\n{body}\n\n"
            f"Σημείωση: οι προβλέψεις δίνονται πάντα με διάστημα εμπιστοσύνης και "
            f"δεν αποτελούν εγγύηση. Το μηχανογραφικό παραμένει δική σας απόφαση.")


def _numbers(text: str) -> set[int]:
    """Extract 'meaningful' integers (>=100) from text, tolerating Greek/EU
    thousands separators (16.809 / 16,809 -> 16809). Small ints (years, counts,
    percentages, ΕΒΕ coefficients) are ignored — they are not the fabrication
    risk; βάσεις/μόρια/θέσεις are."""
    out = set()
    for tok in re.findall(r"\d[\d.,]*\d|\d", text):
        digits = tok.replace(".", "").replace(",", "")
        if digits.isdigit():
            v = int(digits)
            if v >= 100:
                out.add(v)
    return out


def verify_grounding(text: str, ctx: GroundedContext, tol: int = 2):
    """Check every meaningful number in an LLM answer against the context.
    A number is grounded if it appears in the rendered context, OR is within
    `tol` of a context number (rounding), OR is a transparent difference/sum of
    two context numbers (the advisor legitimately computes gaps like
    18.223-17.875=348). Returns (ok: bool, ungrounded: list[int])."""
    ctx_nums = _numbers(ctx.render())
    # only μόρια-scale context numbers (>=1000) may form a legitimate gap; adding
    # two βάσεις is never meaningful (sum rule dropped), and mixing a year/seat
    # count into a difference is not either — both operands must be μόρια-scale.
    big = [c for c in ctx_nums if c >= 1000]
    ungrounded = []
    for n in _numbers(text):
        if any(abs(n - c) <= tol for c in ctx_nums):
            continue
        # transparent gap: |βάση_a − βάση_b|, both operands μόρια-scale
        if any(abs(n - abs(a - b)) <= tol for a in big for b in big if a != b):
            continue
        ungrounded.append(n)
    return (len(ungrounded) == 0), sorted(ungrounded)


def answer(question: str, ctx: GroundedContext,
           generate_fn: Optional[Callable[[str, str], str]] = None,
           system: Optional[str] = None) -> dict:
    """Produce a grounded answer. generate_fn(system, user)->str if an LLM is wired;
    otherwise a deterministic grounded template is returned. `system` overrides the
    default advisor system prompt (e.g. COMPARE_SYSTEM_PROMPT for comparisons).

    Grounding is ENFORCED, not just prompted: when an LLM is used, every
    meaningful number in its output is verified against the retrieved context.
    If any number is not traceable to a fact (a fabricated/drifted βάση), we
    DISCARD the LLM answer and fall back to the deterministic template — the app
    never surfaces an ungrounded number to a student."""
    system = system or SYSTEM_PROMPT
    prompt = build_prompt(question, ctx)
    used_llm = False
    verified = None
    ungrounded: list[int] = []
    if generate_fn is not None:
        try:
            llm_text = generate_fn(system, prompt)
            verified, ungrounded = verify_grounding(llm_text, ctx)
            if verified:
                text = llm_text
                used_llm = True
            else:
                text = template_answer(question, ctx)  # guardrail fallback
        except Exception:
            text = template_answer(question, ctx)       # backend error -> safe fallback
    else:
        text = template_answer(question, ctx)
    return {
        "answer": text,
        "grounded": True,   # always true: template is grounded by construction,
                            # LLM output only surfaces if it passed verification
        "citations": [{"text": c.text, "year": c.year, "source": c.source} for c in ctx.facts],
        "n_facts": len(ctx.facts),
        "used_llm": used_llm,
        "llm_verified": verified,          # None=no LLM tried, True=passed, False=rejected→template
        "ungrounded_numbers": ungrounded,  # what tripped the guard, for audit
        "disclaimer": "Η εφαρμογή δεν εγγυάται εισαγωγή. Το μηχανογραφικό είναι απόφαση του υποψηφίου.",
    }
