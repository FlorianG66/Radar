"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import {
  AvailabilityBadge,
  Badge,
  Button,
  Card,
  Input,
  ScrapeStatusBadge,
  Select,
  Spinner,
} from "@/components/ui";
import { api, errorMessage, isApiError } from "@/lib/api";
import { formatPercent, formatPrice, timeAgo } from "@/lib/format";
import type { Competitor, Product, ProductSearchResult, ProductSearchResponse, Subscription } from "@/types";

export default function ProductsPage() {
  const router = useRouter();
  const [products, setProducts] = useState<Product[]>([]);
  const [competitors, setCompetitors] = useState<Competitor[]>([]);
  const [sub, setSub] = useState<Subscription | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [filterComp, setFilterComp] = useState("");
  const [statusFilter, setStatusFilter] = useState<"active" | "paused" | "all">("active");
  const [showAdd, setShowAdd] = useState(false);

  const load = useCallback(() => {
    api
      .get<Product[]>("/products?limit=500&include_inactive=true")
      .then((rows) => {
        setProducts(rows);
        setError(null);
      })
      .catch((e) => setError(errorMessage(e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    void load();
    api.get<Competitor[]>("/competitors").then(setCompetitors).catch(() => undefined);
    api.get<Subscription>("/subscription").then(setSub).catch(() => undefined);
  }, [load]);

  const filtered = useMemo(
    () =>
      products.filter(
        (p) =>
          (statusFilter === "all" || (statusFilter === "active") === p.is_active) &&
          (!search || p.name.toLowerCase().includes(search.toLowerCase()) || p.url.toLowerCase().includes(search.toLowerCase())) &&
          (!filterComp || String(p.competitor_id) === filterComp),
      ),
    [products, search, filterComp, statusFilter],
  );

  const plan = sub?.plan;
  const limit = plan?.product_limit;
  const activeCount = useMemo(() => products.filter((p) => p.is_active).length, [products]);

  return (
    <>
      <PageHeader
        title="Produits"
        description="Les produits concurrents que vous surveillez."
        actions={
          <Button onClick={() => setShowAdd(true)}>+ Ajouter un produit</Button>
        }
      />

      {plan && limit !== undefined ? (
        <Card className="mb-6">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-slate-600">
              <strong className="capitalize">{plan.name}</strong> — {activeCount} / {limit} produits surveillés
            </p>
            <Link href="/billing" className="text-sm font-medium text-indigo-600 hover:text-indigo-500">
              {activeCount >= limit ? "Augmenter votre quota →" : "Gérer l'abonnement"}
            </Link>
          </div>
          <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-100">
            <div
              className={activeCount >= limit ? "h-2 rounded-full bg-red-500" : "h-2 rounded-full bg-indigo-500"}
              style={{ width: `${Math.min(100, (activeCount / limit) * 100)}%` }}
            />
          </div>
        </Card>
      ) : null}

      {error ? (
        <Card>
          <p className="text-sm text-red-600">{error}</p>
        </Card>
      ) : null}

      {showAdd ? (
        <AddProductForm
          competitors={competitors}
          onRefresh={() => void load()}
          onDone={(created) => {
            setShowAdd(false);
            void load();
            if (created && created.length > 0 && created[0]) {
              router.push(`/products/${created[0]}`);
            }
          }}
          onCancel={() => setShowAdd(false)}
        />
      ) : null}

      <Card className="mb-4">
        <div className="flex flex-col gap-3 sm:flex-row">
          <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as "active" | "paused" | "all")} className="sm:max-w-[160px]">
            <option value="active">Actifs</option>
            <option value="paused">En pause</option>
            <option value="all">Tous</option>
          </Select>
          <Input
            placeholder="Rechercher un produit ou une URL…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="sm:max-w-xs"
          />
          <Select value={filterComp} onChange={(e) => setFilterComp(e.target.value)} className="sm:max-w-[180px]">
            <option value="">Tous les concurrents</option>
            {competitors.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
        </div>
      </Card>

      {loading ? (
        <Spinner label="Chargement…" />
      ) : filtered.length === 0 ? (
        <Card>
          <p className="py-10 text-center text-sm text-slate-400">
            {statusFilter === "paused"
              ? "Aucun produit en pause."
              : statusFilter === "all"
                ? "Aucun produit surveillé. Ajoutez votre première URL concurrente."
                : "Aucun produit. Ajoutez votre première URL concurrente pour démarrer la surveillance."}
          </p>
        </Card>
      ) : (
        <Card className="overflow-x-auto p-0">
          <table className="min-w-full divide-y divide-slate-100 text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-slate-400">
                <th className="px-4 py-3 font-medium">Produit</th>
                <th className="px-4 py-3 font-medium">Concurrent</th>
                <th className="px-4 py-3 font-medium">Prix</th>
                <th className="px-4 py-3 font-medium">Var.</th>
                <th className="px-4 py-3 font-medium">Dispo</th>
                <th className="px-4 py-3 font-medium">État</th>
                <th className="px-4 py-3 text-right font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.map((p) => (
                <tr key={p.id} className="hover:bg-slate-50/60">
                  <td className="max-w-[260px] px-4 py-3">
                    <Link href={`/products/${p.id}`} className="block truncate font-medium text-slate-800 hover:text-indigo-600">
                      {p.name}
                    </Link>
                    <span className="mt-0.5 block truncate text-xs text-slate-400">{p.url}</span>
                  </td>
                  <td className="px-4 py-3">
                    {p.competitor_name ? <Badge tone="slate">{p.competitor_name}</Badge> : <span className="text-slate-300">—</span>}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 font-semibold text-slate-900">
                    {formatPrice(p.last_price, p.currency)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3">
                    {p.variation_pct !== null && p.variation_pct !== undefined ? (
                      <span className={p.variation_pct <= 0 ? "text-emerald-600" : "text-amber-600"}>
                        {formatPercent(p.variation_pct)}
                      </span>
                    ) : (
                      <span className="text-slate-300">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <AvailabilityBadge availability={p.last_availability} />
                  </td>
                  <td className="px-4 py-3">
                    <ScrapeStatusBadge status={p.last_scrape_status} />
                    <span className="mt-0.5 block text-[10px] text-slate-400">{timeAgo(p.last_checked_at)}</span>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right">
                    <div className="inline-flex gap-1">
                      <Button variant="ghost" size="sm" title="Vérifier maintenant" onClick={() => triggerScrape(p.id)}>
                        ↻
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        title={p.is_active ? "Mettre en pause" : "Réactiver"}
                        onClick={() => toggleActive(p)}
                      >
                        {p.is_active ? "⏸" : "▶"}
                      </Button>
                      <Button variant="ghost" size="sm" title="Supprimer" onClick={() => remove(p)}>
                        🗑
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </>
  );

  async function triggerScrape(id: number) {
    try {
      await api.post<{ message: string }>(`/products/${id}/scrape`);
      void load();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function toggleActive(p: Product) {
    try {
      await api.patch<Product>(`/products/${p.id}`, { is_active: !p.is_active });
      void load();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function remove(p: Product) {
    if (!window.confirm(`Supprimer « ${p.name} » et tout son historique ?`)) return;
    try {
      await api.del<{ message: string }>(`/products/${p.id}`);
      void load();
    } catch (e) {
      setError(errorMessage(e));
    }
  }
}

function AddProductForm({
  competitors,
  onRefresh,
  onDone,
  onCancel,
}: {
  competitors: Competitor[];
  onRefresh: () => void;
  onDone: (created: number[] | null) => void;
  onCancel: () => void;
}) {
  const [mode, setMode] = useState<"search" | "url">("search");

  // Mode recherche en ligne
  const [searchQuery, setSearchQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [searchData, setSearchData] = useState<ProductSearchResponse | null>(null);
  const [addingUrl, setAddingUrl] = useState<string | null>(null);
  const [addedUrls, setAddedUrls] = useState<Set<string>>(new Set());

  // Mode URL manuelle
  const [urls, setUrls] = useState("");
  const [name, setName] = useState("");
  const [category, setCategory] = useState("");
  const [competitorName, setCompetitorName] = useState("");
  const [competitorId, setCompetitorId] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Erreur partagée
  const [error, setError] = useState<string | null>(null);

  async function onSearchSubmit(e: FormEvent) {
    e.preventDefault();
    const q = searchQuery.trim();
    if (q.length < 3) {
      setError("Entrez au moins 3 caractères pour lancer la recherche.");
      return;
    }
    setError(null);
    setSearching(true);
    setSearchData(null);
    try {
      const res = await api.get<ProductSearchResponse>(`/products/search?q=${encodeURIComponent(q)}`);
      setSearchData(res);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSearching(false);
    }
  }

  async function handleAddResult(r: ProductSearchResult) {
    setAddingUrl(r.url);
    setError(null);
    try {
      await api.post<Product>("/products", {
        url: r.url,
        name: r.name,
        competitor_name: r.label,
      });
      setAddedUrls((prev) => {
        const next = new Set(prev);
        next.add(r.url);
        return next;
      });
      onRefresh();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setAddingUrl(null);
    }
  }

  async function onUrlSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const list = urls
      .split(/[\n,]/)
      .map((s) => s.trim())
      .filter(Boolean);
    if (list.length === 0) {
      setError("Collez au moins une URL (une par ligne).");
      return;
    }
    setSubmitting(true);
    const created: number[] = [];
    for (const url of list) {
      try {
        const p = await api.post<Product>("/products", {
          url,
          name: name.trim() || "",
          category: category.trim() || null,
          ...(competitorId ? { competitor_id: Number(competitorId) } : { competitor_name: competitorName.trim() || null }),
        });
        created.push(p.id);
      } catch (err) {
        if (isApiError(err, 402)) {
          setError(errorMessage(err));
          break;
        }
      }
    }
    setSubmitting(false);
    onDone(created);
  }

  return (
    <Card className="mb-6">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-3">
        <div>
          <h2 className="font-semibold text-slate-900">Ajouter des produits à surveiller</h2>
          <p className="mt-0.5 text-xs text-slate-500">
            {mode === "search"
              ? "Recherchez un produit en ligne pour comparer les prix chez vos concurrents et les ajouter."
              : "Ajoutez directement une ou plusieurs URLs de fiches produits."}
          </p>
        </div>
        <div className="inline-flex rounded-lg bg-slate-100 p-1 text-xs font-medium">
          <button
            type="button"
            onClick={() => {
              setMode("search");
              setError(null);
            }}
            className={`rounded-md px-3 py-1.5 transition ${
              mode === "search" ? "bg-white text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900"
            }`}
          >
            🔍 Recherche par nom
          </button>
          <button
            type="button"
            onClick={() => {
              setMode("url");
              setError(null);
            }}
            className={`rounded-md px-3 py-1.5 transition ${
              mode === "url" ? "bg-white text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900"
            }`}
          >
            🔗 Saisie d&apos;URLs
          </button>
        </div>
      </div>

      {error ? (
        <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
      ) : null}

      {mode === "search" ? (
        <div className="mt-4 space-y-4">
          <form onSubmit={onSearchSubmit} className="flex gap-2">
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Ex: RTX 5070 12GB, Samsung 990 Pro, Keychron K8…"
              className="flex-1"
            />
            <Button type="submit" disabled={searching}>
              {searching ? "Recherche…" : "Rechercher en ligne"}
            </Button>
            <Button type="button" variant="outline" onClick={onCancel}>
              Fermer
            </Button>
          </form>

          {searching ? (
            <div className="py-8">
              <Spinner label="Recherche des offres chez vos concurrents et sur le web…" />
            </div>
          ) : searchData ? (
            <div className="space-y-4 pt-2">
              {searchData.merchants && searchData.merchants.length > 0 ? (
                <div className="flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
                  <span className="font-medium text-slate-600">Marchands interrogés :</span>
                  {searchData.merchants.map((m) => (
                    <Badge key={m.domain} tone={m.ok ? "slate" : "red"}>
                      {m.label} {!m.ok ? "(indisponible)" : ""}
                    </Badge>
                  ))}
                </div>
              ) : null}

              {searchData.results.length === 0 ? (
                <div className="rounded-lg border border-dashed border-slate-200 py-8 text-center text-sm text-slate-500">
                  Aucune offre trouvée pour &laquo; {searchData.query} &raquo; chez les marchands configurés.
                  <p className="mt-1 text-xs text-slate-400">
                    Vous pouvez essayer une recherche plus générique ou ajouter directement l&apos;URL dans l&apos;onglet &laquo; Saisie d&apos;URLs &raquo;.
                  </p>
                </div>
              ) : (
                <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
                  <table className="min-w-full divide-y divide-slate-100 text-sm">
                    <thead>
                      <tr className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-400">
                        <th className="px-4 py-2.5 font-medium">Marchand</th>
                        <th className="px-4 py-2.5 font-medium">Produit trouvé</th>
                        <th className="px-4 py-2.5 font-medium">Prix actuel</th>
                        <th className="px-4 py-2.5 font-medium">Disponibilité</th>
                        <th className="px-4 py-2.5 text-right font-medium">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {searchData.results.map((r) => {
                        const isMonitored = r.tracked || addedUrls.has(r.url);
                        const isAdding = addingUrl === r.url;
                        return (
                          <tr key={r.url} className="hover:bg-slate-50/60">
                            <td className="whitespace-nowrap px-4 py-3">
                              <Badge tone="indigo">{r.label}</Badge>
                              <span className="ml-1.5 text-xs text-slate-400">{r.domain}</span>
                            </td>
                            <td className="max-w-[280px] px-4 py-3">
                              <a
                                href={r.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="block truncate font-medium text-slate-800 hover:text-indigo-600 hover:underline"
                                title={r.name}
                              >
                                {r.name} ↗
                              </a>
                            </td>
                            <td className="whitespace-nowrap px-4 py-3 font-semibold text-slate-900">
                              {formatPrice(r.price, r.currency)}
                            </td>
                            <td className="whitespace-nowrap px-4 py-3">
                              <AvailabilityBadge availability={r.availability} />
                            </td>
                            <td className="whitespace-nowrap px-4 py-3 text-right">
                              {isMonitored ? (
                                <Badge tone="emerald">✓ Surveillé</Badge>
                              ) : (
                                <Button
                                  size="sm"
                                  disabled={isAdding}
                                  onClick={() => handleAddResult(r)}
                                >
                                  {isAdding ? "Ajout…" : "+ Surveiller"}
                                </Button>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ) : (
            <p className="py-4 text-xs text-slate-400">
              Saisissez le nom d&apos;un produit (ex. <em>RTX 5070</em>, <em>Keychron K8</em>) pour voir les prix chez les marchands et sélectionner ceux à surveiller.
            </p>
          )}
        </div>
      ) : (
        <form onSubmit={onUrlSubmit} className="mt-4 space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">URL des fiches produits</label>
            <textarea
              required
              rows={4}
              className="w-full rounded-lg border-0 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm ring-1 ring-inset ring-slate-300 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder={"https://concurrent.fr/produit-1\nhttps://concurrent.fr/produit-2"}
              value={urls}
              onChange={(e) => setUrls(e.target.value)}
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Nom (optionnel)</label>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Détecté automatiquement si vide" />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Catégorie (optionnel)</label>
              <Input value={category} onChange={(e) => setCategory(e.target.value)} placeholder="GPU, Audio…" />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Concurrent existant</label>
              <Select value={competitorId} onChange={(e) => setCompetitorId(e.target.value)}>
                <option value="">—</option>
                {competitors.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">ou nom du nouveau concurrent</label>
              <Input value={competitorName} onChange={(e) => setCompetitorName(e.target.value)} disabled={!!competitorId} />
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onCancel}>
              Annuler
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? "Ajout en cours…" : "Ajouter"}
            </Button>
          </div>
        </form>
      )}
    </Card>
  );
}