import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useAsync, Loading, ErrorBox } from "../lib/hooks";
import { fmtInt } from "../lib/format";

export default function Home() {
  const { data: meta, error, loading } = useAsync(() => api.meta(), []);
  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  if (!meta) return null;
  const c = meta.counts;
  return (
    <>
      <div className="card">
        <h2>Οδηγός Πανελλαδικών Εξετάσεων</h2>
        <p className="muted">
          Δέκα χρόνια επίσημων βάσεων εισαγωγής (2015–2025), με πλήρη κάλυψη του καθεστώτος
          <strong> ΕΒΕ</strong> (Ελάχιστη Βάση Εισαγωγής, ν.4777/2021), των <strong>κενών θέσεων</strong>,
          των τμημάτων σε κίνδυνο και των νέων <strong>μη κρατικών πανεπιστημίων (ΝΠΠΕ, ν.5094/2024)</strong>.
        </p>
      </div>

      <div className="grid cols-4">
        <div className="card stat"><div className="num">{fmtInt(c.departments)}</div><div className="lbl">τμήματα</div></div>
        <div className="card stat"><div className="num">{fmtInt(c.institutions)}</div><div className="lbl">ιδρύματα</div></div>
        <div className="card stat"><div className="num">{fmtInt(c.admission_rows)}</div><div className="lbl">εγγραφές βάσεων</div></div>
        <div className="card stat"><div className="num">{meta.years.length}</div><div className="lbl">έτη δεδομένων</div></div>
      </div>

      <div className="grid cols-2">
        <Link to="/anazitisi" className="card" style={{ display: "block" }}>
          <h3>🔎 Αναζήτηση & προφίλ τμήματος</h3>
          <p className="muted small">Φιλτράρισμα ανά πεδίο, πόλη, ίδρυμα και εύρος μορίων· δεκαετής ιστορία βάσης, εισακτέοι, πληρότητα και ΕΒΕ.</p>
        </Link>
        <Link to="/statistika" className="card" style={{ display: "block" }}>
          <h3>📊 Στατιστικά & κενές θέσεις</h3>
          <p className="muted small">Τάσεις ανά πεδίο, heatmap κενών θέσεων 2015–2025 και δείκτης «τμήματα σε κίνδυνο».</p>
        </Link>
        <Link to="/ypologistis" className="card" style={{ display: "block" }}>
          <h3>🧮 Υπολογιστής μορίων + ΕΒΕ</h3>
          <p className="muted small">Δώστε βαθμούς ανά μάθημα, υπολογίστε μόρια ανά πεδίο και δείτε σε ποια τμήματα είστε επιλέξιμοι — με την ΕΒΕ ως αυστηρό κατώφλι.</p>
        </Link>
        <Link to="/nppe" className="card" style={{ display: "block" }}>
          <h3>🏛️ Μη κρατικά πανεπιστήμια (ΝΠΠΕ)</h3>
          <p className="muted small">Τα αδειοδοτημένα ιδρύματα, προγράμματα και δίδακτρα (€9.000–€27.500), δίπλα-δίπλα με τις δημόσιες εναλλακτικές.</p>
        </Link>
      </div>

      <div className="disclaimer">
        Οι προβλέψεις βάσεων και οι δείκτες κινδύνου συνοδεύονται πάντα από διαστήματα αβεβαιότητας.
        Το μηχανογραφικό παραμένει απόφαση του υποψηφίου· η εφαρμογή δεν εγγυάται εισαγωγή.
      </div>
    </>
  );
}
