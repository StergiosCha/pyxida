import { NavLink, Route, Routes } from "react-router-dom";
import Home from "./pages/Home";
import Search from "./pages/Search";
import DepartmentPage from "./pages/DepartmentPage";
import Dashboard from "./pages/Dashboard";
import Calculator from "./pages/Calculator";
import Nppe from "./pages/Nppe";
import Compare from "./pages/Compare";
import Advisor from "./pages/Advisor";
import Simulator from "./pages/Simulator";
import RegionMap from "./pages/RegionMap";
import Intent from "./pages/Intent";
import Desert from "./pages/Desert";
import PrivatePath from "./pages/PrivatePath";
import Projection from "./pages/Projection";
import ClassMap from "./pages/ClassMap";
import Places from "./pages/Places";

const nav = [
  { to: "/", label: "Αρχική", end: true },
  { to: "/anazitisi", label: "Αναζήτηση τμημάτων" },
  { to: "/statistika", label: "Στατιστικά" },
  { to: "/sygkrisi", label: "Σύγκριση προγραμμάτων" },
  { to: "/ypologistis", label: "Υπολογιστής μορίων" },
  { to: "/nppe", label: "Μη κρατικά (ΝΠΠΕ)" },
  { to: "/poleis", label: "Πόλεις & Ιδρύματα" },
  { to: "/chartis", label: "Χάρτης κινδύνου" },
  { to: "/erimos", label: "Πανεπιστημιακή έρημος" },
  { to: "/prothesi", label: "Δημόσιο vs ιδιωτικό" },
  { to: "/idiotiko-monopati", label: "Το ιδιωτικό μονοπάτι" },
  { to: "/provoli-2030", label: "Προβολή 2030" },
  { to: "/ploutos", label: "Πλούτος & πληρότητα" },
  { to: "/prosomoiotis", label: "Προσομοιωτής 2026" },
  { to: "/symvoulos", label: "Σύμβουλος" },
];

export default function App() {
  return (
    <>
      <header className="top">
        <div className="app">
          <h1>🧭 Πυξίδα ΑΕΙ</h1>
          <nav>
            {nav.map((n) => (
              <NavLink key={n.to} to={n.to} end={n.end}
                className={({ isActive }) => (isActive ? "active" : "")}>
                {n.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="app">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/anazitisi" element={<Search />} />
          <Route path="/tmima/:code" element={<DepartmentPage />} />
          <Route path="/statistika" element={<Dashboard />} />
          <Route path="/ypologistis" element={<Calculator />} />
          <Route path="/sygkrisi" element={<Compare />} />
          <Route path="/nppe" element={<Nppe />} />
          <Route path="/poleis" element={<Places />} />
          <Route path="/prosomoiotis" element={<Simulator />} />
          <Route path="/chartis" element={<RegionMap />} />
          <Route path="/erimos" element={<Desert />} />
          <Route path="/prothesi" element={<Intent />} />
          <Route path="/idiotiko-monopati" element={<PrivatePath />} />
          <Route path="/provoli-2030" element={<Projection />} />
          <Route path="/ploutos" element={<ClassMap />} />
          <Route path="/symvoulos" element={<Advisor />} />
        </Routes>
        <footer className="muted small" style={{ marginTop: 40, borderTop: "1px solid var(--line)", paddingTop: 16 }}>
          Πηγή δεδομένων: <a href="https://data.gov.gr" target="_blank" rel="noreferrer">data.gov.gr</a> (Υπ. Παιδείας),
          βάσεις εισαγωγής 2015–2025. Κάθε αριθμός είναι ιχνηλατήσιμος στο αρχείο και το έτος προέλευσης.
          Τα έτη 2020–2023 απουσιάζουν από τα επίσημα ανοικτά δεδομένα.
        </footer>
      </main>
    </>
  );
}
