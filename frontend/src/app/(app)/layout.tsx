"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { Logo } from "@/components/logo";
import { Spinner } from "@/components/ui";
import { AuthProvider, useAuth } from "@/lib/auth";

const navItems = [
  { href: "/dashboard", label: "Tableau de bord", icon: "📊" },
  { href: "/products", label: "Produits", icon: "🛍️" },
  { href: "/changes", label: "Changements", icon: "⚡" },
  { href: "/notifications", label: "Notifications", icon: "🔔" },
  { href: "/import", label: "Import / Export", icon: "📥" },
  { href: "/billing", label: "Facturation", icon: "💳" },
  { href: "/settings", label: "Paramètres", icon: "⚙️" },
] as const;

function SidebarLink({ href, label, icon }: { href: string; label: string; icon: string }) {
  const pathname = usePathname();
  const active = pathname === href || pathname.startsWith(`${href}/`);
  return (
    <Link
      href={href}
      className={
        active
          ? "flex items-center gap-3 rounded-lg bg-indigo-50 px-3 py-2 text-sm font-semibold text-indigo-700"
          : "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900"
      }
    >
      <span className="text-base">{icon}</span>
      {label}
    </Link>
  );
}

function Shell({ children }: { children: ReactNode }) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading) return <Spinner label="Chargement…" />;
  if (!user) return null;

  return (
    <div className="flex min-h-screen">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-slate-200 bg-white md:flex">
        <div className="flex h-16 items-center border-b border-slate-200 px-4">
          <Logo />
        </div>
        <nav className="flex-1 space-y-1 overflow-y-auto p-3">
          {navItems.map((n) => (
            <SidebarLink key={n.href} {...n} />
          ))}
          {user.is_admin ? (
            <SidebarLink href="/admin" label="Administration" icon="🛡️" />
          ) : null}
        </nav>
        <div className="border-t border-slate-200 p-3">
          <div className="rounded-lg bg-slate-50 p-3">
            <p className="truncate text-sm font-medium text-slate-800">
              {user.first_name || user.email}
            </p>
            <p className="truncate text-xs text-slate-500">{user.email}</p>
            <button
              onClick={() => {
                logout();
                router.push("/login");
              }}
              className="mt-2 text-xs font-medium text-slate-500 hover:text-red-600"
            >
              Se déconnecter
            </button>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col md:pl-60">
        {/* Mobile top bar */}
        <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-slate-200 bg-white/80 px-4 backdrop-blur md:hidden">
          <Logo />
          <button
            onClick={() => {
              if (pathname !== "/dashboard") router.push("/dashboard");
            }}
            className="rounded-lg px-2 py-1 text-sm font-medium text-slate-600 hover:bg-slate-100"
          >
            Menu
          </button>
        </header>
        <main className="flex-1 px-4 py-8 sm:px-6 lg:px-10">{children}</main>
      </div>
    </div>
  );
}

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <Shell>{children}</Shell>
    </AuthProvider>
  );
}