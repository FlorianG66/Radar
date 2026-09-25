"use client";

import { useCallback, useEffect, useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { Badge, Button, Card, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { AdminStats, DomainState, OrgAdmin } from "@/types";

export default function AdminPage() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [orgs, setOrgs] = useState<OrgAdmin[]>([]);
  const [domains, setDomains] = useState<DomainState[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    Promise.all([
      api.get<AdminStats>("/admin/stats").then((s) => {
        setStats(s);
        setError(null);
      }),
      api.get<OrgAdmin[]>("/admin/organizations").then(setOrgs),
      api.get<DomainState[]>("/admin/domains").then(setDomains),
    ]).catch((e) => setError(errorMessage(e)));
  }, []);

  useEffect(() => void load(), [load]);

  async function toggleDomain(d: DomainState) {
    setBusy(true);
    try {
      await api.post<DomainState>(`/admin/domains/${d.name}/${d.disabled ? "enable" : "disable"}`);
      void load();
    } catch (e) {
      setError(errorMessage(e));
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
  if (!stats) return <Spinner label="Chargement…" />;

  const statCards: { label: string; value: number }[] = [
    { label: "Utilisateurs", value: stats.users },
    { label: "Organisations", value: stats.organizations },
    { label: "Produits", value: stats.products },
    { label: "Événements de changement", value: stats.change_events },
    { label: "Alertes en échec (scraping)", value: stats.scrape_errors },
    { label: "Jobs en échec", value: stats.failed_jobs },
  ];

  return (
    <>
      <PageHeader title="Administration" description="Vue d'ensemble de la plateforme Radar." />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {statCards.map((s) => (
          <Card key={s.label}>
            <p className="text-sm text-slate-500">{s.label}</p>
            <p className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">{s.value}</p>
          </Card>
        ))}
        <Card>
          <p className="text-sm text-slate-500">Jobs en file d&apos;attente</p>
          <p className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">{stats.queued_jobs}</p>
        </Card>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card>
          <h2 className="font-semibold text-slate-900">Abonnements par plan</h2>
          {Object.keys(stats.subscriptions).length === 0 ? (
            <p className="mt-3 text-sm text-slate-400">Aucun abonnement.</p>
          ) : (
            <ul className="mt-3 space-y-1">
              {Object.entries(stats.subscriptions).map(([k, v]) => (
                <li key={k} className="flex items-center justify-between text-sm">
                  <span className="text-slate-600">{k.replace(":", " · ")}</span>
                  <Badge tone="indigo">{v}</Badge>
                </li>
              ))}
            </ul>
          )}

          <h2 className="mt-6 font-semibold text-slate-900">Scraping par domaine</h2>
          {stats.domains.length === 0 ? (
            <p className="mt-3 text-sm text-slate-400">Aucun domaine scrapé.</p>
          ) : (
            <ul className="mt-3 divide-y divide-slate-100 text-sm">
              {stats.domains.slice(0, 15).map((d) => (
                <li key={d.domain} className="flex items-center justify-between py-2">
                  <span className="text-slate-700">{d.domain}</span>
                  <span className="text-xs text-slate-400">
                    {d.scrapes} relevés · <span className={d.errors ? "text-red-600" : "text-emerald-600"}>{d.errors} erreurs</span>
                  </span>
                </li>
              ))}
            </ul>
          )}

          {stats.recent_failures.length > 0 ? (
            <>
              <h2 className="mt-6 font-semibold text-slate-900">Échecs récents (7 j)</h2>
              <ul className="mt-3 divide-y divide-slate-100 text-sm">
                {stats.recent_failures.map((f) => (
                  <li key={f.id} className="py-2">
                    <p className="truncate text-xs text-slate-700">{f.url}</p>
                    <p className="mt-0.5 text-xs text-red-600">
                      {f.error ?? `HTTP ${f.http_status ?? "?"}`} · {formatDateTime(f.finished_at)}
                    </p>
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </Card>

        <div className="space-y-6">
          <Card>
            <h2 className="font-semibold text-slate-900">Domaines d&apos;extracteurs</h2>
            <p className="mt-1 text-sm text-slate-500">Activez/désactivez un extracteur spécialisé par domaine.</p>
            <ul className="mt-3 divide-y divide-slate-100">
              {domains.map((d) => (
                <li key={d.name} className="flex items-center justify-between py-2">
                  <div>
                    <p className="text-sm font-medium text-slate-800">
                      {d.name}{" "}
                      {d.disabled ? <Badge tone="red">Désactivé</Badge> : <Badge tone="green">Actif</Badge>}
                    </p>
                    {d.disabled_reason ? <p className="text-xs text-slate-400">{d.disabled_reason}</p> : null}
                  </div>
                  <Button variant="outline" size="sm" disabled={busy} onClick={() => void toggleDomain(d)}>
                    {d.disabled ? "Réactiver" : "Désactiver"}
                  </Button>
                </li>
              ))}
            </ul>
          </Card>

          <Card>
            <h2 className="font-semibold text-slate-900">Organisations</h2>
            {orgs.length === 0 ? (
              <p className="mt-3 text-sm text-slate-400">Aucune organisation.</p>
            ) : (
              <div className="mt-3 max-h-96 overflow-y-auto">
                <table className="min-w-full text-sm">
                  <thead className="text-left text-xs uppercase tracking-wide text-slate-400">
                    <tr>
                      <th className="py-2 pr-3 font-medium">Nom</th>
                      <th className="py-2 pr-3 font-medium">Produits</th>
                      <th className="py-2 font-medium">Plan</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {orgs.map((o) => (
                      <tr key={o.id}>
                        <td className="py-2 pr-3">
                          <p className="truncate text-slate-800">{o.name}</p>
                          <p className="truncate text-xs text-slate-400">{o.email}</p>
                        </td>
                        <td className="py-2 pr-3 text-slate-600">{o.products_count}</td>
                        <td className="py-2">
                          <Badge tone={o.plan_slug ? "indigo" : "slate"}>{o.plan_slug ?? "aucun"}</Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}