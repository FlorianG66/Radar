"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { PriceChart } from "@/components/PriceChart";
import { AvailabilityBadge, Badge, Button, Card, Input, ScrapeStatusBadge, Select, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { formatDate, formatDateTime, formatPrice, timeAgo } from "@/lib/format";
import type { ChangeEvent, History, Plan, Product, Subscription } from "@/types";

export default function ProductDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);

  const [product, setProduct] = useState<Product | null>(null);
  const [history, setHistory] = useState<History | null>(null);
  const [changes, setChanges] = useState<ChangeEvent[]>([]);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [interval, setInterval] = useState<"hourly" | "daily">("daily");
  const [days, setDays] = useState(90);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    return Promise.all([
      api.get<Product>(`/products/${id}`).then((p) => {
        setProduct(p);
        setError(null);
      }),
      api.get<History>(`/products/${id}/history?days=${days}&interval=${interval}`).then(setHistory),
      api.get<ChangeEvent[]>(`/products/${id}/changes`).then(setChanges).catch(() => undefined),
      api.get<Subscription>("/subscription").then((s) => setPlan(s.plan)),
    ]).catch((e) => setError(errorMessage(e)));
  }, [id, days, interval]);

  useEffect(() => {
    void load();
  }, [load]);

  const p = product;

  const maxHistoryDays = plan?.history_days ?? 30;

  const comparison = useMemo(() => {
    if (!p || !history) return null;
    const own = history.own_prices.length > 0 ? history.own_prices[history.own_prices.length - 1] : null;
    return { own, last: history.snapshots[history.snapshots.length - 1] };
  }, [p, history]);

  if (error) {
    return (
      <Card>
        <p className="text-sm text-red-600">{error}</p>
        <Button variant="outline" className="mt-4" onClick={() => void load()}>
          Réessayer
        </Button>
      </Card>
    );
  }
  if (!p) return <Spinner label="Chargement du produit…" />;

  return (
    <>
      <PageHeader
        title={p.name || "Produit concurrent"}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <a href={p.url} target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:text-indigo-500">
              {p.url}
            </a>
            {p.competitor_name ? <Badge tone="slate">{p.competitor_name}</Badge> : null}
            {p.category ? <Badge tone="violet">{p.category}</Badge> : null}
            <AvailabilityBadge availability={p.last_availability} />
          </span>
        }
        actions={
          <Button variant="outline" size="sm" disabled={busy} onClick={async () => {
            setBusy(true);
            try {
              await api.post(`/products/${p.id}/scrape`);
              await load();
            } catch (e) {
              setError(errorMessage(e));
            } finally {
              setBusy(false);
            }
          }}>
            {busy ? "Scraping…" : "↻ Vérifier maintenant"}
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <InfoCard label="Prix relevé">
          <div className="mt-1 text-2xl font-bold text-slate-900">{formatPrice(p.last_price, p.currency)}</div>
          <p className="mt-1 text-xs text-slate-500">
            {p.variation_pct !== null && p.variation_pct !== undefined ? (
              <span className={p.variation_pct <= 0 ? "text-emerald-600" : "text-amber-600"}>
                {p.variation_pct <= 0 ? "▼" : "▲"} {p.variation_pct.toFixed(1)} %
              </span>
            ) : null}{" "}
            vs précédent relevé
          </p>
        </InfoCard>
        <InfoCard label="Prix de référence">
          <div className="mt-1 text-2xl font-bold text-slate-900">
            {comparison?.own && comparison.own.price != null
              ? formatPrice(comparison.own.price, comparison.own.currency || p.own_currency)
              : "—"}
          </div>
          <p className="mt-1 text-xs text-slate-500">
            {p.own_name ? `Votre prix public (${p.own_name})` : "Renseignez votre prix dans la section « Mon prix »"}
          </p>
        </InfoCard>
        <InfoCard label="Dernière vérification">
          <div className="mt-1 text-2xl font-bold text-slate-900">
            <ScrapeStatusBadge status={p.last_scrape_status} />
          </div>
          <p className="mt-1 text-xs text-slate-500">
            {timeAgo(p.last_checked_at)}
            {p.next_check_at ? ` · prochain relevé ${timeAgo(p.next_check_at)}` : ""}
          </p>
        </InfoCard>
        <InfoCard label="Promo détectée">
          <div className="mt-1 text-2xl font-bold text-slate-900">
            {history && history.snapshots.some((s) => s.in_promotion) ? (
              <span className="text-amber-600">Oui</span>
            ) : (
              <span className="text-slate-400">Non</span>
            )}
          </div>
          <p className="mt-1 text-xs text-slate-500">{p.seen_promotion ? "Historique promo présent" : "Aucune promo sur la période"}</p>
        </InfoCard>
      </div>

      <Card className="mt-6">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-semibold text-slate-900">Évolution du prix</h2>
          <div className="flex items-center gap-2 text-sm">
            <Select value={String(days)} onChange={(e) => setDays(Number(e.target.value))}>
              {[7, 30, 90, 180, 365].map((d) => (
                <option key={d} value={d} disabled={d > maxHistoryDays && maxHistoryDays !== 0}>
                  {d} jours
                </option>
              ))}
            </Select>
            <Select value={interval} onChange={(e) => setInterval(e.target.value as "hourly" | "daily")}>
              <option value="daily">Quotidien</option>
              <option value="hourly">Horaire</option>
            </Select>
          </div>
        </div>
        {comparison ? (
          <PriceChart
            data={(history?.snapshots ?? [])
              .filter((s) => s.price != null)
              .map((s) => ({ at: s.scraped_at, price: s.price as number }))}
            currency={p.currency ?? "EUR"}
          />
        ) : (
          <p className="py-10 text-center text-sm text-slate-400">Aucun relevé de prix pour cette période.</p>
        )}
        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          <div className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
            <span className="font-medium">Prix d&apos;ouverture : </span>
            {formatPrice(history?.snapshots[0]?.price ?? null, p.currency)}
          </div>
          <div className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
            <span className="font-medium">Plus bas : </span>
            {formatPrice(Math.min(...(history?.snapshots.map((s) => s.price ?? Infinity) ?? [Infinity])), p.currency)}
          </div>
          <div className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
            <span className="font-medium">Plus haut : </span>
            {formatPrice(Math.max(...(history?.snapshots.map((s) => s.price ?? -Infinity) ?? [-Infinity])), p.currency)}
          </div>
        </div>
      </Card>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <OwnPriceCard product={p} onSaved={() => void load()} />
        <SettingsCard product={p} onChange={() => void load()} />
      </div>

      {changes.length > 0 ? (
        <Card className="mt-6">
          <div className="mb-2">
            <h2 className="font-semibold text-slate-900">Journal des changements</h2>
          </div>
          <ul className="divide-y divide-slate-100">
            {changes.map((c) => (
              <li key={c.id} className="py-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone="indigo">{c.event_type}</Badge>
                  <span className="text-xs text-slate-400">{formatDateTime(c.created_at)}</span>
                  {c.importance === "high" ? <Badge tone="red">Important</Badge> : null}
                </div>
                <p className="mt-1 text-sm text-slate-700">{c.title}</p>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}
    </>
  );
}

function InfoCard({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <Card>
      <p className="text-sm text-slate-500">{label}</p>
      {children}
    </Card>
  );
}

function OwnPriceCard({ product, onSaved }: { product: Product; onSaved: () => void }) {
  const [name, setName] = useState(product.own_name ?? "");
  const [price, setPrice] = useState(product.own_price != null ? String(product.own_price) : "");
  const [currency, setCurrency] = useState(product.own_currency ?? "EUR");
  const [submitting, setSubmitting] = useState(false);
  const [saved, setSaved] = useState(false);

  async function submit() {
    setSubmitting(true);
    setSaved(false);
    try {
      await api.put(`/products/${product.id}/own-price`, {
        price: price ? Number(price) : null,
        currency,
        ...(name.trim() ? { name: name.trim() } : {}),
      });
      setSaved(true);
      onSaved();
    } catch (e) {
      alert(errorMessage(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <h2 className="font-semibold text-slate-900">Mon prix de référence</h2>
      <p className="mt-1 text-sm text-slate-500">
        Comparez le prix du concurrent au vôtre pour repérer les écarts.
      </p>
      <div className="mt-4 space-y-3">
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">Nom du produit (optionnel)</label>
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="ex. Ma brouette Rouge XL" />
        </div>
        <div className="grid grid-cols-3 gap-3">
          <div className="col-span-2">
            <label className="mb-1 block text-sm font-medium text-slate-700">Prix HT</label>
            <Input type="number" step="0.01" min="0" value={price} onChange={(e) => setPrice(e.target.value)} placeholder="0.00" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Devise</label>
            <Select value={currency} onChange={(e) => setCurrency(e.target.value)}>
              <option value="EUR">€</option>
              <option value="USD">$</option>
              <option value="GBP">£</option>
              <option value="CHF">CHF</option>
            </Select>
          </div>
        </div>
        {saved ? <p className="text-sm text-emerald-600">Enregistré ✓</p> : null}
        <Button onClick={() => void submit()} disabled={submitting}>
          {submitting ? "Enregistrement…" : "Enregistrer"}
        </Button>
      </div>
    </Card>
  );
}

function SettingsCard({ product, onChange }: { product: Product; onChange: () => void }) {
  const [name, setName] = useState(product.name);
  const [category, setCategory] = useState(product.category ?? "");
  const [intervalHours, setIntervalHours] = useState(product.check_interval_hours != null ? String(product.check_interval_hours) : "");
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    setSubmitting(true);
    try {
      await api.patch<Product>(`/products/${product.id}`, {
        name,
        category: category || null,
        check_interval_hours: intervalHours ? Number(intervalHours) : null,
      });
      onChange();
    } catch (e) {
      alert(errorMessage(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <h2 className="font-semibold text-slate-900">Paramètres</h2>
      <div className="mt-4 space-y-3">
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">Nom affiché</label>
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Catégorie</label>
            <Input value={category} onChange={(e) => setCategory(e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Fréquence de vérification (h)</label>
            <Input
              type="number"
              min="1"
              step="1"
              value={intervalHours}
              onChange={(e) => setIntervalHours(e.target.value)}
              placeholder="Héritée du plan"
            />
          </div>
        </div>
        <div className="flex items-center gap-2 pt-1">
          <Button onClick={() => void submit()} disabled={submitting}>
            {submitting ? "Enregistrement…" : "Enregistrer"}
          </Button>
          <p className="text-xs text-slate-400">URL : {product.url} · SKU : {product.sku ?? "—"}</p>
        </div>
      </div>
      <p className="mt-4 border-t border-slate-100 pt-3 text-xs text-slate-500">
        Créé le {formatDate(product.created_at)} · Dernière validation {" "}
        {product.last_scrape_error ? (
          <span className="text-red-600" title={product.last_scrape_error}>
            {product.last_scrape_error.slice(0, 80)}
            {product.last_scrape_error.length > 80 ? "…" : ""}
          </span>
        ) : (
          "sans erreur"
        )}
      </p>
    </Card>
  );
}