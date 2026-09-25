import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";

import { AVAILABILITY_LABELS, SCRAPE_STATUS_LABELS } from "@/lib/format";

export function cn(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

const tones: Record<string, string> = {
  indigo: "bg-indigo-600 text-white hover:bg-indigo-500 disabled:bg-indigo-300",
  slate: "bg-slate-800 text-white hover:bg-slate-700 disabled:bg-slate-400",
  outline:
    "bg-white text-slate-700 ring-1 ring-inset ring-slate-300 hover:bg-slate-50 disabled:opacity-50",
  ghost: "bg-transparent text-slate-600 hover:bg-slate-100 disabled:opacity-50",
  danger: "bg-red-600 text-white hover:bg-red-500 disabled:bg-red-300",
};

export function Button({
  variant = "indigo",
  size = "md",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: keyof typeof tones;
  size?: "sm" | "md" | "lg";
}) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500",
        size === "sm" && "px-2.5 py-1.5 text-xs",
        size === "md" && "px-3.5 py-2 text-sm",
        size === "lg" && "px-5 py-2.5 text-base",
        tones[variant],
        className,
      )}
      {...props}
    />
  );
}

export function Input({
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "w-full rounded-lg border-0 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm ring-1 ring-inset ring-slate-300 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500",
        className,
      )}
      {...props}
    />
  );
}

export function Select({
  className,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        "w-full rounded-lg border-0 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm ring-1 ring-inset ring-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500",
        className,
      )}
      {...props}
    />
  );
}

const badgeTones: Record<string, string> = {
  green: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  red: "bg-red-50 text-red-700 ring-red-200",
  amber: "bg-amber-50 text-amber-700 ring-amber-200",
  slate: "bg-slate-100 text-slate-600 ring-slate-200",
  indigo: "bg-indigo-50 text-indigo-700 ring-indigo-200",
  blue: "bg-sky-50 text-sky-700 ring-sky-200",
};

export function Badge({
  tone = "slate",
  children,
}: {
  tone?: keyof typeof badgeTones;
  children: ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset whitespace-nowrap",
        badgeTones[tone],
      )}
    >
      {children}
    </span>
  );
}

export function Card({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border border-slate-200 bg-white p-5 shadow-sm",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function StatCard({
  label,
  value,
  hint,
  tone = "indigo",
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: keyof typeof badgeTones;
}) {
  return (
    <Card>
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-500">{label}</p>
        <span className={cn("size-2 rounded-full", badgeTones[tone])} />
      </div>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">{value}</p>
      {hint ? <p className="mt-1 text-xs text-slate-400">{hint}</p> : null}
    </Card>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-slate-50/50 px-6 py-14 text-center">
      <div className="flex size-12 items-center justify-center rounded-full bg-white text-2xl shadow-sm">
        🛰️
      </div>
      <h3 className="mt-4 text-sm font-semibold text-slate-900">{title}</h3>
      {description ? <p className="mt-1 max-w-sm text-sm text-slate-500">{description}</p> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex justify-center py-16">
      <svg className="size-8 animate-spin text-indigo-600" viewBox="0 0 24 24" fill="none">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
      </svg>
      {label ? <span className="sr-only">{label}</span> : null}
    </div>
  );
}

export function Alert({ tone = "red", children }: { tone?: "red" | "green" | "amber"; children: ReactNode }) {
  const map = {
    red: "border-red-200 bg-red-50 text-red-700",
    green: "border-emerald-200 bg-emerald-50 text-emerald-700",
    amber: "border-amber-200 bg-amber-50 text-amber-700",
  };
  return <div className={cn("rounded-lg border px-3 py-2 text-sm", map[tone])}>{children}</div>;
}

export function AvailabilityBadge({ availability }: { availability: string | null }) {
  if (availability === "in_stock")
    return <Badge tone="green">{AVAILABILITY_LABELS.in_stock}</Badge>;
  if (availability === "out_of_stock")
    return <Badge tone="red">{AVAILABILITY_LABELS.out_of_stock}</Badge>;
  if (availability === "preorder") return <Badge tone="amber">{AVAILABILITY_LABELS.preorder}</Badge>;
  return <Badge tone="slate">Inconnu</Badge>;
}

export function ScrapeStatusBadge({ status }: { status: string }) {
  const tone: keyof typeof badgeTones =
    status === "ok" ? "green" : status === "error" ? "red" : status === "disabled" ? "slate" : "amber";
  return <Badge tone={tone}>{SCRAPE_STATUS_LABELS[status] ?? status}</Badge>;
}

const eventTones: Record<string, string> = {
  price_drop: "green",
  price_rise: "amber",
  price_back: "blue",
  promotion_start: "indigo",
  promotion_end: "amber",
  promotion_change: "amber",
  in_stock: "green",
  out_of_stock: "red",
  product_info: "slate",
  scrape_failed: "red",
};

export function EventBadge({ type }: { type: string }) {
  const tone = (eventTones[type] ?? "slate") as keyof typeof badgeTones;
  return <Badge tone={tone}>{type.replace(/_/g, " ")}</Badge>;
}