"use client";

import { useId } from "react";

import { formatPrice } from "@/lib/format";

interface Point {
  at: string;
  price: number;
}

export function PriceChart({ data, currency }: { data: Point[]; currency?: string | null }) {
  const gradId = useId().replace(/:/g, "");
  const prices = data.map((d) => d.price);
  if (prices.length === 0) {
    return (
      <div className="flex h-56 items-center justify-center text-sm text-slate-400">
        Aucune donnée de prix pour le moment.
      </div>
    );
  }

  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const span = max - min || 1;
  const W = 640;
  const H = 200;
  const pad = 10;

  const pts = data.map((d, i) => {
    const x = pad + (i / Math.max(1, data.length - 1)) * (W - 2 * pad);
    const y = H - pad - ((d.price - min) / span) * (H - 2 * pad);
    return [x, y] as const;
  });

  const path = pts.map(([x, y], i) => `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
  const area = `${path} L ${pts[pts.length - 1][0].toFixed(1)} ${H} L ${pts[0][0].toFixed(1)} ${H} Z`;
  const last = pts[pts.length - 1];

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Évolution du prix">
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#6366f1" stopOpacity="0.25" />
            <stop offset="100%" stopColor="#6366f1" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0.25, 0.5, 0.75].map((f) => (
          <line
            key={f}
            x1={pad}
            x2={W - pad}
            y1={H * f}
            y2={H * f}
            stroke="#e2e8f0"
            strokeDasharray="4 4"
            strokeWidth="1"
          />
        ))}
        <path d={area} fill={`url(#${gradId})`} />
        <path d={path} fill="none" stroke="#6366f1" strokeWidth="2.5" strokeLinecap="round" />
        <circle cx={last[0]} cy={last[1]} r="4" fill="#6366f1" stroke="#fff" strokeWidth="2" />
      </svg>
      <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
        <span>
          Min : <strong>{formatPrice(min, currency)}</strong>
        </span>
        <span className="font-semibold text-slate-700">{formatPrice(prices[prices.length - 1], currency)}</span>
        <span>
          Max : <strong>{formatPrice(max, currency)}</strong>
        </span>
      </div>
    </div>
  );
}