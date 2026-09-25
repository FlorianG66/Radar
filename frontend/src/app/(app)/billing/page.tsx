"use client";

import { useCallback, useEffect, useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { Badge, Button, Card, Spinner } from "@/components/ui";
import { API_URL, api, errorMessage } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { Plan, Subscription } from "@/types";

export default function BillingPage() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [sub, setSub] = useState<Subscription | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    Promise.all([
      api.get<Plan[]>("/subscription/plans").then(setPlans),
      api.get<Subscription>("/subscription").then((s) => {
        setSub(s);
        setError(null);
      }),
    ]).catch((e) => setError(errorMessage(e)));
  }, []);

  useEffect(() => void load(), [load]);

  async function choose(plan: string) {
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<{ url: string }>("/subscription/checkout", {
        plan,
        success_url: `${window.location.origin}/billing?success=1`,
        cancel_url: `${window.location.origin}/billing?cancelled=1`,
      });
      if (res.url) window.location.assign(res.url);
    } catch (e) {
      const msg = errorMessage(e);
      if (window.confirm(`${msg}\n\nActiver le plan directement ? (mode démo)`)) {
        try {
          await api.post<Subscription>("/subscription/dev-assign", { plan });
          void load();
        } catch (e2) {
          setError(errorMessage(e2));
        }
      } else {
        setError(msg);
      }
    } finally {
      setBusy(false);
    }
  }

  if (error) {
    return (
      <div className="space-y-4">
        <Card>
          <p className="text-sm text-red-600">{error}</p>
        </Card>
        <Button variant="outline" onClick={() => void load()}>
          Réessayer
        </Button>
      </div>
    );
  }
  if (sub === null) return <Spinner label="Chargement…" />;

  return (
    <>
      <PageHeader
        title="Facturation"
        description="Gérez votre abonnement Radar et vos limites."
      />
      <div className="grid gap-6 lg:grid-cols-3">
        {plans.map((p) => {
          const current = sub?.plan_slug === p.slug;
          return (
            <Card
              key={p.slug}
              className={current ? "border-indigo-300 ring-2 ring-indigo-500/20" : ""}
            >
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-slate-900">{p.name}</h2>
                {current ? <Badge tone="indigo">Plan actuel</Badge> : null}
              </div>
              <p className="mt-2 text-3xl font-bold text-slate-900">
                {(p.price_cents / 100).toLocaleString("fr-FR", { minimumFractionDigits: 0 })}
                <span className="text-base font-medium text-slate-400"> € / mois</span>
              </p>
              <ul className="mt-4 space-y-2 text-sm text-slate-600">
                <li>🛍️ {p.product_limit} produits suivis</li>
                <li>🔁 {p.checks_per_day} vérifications / jour</li>
                <li>
                  📈 {p.history_days === 0 ? "Historique illimité" : `${p.history_days} jours d'historique`}
                </li>
                {p.features.map((f) => (
                  <li key={f}>✅ {f}</li>
                ))}
              </ul>
              <Button
                className="mt-5 w-full"
                variant={current ? "outline" : "indigo"}
                onClick={() => void choose(p.slug)}
                disabled={busy || current}
              >
                {current ? "Abonnement actif" : sub ? "Choisir ce plan" : "Démarrer"}
              </Button>
            </Card>
          );
        })}
      </div>

      <Card className="mt-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-semibold text-slate-900">Détails de l&apos;abonnement</h2>
            <p className="mt-1 text-sm text-slate-500">
              Statut : <span className="capitalize">{sub.status}</span>
              {sub.plan ? ` · Plan ${sub.plan.name}` : ""}
              {sub.current_period_end
                ? ` · Prochaine échéance le ${formatDate(sub.current_period_end)}`
                : ""}
              {sub.trial_ends_at
                ? ` · Essai jusqu'au ${formatDate(sub.trial_ends_at)}`
                : ""}
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  const r = await api.post<{ url: string }>("/subscription/portal");
                  if (r.url) window.location.assign(r.url);
                } catch (e) {
                  setError(errorMessage(e));
                } finally {
                  setBusy(false);
                }
              }}
            >
              Portail Stripe
            </Button>
            <Button variant="outline" disabled={busy} onClick={() => void load()}>
              Actualiser
            </Button>
          </div>
        </div>
        <p className="mt-4 border-t border-slate-100 pt-3 text-xs text-slate-400">
          API : {API_URL}
        </p>
      </Card>
    </>
  );
}