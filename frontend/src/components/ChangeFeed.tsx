import Link from "next/link";

import { EventBadge } from "@/components/ui";
import { formatDateTime } from "@/lib/format";
import type { ChangeEvent } from "@/types";

export function ChangeFeed({ events, emptyHref = "/changes" }: { events: ChangeEvent[]; emptyHref?: string }) {
  if (events.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-slate-400">
        Aucun changement pour le moment.{" "}
        <Link href={emptyHref} className="text-indigo-600 hover:text-indigo-500">
          Voir tout
        </Link>
      </p>
    );
  }
  return (
    <ul className="divide-y divide-slate-100">
      {events.map((e) => (
        <li key={e.id} className="flex items-start justify-between gap-4 py-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <EventBadge type={e.event_type} />
              <span className="text-xs text-slate-400">{formatDateTime(e.created_at)}</span>
            </div>
            <p className="mt-1 truncate text-sm font-medium text-slate-800">{e.title}</p>
            {e.product_name ? (
              <Link
                href={`/products/${e.product_id}`}
                className="mt-0.5 block truncate text-xs text-indigo-600 hover:text-indigo-500"
              >
                {e.product_name}
              </Link>
            ) : null}
          </div>
          {e.importance === "high" ? (
            <span className="mt-1 shrink-0 rounded-full bg-red-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-red-600">
              Important
            </span>
          ) : null}
        </li>
      ))}
    </ul>
  );
}