const currencyFmt = (currency: string) =>
  new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: currency || "EUR",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

export function formatPrice(
  price: number | null | undefined,
  currency?: string | null,
): string {
  if (price === null || price === undefined) return "—";
  try {
    return currencyFmt(currency || "EUR").format(price);
  } catch {
    return `${price.toLocaleString("fr-FR")} ${currency ?? ""}`.trim();
  }
}

export function formatPercent(pct: number | null | undefined): string {
  if (pct === null || pct === undefined || Number.isNaN(pct)) return "";
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toLocaleString("fr-FR", { maximumFractionDigits: 1 })}%`;
}

const dateFmt = new Intl.DateTimeFormat("fr-FR", {
  day: "2-digit",
  month: "short",
  year: "numeric",
});

const datetimeFmt = new Intl.DateTimeFormat("fr-FR", {
  day: "2-digit",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return dateFmt.format(new Date(iso));
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return datetimeFmt.format(new Date(iso));
}

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "jamais";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diff / 60000);
  if (mins < 1) return "à l'instant";
  if (mins < 60) return `il y a ${mins} min`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `il y a ${hours} h`;
  const days = Math.round(hours / 24);
  return `il y a ${days} j`;
}

export const AVAILABILITY_LABELS: Record<string, string> = {
  in_stock: "En stock",
  out_of_stock: "Rupture",
  preorder: "Précommande",
};

export const SCRAPE_STATUS_LABELS: Record<string, string> = {
  pending: "En attente",
  ok: "OK",
  error: "Erreur",
  disabled: "Désactivé",
};

export const EVENT_IMPORTANCE_LABELS: Record<string, string> = {
  high: "Importante",
  medium: "Moyenne",
  low: "Mineure",
};