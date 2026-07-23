// Greek-locale formatting helpers.
export const fmtInt = (n: number | null | undefined) =>
  n == null ? "—" : new Intl.NumberFormat("el-GR").format(Math.round(n));

export const fmtMoria = (n: number | null | undefined) =>
  n == null ? "—" : new Intl.NumberFormat("el-GR").format(Math.round(n));

export const fmtPct = (x: number | null | undefined, digits = 1) =>
  x == null ? "—" : `${(x * 100).toFixed(digits)}%`;

export const fmtEuro = (n: number | null | undefined) =>
  n == null ? "—" : new Intl.NumberFormat("el-GR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(n);

export const FIELD_COLORS: Record<string, string> = {
  "1ο": "#1f5fa8", "2ο": "#2e8b57", "3ο": "#e08214", "4ο": "#8f4fa8",
};

export const riskColor = (band: string) =>
  band === "υψηλός" ? "#c0392b" : band === "μέτριος" ? "#e08214" : "#2e8b57";
