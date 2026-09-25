import Link from "next/link";

export function Logo({ light = false }: { light?: boolean }) {
  return (
    <Link href="/" className="inline-flex items-center gap-2">
      <span className="flex size-7 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 text-sm">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path
            d="M9 4.5a2.2 2.2 0 1 1 3 2.1v2.6h3.6a2.2 2.2 0 0 1 2.2 2.2v.8a2.2 2.2 0 1 1-2.2 0v-.8h-3.6v2.6a2.2 2.2 0 1 1-3 2.1v-9.3zM19.5 18.2v1h-15v-1h15z"
            fill="currentColor"
            className="text-white"
          />
        </svg>
      </span>
      <span className={cn(light ? "text-white" : "text-slate-900")}>
        <span className="text-lg font-bold tracking-tight">Radar</span>
      </span>
    </Link>
  );
}

function cn(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}