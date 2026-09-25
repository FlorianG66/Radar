import Link from "next/link";

import { Logo } from "@/components/logo";
import { AuthProvider } from "@/lib/auth";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <div className="flex min-h-screen flex-col items-center justify-center bg-slate-50 px-4">
        <div className="mb-8">
          <Logo />
        </div>
        <div className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
          {children}
        </div>
        <p className="mt-6 text-xs text-slate-400">
          <Link href="/" className="hover:text-slate-600">
            ← Retour à l&apos;accueil
          </Link>
        </p>
      </div>
    </AuthProvider>
  );
}