"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ChangeFeed } from "@/components/ChangeFeed";
import { PageHeader } from "@/components/PageHeader";
import { Badge, Card, Spinner, StatCard } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { formatPrice, timeAgo } from "@/lib/format";
import type { Dashboard } from "@/types";

export default function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<Dashboard>("/dashboard?days=7")
      .then(setData)
      .catch((e) => setError(errorMessage(e)));
  }, []);

  if (error)
    return (
      <Card>
        <p className="text-sm text-red-600">{error}</p>
      </Card>
    );
  if (!data) return <Spinner label="Chargement du tableau de bord…" />;

  const plan = data.plan;

  return (
    <>
      <PageHeader
        title="Tableau de bord"
        description="Vue d'ensemble de votre veille concurrentielle sur les 7 derniers jours."
        actions={
          <Link
            href="/import"
            className="inline-flex rounded-lg bg-indigo-600 px-3.5 py-2 text-sm font-medium text-white hover:bg-indigo-500"
          >
            Ajouter des produits
          </Link>
        }
      />

      {plan ? (
        <Card className="mb-6 flex flex-wrap items-center justify-between gap-3 bg-gradient-to-r from-indigo-50 to-violet-50">
          <div>
            <p className="text-sm text-slate-600">
              Plan <strong className="capitalize">{plan.plan?.name ?? plan.plan_slug ?? "—"}</strong>
            </p>
            <p className="mt-0.5 text-xs text-slate-500">
              {plan.status === "trialing" ? "Période d'essai en cours" : `Statut : ${plan.status}`}
              {plan.current_period_end ? ` · Prochaine échéance le ${new Date(plan.current_period_end).toLocaleDateString("fr-FR")}` : ""}
            </p>
          </div>
          <Link
            href="/billing"
            className="text-sm font-medium text-indigo-700 hover:text-indigo-500"
          >
            Gérer l&apos;abonnement →
          </Link>
        </Card>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Produits suivis" value={data.products_count} hint={`${data.active_products} actifs`} />
        <StatCard label="Changements (7 j)" value={data.changes_today} tone="blue" />
        <StatCard label="Baisse de prix" value={data.price_drops_today} tone="green" hint={`${data.price_rises_today} hausses`} />
        <StatCard label="Erreurs de scraping" value={data.scrape_errors} tone={data.scrape_errors > 0 ? "red" : "slate"} hint={`${data.checks_today} vérifications`} />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="font-semibold text-slate-900">Changements récents</h2>
            <Link href="/changes" className="text-sm text-indigo-600 hover:text-indigo-500">
              Tout voir
            </Link>
          </div>
          <ChangeFeed events={data.recent_changes} />
        </Card>

        <Card>
          <div className="mb-2 flex items-center justify-between">
            <h2 className="font-semibold text-slate-900">Produits récemment vérifiés</h2>
            <Link href="/products" className="text-sm text-indigo-600 hover:text-indigo-500">
              Tout voir
            </Link>
          </div>
          {data.product_preview.length === 0 ? (
            <p className="py-8 text-center text-sm text-slate-400">
              Aucun produit ajouté. Commencez par en surveiller un !
            </p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {data.product_preview.map((p) => (
                <li key={p.id} className="py-3">
                  <Link href={`/products/${p.id}`} className="block truncate text-sm font-medium text-slate-800 hover:text-indigo-600">
                    {p.name}
                  </Link>
                  <div className="mt-1 flex items-center justify-between text-xs text-slate-500">
                    <span>
                      {p.competitor_name ? (
                        <Badge tone="slate">{p.competitor_name}</Badge>
                      ) : null}{" "}
                      {formatPrice(p.last_price, p.currency)}
                    </span>
                    <span>{timeAgo(p.last_checked_at)}</span>
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