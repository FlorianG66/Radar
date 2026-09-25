"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { ChangeFeed } from "@/components/ChangeFeed";
import { PageHeader } from "@/components/PageHeader";
import { Card, Select, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import type { ChangeEvent } from "@/types";

const EVENT_TYPES = [
  "price_drop",
  "price_rise",
  "price_back",
  "promotion_start",
  "promotion_end",
  "promotion_change",
  "in_stock",
  "out_of_stock",
  "scrape_failed",
  "product_info",
];

export default function ChangesPage() {
  const [events, setEvents] = useState<ChangeEvent[]>([]);
  const [type, setType] = useState("");
  const [competitor, setCompetitor] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback((t: string) => {
    api
      .get<ChangeEvent[]>(`/changes?limit=300${t ? `&event_type=${encodeURIComponent(t)}` : ""}`)
      .then((rows) => {
        setEvents(rows);
        setError(null);
      })
      .catch((e) => setError(errorMessage(e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => void load(type), [load, type]);

  const competitors = useMemo(() => {
    const names = new Set(events.map((e) => e.competitor_name).filter(Boolean) as string[]);
    return [...names].sort();
  }, [events]);

  const filtered = competitor ? events.filter((e) => e.competitor_name === competitor) : events;

  return (
    <>
      <PageHeader
        title="Changements"
        description="Tous les événements détectés sur vos produits suivis."
      />
      <Card className="mb-4">
        <div className="flex flex-col gap-3 sm:flex-row">
          <Select value={type} onChange={(e) => setType(e.target.value)} className="sm:max-w-[220px]">
            <option value="">Tous les types</option>
            {EVENT_TYPES.map((t) => (
              <option key={t} value={t}>
                {t.replace(/_/g, " ")}
              </option>
            ))}
          </Select>
          <Select value={competitor} onChange={(e) => setCompetitor(e.target.value)} className="sm:max-w-[220px]">
            <option value="">Tous les concurrents</option>
            {competitors.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </Select>
        </div>
      </Card>
      <Card>
        {error ? (
          <p className="text-sm text-red-600">{error}</p>
        ) : loading ? (
          <Spinner label="Chargement…" />
        ) : (
          <ChangeFeed events={filtered} emptyHref="/products" />
        )}
      </Card>
    </>
  );
}