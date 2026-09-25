"use client";

import { useCallback, useEffect, useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { Badge, Card, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { NotificationRow } from "@/types";

const PREF_LABELS: Record<string, { label: string; hint: string }> = {
  price_drop: { label: "Baisse de prix", hint: "Un concurrent baisse son prix" },
  price_rise: { label: "Hausse de prix", hint: "Un concurrent augmente son prix" },
  price_back: { label: "Retour au prix initial", hint: "Le prix revient à sa valeur précédente" },
  out_of_stock: { label: "Rupture de stock", hint: "Le produit n'est plus disponible" },
  in_stock: { label: "Retour en stock", hint: "Le produit redevient disponible" },
  promotion_start: { label: "Début de promotion", hint: "Une remise est détectée" },
  promotion_end: { label: "Fin de promotion", hint: "La remise se termine" },
  promotion_change: { label: "Changement de promotion", hint: "L'ampleur de la remise évolue" },
  product_info: { label: "Informations produit", hint: "Nom, description, images…" },
  scrape_failed: { label: "Échec de scraping", hint: "La page n'a pas pu être analysée" },
};

export default function NotificationsPage() {
  const [prefs, setPrefs] = useState<Record<string, boolean> | null>(null);
  const [rows, setRows] = useState<NotificationRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);

  const load = useCallback(() => {
    Promise.all([
      api.get<{ prefs: Record<string, boolean> }>("/notifications/preferences/all").then((r) => {
        setPrefs(r.prefs);
        setError(null);
      }),
      api.get<NotificationRow[]>("/notifications?limit=100").then(setRows),
    ])
      .catch((e) => setError(errorMessage(e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function toggle(key: string, enabled: boolean) {
    setSaving(key);
    try {
      await api.put<{ prefs: Record<string, boolean> }>("/notifications/preferences", {
        event_type: key,
        enabled,
      });
      setPrefs((p) => ({ ...p, [key]: enabled }));
    } catch (e) {
      alert(errorMessage(e));
    } finally {
      setSaving(null);
    }
  }

  if (loading) return <Spinner label="Chargement…" />;

  return (
    <>
      <PageHeader title="Notifications" description="Choisissez les événements à surveiller et consultez l'historique des alertes." />
      {error ? (
        <Card>
          <p className="text-sm text-red-600">{error}</p>
        </Card>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-5">
        <Card className="lg:col-span-2">
          <h2 className="font-semibold text-slate-900">Préférences</h2>
          <p className="mt-1 text-sm text-slate-500">Recevez un e-mail à chaque événement activé.</p>
          <ul className="mt-4 space-y-3">
            {prefs
              ? Object.entries(prefs).map(([key, enabled]) => {
                  const meta = PREF_LABELS[key];
                  return (
                    <li key={key} className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-medium text-slate-800">{meta?.label ?? key}</p>
                        <p className="text-xs text-slate-500">{meta?.hint ?? ""}</p>
                      </div>
                      <button
                        onClick={() => void toggle(key, !enabled)}
                        disabled={saving === key}
                        aria-label={`${meta?.label ?? key} : ${enabled ? "activé" : "désactivé"}`}
                        className={
                          enabled
                            ? "relative h-6 w-11 shrink-0 rounded-full bg-indigo-600 transition-colors disabled:opacity-50"
                            : "relative h-6 w-11 shrink-0 rounded-full bg-slate-300 transition-colors disabled:opacity-50"
                        }
                      >
                        <span
                          className={
                            enabled
                              ? "absolute left-6 top-0.5 size-5 rounded-full bg-white shadow"
                              : "absolute left-0.5 top-0.5 size-5 rounded-full bg-white shadow"
                          }
                        />
                      </button>
                    </li>
                  );
                })
              : null}
          </ul>
        </Card>

        <Card className="lg:col-span-3">
          <h2 className="font-semibold text-slate-900">Historique</h2>
          {rows.length === 0 ? (
            <p className="py-10 text-center text-sm text-slate-400">Aucune alerte pour le moment.</p>
          ) : (
            <ul className="mt-3 divide-y divide-slate-100">
              {rows.map((n) => (
                <li key={n.id} className="flex items-center justify-between gap-4 py-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-800">{n.subject ?? "Notification"}</p>
                    <p className="mt-0.5 truncate text-xs text-slate-500">
                      {formatDateTime(n.created_at)}
                      {n.product_name ? ` · ${n.product_name}` : ""}
                      {n.event_type ? ` · ${n.event_type.replace(/_/g, " ")}` : ""}
                    </p>
                  </div>
                  <div className="shrink-0">
                    <Badge tone={n.status === "sent" ? "green" : n.status === "pending" ? "amber" : "slate"}>
                      {n.status}
                    </Badge>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </>
  );
}