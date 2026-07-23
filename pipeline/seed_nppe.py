"""
Phase 2 · seed_nppe.py — ΝΠΠΕ (Νομικά Πρόσωπα Πανεπιστημιακής Εκπαίδευσης,
ν.5094/2024) seed. Hand-curated STRICTLY from the research report §4.

FIDELITY RULES (each field traces to the report; nothing is invented):
  • Institution / parent names verbatim from the report's "Four licensed for
    2025-2026" list: UNIC Athens (University of Nicosia, Cyprus — Elliniko/
    Athens); CITY / University of York Europe Campus (Thessaloniki); The
    University of Keele, Greece (Athens); Αμερικανικό Πανεπιστήμιο Ανατόλια
    (The Open University — Thessaloniki).
  • Programs: ONLY UNIC Athens has a report-stated program list ("five
    programs: Ιατρική, Φαρμακευτική, Διοίκηση Επιχειρήσεων, Ψυχολογία,
    Νομική"). For York/Keele/Anatolia the report gives NO program list, so we
    seed a single institution-level row and set program specifics to unknown —
    we do NOT invent programs.
  • Tuition: report gives a SECTOR range €9,000–€27,500/yr and UNIC-specific
    figures only (€15,480/yr EU most schools; Medicine €27,000 EU / €28,980
    intl). For non-UNIC institutions we have NO per-program tuition → NULL, with
    the sector range recorded in the note. We do NOT invent per-program fees.
  • Certification: the report gives ONE sector date — "24 certified by 29 Oct
    2025". We use 2025-10-29 for all and DO NOT invent per-institution dates.
    York Law and Keele Law were NOT certified for 2025-26 (must reapply);
    UNIC Athens Law WAS certified — recorded in notes.
  • Enrollment: no official total ("εκατοντάδες"); the only press figure is
    UNIC Athens ≈300 across five programs (News24/7). We record it once at the
    institution level with enrollment_is_official=FALSE and the "850 = dorm
    rooms, not enrolment" clarification. Not split per program.

Run:  python -m pipeline.seed_nppe   (inserts into an existing pyxida.duckdb)
"""
from __future__ import annotations
from pathlib import Path
import duckdb

DB = Path(__file__).resolve().parent.parent / "data" / "pyxida.duckdb"

CERT_DATE = "2025-10-29"   # sector-wide: "24 certified by 29 Oct 2025" (report §4)
SECTOR_RANGE = "Εύρος τομέα €9.000–€27.500/έτος (έκθεση)· δεν δίνονται ανά πρόγραμμα δίδακτρα."

# (institution, parent_uni, city, program, degree_years, tuition_eu,
#  tuition_intl, certified, certified_date, enrollment, enrollment_is_official,
#  public_analog_dept, note)
NPPE = [
    # ── UNIC Athens: five report-stated programs ────────────────────────────
    ("UNIC Athens (Παν. Λευκωσίας)", "University of Nicosia (Cyprus)", "Αθήνα (Ελληνικό)",
     "Ιατρική", 6, 27000, 28980, True, CERT_DATE,
     300, False, "ΙΑΤΡΙΚΗΣ (δημόσια)",
     "Ιατρική €27.000/έτος ΕΕ, €28.980 εκτός ΕΕ (έκθεση). UNIC Athens: ≈300 φοιτητές "
     "συνολικά σε 5 προγράμματα, Νοέμβριος 2025 (δημοσιεύματα, News24/7)· το «850» "
     "αφορά δωμάτια εστίας, όχι εγγραφές."),
    ("UNIC Athens (Παν. Λευκωσίας)", "University of Nicosia (Cyprus)", "Αθήνα (Ελληνικό)",
     "Φαρμακευτική", 5, 15480, None, True, CERT_DATE,
     None, False, "ΦΑΡΜΑΚΕΥΤΙΚΗΣ (δημόσια)", "Δίδακτρα ΕΕ €15.480/έτος (έκθεση, «most schools»)."),
    ("UNIC Athens (Παν. Λευκωσίας)", "University of Nicosia (Cyprus)", "Αθήνα (Ελληνικό)",
     "Διοίκηση Επιχειρήσεων", 4, 15480, None, True, CERT_DATE,
     None, False, "ΟΡΓΑΝΩΣΗΣ & ΔΙΟΙΚΗΣΗΣ ΕΠΙΧΕΙΡΗΣΕΩΝ (δημόσια)", "Δίδακτρα ΕΕ €15.480/έτος (έκθεση)."),
    ("UNIC Athens (Παν. Λευκωσίας)", "University of Nicosia (Cyprus)", "Αθήνα (Ελληνικό)",
     "Ψυχολογία", 4, 15480, None, True, CERT_DATE,
     None, False, "ΨΥΧΟΛΟΓΙΑΣ (δημόσια)", "Δίδακτρα ΕΕ €15.480/έτος (έκθεση)."),
    ("UNIC Athens (Παν. Λευκωσίας)", "University of Nicosia (Cyprus)", "Αθήνα (Ελληνικό)",
     "Νομική", 4, 15480, None, True, CERT_DATE,
     None, False, "ΝΟΜΙΚΗΣ (δημόσια)", "Η Νομική UNIC Athens ΠΙΣΤΟΠΟΙΗΘΗΚΕ για 2025-26 (έκθεση). "
     "Δίδακτρα ΕΕ €15.480/έτος."),
    # ── York / Keele / Anatolia: institution-level only (no program list in report) ──
    ("CITY / University of York Europe Campus", "University of York (UK)", "Θεσσαλονίκη",
     "Προπτυχιακά προγράμματα (δεν προσδιορίζονται στην έκθεση)", 4, None, None, True, CERT_DATE,
     None, False, None,
     "Η Νομική York ΔΕΝ πιστοποιήθηκε για 2025-26 (επανυποβολή για 2026-27). " + SECTOR_RANGE),
    ("The University of Keele, Greece", "Keele University (UK)", "Αθήνα",
     "Προπτυχιακά προγράμματα (δεν προσδιορίζονται στην έκθεση)", 4, None, None, True, CERT_DATE,
     None, False, None,
     "Η Νομική Keele ΔΕΝ πιστοποιήθηκε για 2025-26 (επανυποβολή για 2026-27). " + SECTOR_RANGE),
    ("Αμερικανικό Πανεπιστήμιο Ανατόλια", "The Open University", "Θεσσαλονίκη",
     "Προπτυχιακά προγράμματα (δεν προσδιορίζονται στην έκθεση)", 4, None, None, True, CERT_DATE,
     None, False, None,
     "Μητρικό «The Open University» (έκθεση §4). " + SECTOR_RANGE),
]


def seed():
    con = duckdb.connect(str(DB))
    con.execute("DELETE FROM nppe_program")
    for i, row in enumerate(NPPE, start=1):
        con.execute("""INSERT INTO nppe_program
            (nppe_id, institution, parent_uni, city, program, degree_years,
             tuition_eu, tuition_intl, certified, certified_date, enrollment,
             enrollment_is_official, public_analog_dept, source_id, note)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [i, *row[:12], None, row[12]])   # ..public_analog_dept, source_id=None, note
    n = con.execute("SELECT COUNT(*) FROM nppe_program").fetchone()[0]
    con.close()
    return n


if __name__ == "__main__":
    print("ΝΠΠΕ rows seeded:", seed())
