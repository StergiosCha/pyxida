import { useEffect, useState } from "react";
import { ScatterChart, Scatter, XAxis, YAxis, ZAxis, Tooltip, CartesianGrid, ResponsiveContainer } from "recharts";
import { api, WFResp } from "../lib/api";
import { ErrorBox, Loading } from "../lib/hooks";
import { fmtInt } from "../lib/format";

// «Πλούτος & πληρότητα» — περιφερειακή συσχέτιση GDP/κατοίκου ↔ πληρότητας.
// Αναφέρει τον ΠΡΑΓΜΑΤΙΚΟ συντελεστή, με ρητή προειδοποίηση οικολογικού σφάλματος.
export default function ClassMap() {
  const [d, setD] = useState<WFResp | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api.statsWealthFill().then(setD).catch((e) => setError(String(e))); }, []);

  if (error) return <div className="page"><ErrorBox error={error} /></div>;
  if (!d) return <div className="page"><Loading /></div>;

  const pts = d.regions.map((r) => ({ x: r.gdp_per_capita, y: r.fill * 100,
    z: r.n, region: r.region, metro: r.is_metro }));

  return (
    <div className="page">
      <h1>Πλούτος περιφέρειας & πληρότητα σχολών</h1>
      <p className="lead">
        Κατά κοινή αφήγηση, οι πλούσιες περιοχές γεμίζουν τις σχολές τους και η φτωχή περιφέρεια
        αδειάζει. Ελέγχουμε το με πραγματικά δεδομένα: GDP/κατοίκου (Eurostat) vs πληρότητα (data.gov.gr).
      </p>

      <div className={"wf-headline " + (d.significant_05 ? "wf-sig" : "wf-nsig")}>
        {d.finding}
      </div>

      <ResponsiveContainer width="100%" height={340}>
        <ScatterChart margin={{ top: 10, right: 20, bottom: 40, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
          <XAxis type="number" dataKey="x" name="GDP/κάτοικο" unit="€" fontSize={12}
            label={{ value: "GDP/κάτοικο (€)", position: "insideBottom", offset: -25, fontSize: 12 }} />
          <YAxis type="number" dataKey="y" name="Πληρότητα" unit="%" fontSize={12}
            label={{ value: "Πληρότητα %", angle: -90, position: "insideLeft", fontSize: 12 }} />
          <ZAxis type="number" dataKey="z" range={[40, 300]} name="τμήματα" />
          <Tooltip cursor={{ strokeDasharray: "3 3" }}
            formatter={(v: number, n: string) => [n === "Πληρότητα" ? `${v.toFixed(0)}%` : fmtInt(v), n]}
            labelFormatter={() => ""}
            content={({ payload }) => payload && payload[0] ? (
              <div className="wf-tip">
                <b>{(payload[0].payload as {region:string}).region}</b><br />
                GDP €{fmtInt((payload[0].payload as {x:number}).x)}<br />
                Πληρότητα {((payload[0].payload as {y:number}).y).toFixed(0)}%
              </div>) : null} />
          <Scatter data={pts.filter((p) => !p.metro)} fill="#c0392b" name="περιφέρεια" />
          <Scatter data={pts.filter((p) => p.metro)} fill="#1f5fa8" name="μητρόπολη" />
        </ScatterChart>
      </ResponsiveContainer>

      <p className="disclaimer"><b>Προσοχή — οικολογικό σφάλμα:</b> {d.caveat}</p>
    </div>
  );
}
