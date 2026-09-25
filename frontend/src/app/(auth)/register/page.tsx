"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useMemo, useState } from "react";

import { Alert, Button, Input } from "@/components/ui";
import { useAuth } from "@/lib/auth";

export default function RegisterPage() {
  const { register, error } = useAuth();
  const router = useRouter();
  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    organization_name: "",
    email: "",
    password: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const passwordOk = useMemo(
    () => form.password.length >= 8 && (/[A-Z]/.test(form.password) || /\d/.test(form.password)),
    [form.password],
  );

  function set<K extends keyof typeof form>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLocalError(null);
    if (!passwordOk) {
      setLocalError("Le mot de passe doit contenir au moins 8 caractères, dont une majuscule ou un chiffre.");
      return;
    }
    setSubmitting(true);
    try {
      await register(form);
      router.push("/dashboard");
      router.refresh();
    } catch (err) {
      setLocalError(err instanceof Error ? err.message : "Inscription impossible");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <h1 className="text-xl font-semibold text-slate-900">Créer votre compte</h1>
      <p className="mt-1 text-sm text-slate-500">Essai Pro de 14 jours, sans carte bancaire.</p>
      {error || localError ? (
        <div className="mt-4">
          <Alert>{error || localError}</Alert>
        </div>
      ) : null}
      <form onSubmit={onSubmit} className="mt-6 space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="first_name" className="mb-1 block text-sm font-medium text-slate-700">
              Prénom
            </label>
            <Input
              id="first_name"
              value={form.first_name}
              onChange={(e) => set("first_name", e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="last_name" className="mb-1 block text-sm font-medium text-slate-700">
              Nom
            </label>
            <Input id="last_name" value={form.last_name} onChange={(e) => set("last_name", e.target.value)} />
          </div>
        </div>
        <div>
          <label htmlFor="org" className="mb-1 block text-sm font-medium text-slate-700">
            Entreprise
          </label>
          <Input
            id="org"
            required
            placeholder="Ma boutique"
            value={form.organization_name}
            onChange={(e) => set("organization_name", e.target.value)}
          />
        </div>
        <div>
          <label htmlFor="email" className="mb-1 block text-sm font-medium text-slate-700">
            Email professionnel
          </label>
          <Input
            id="email"
            type="email"
            required
            autoComplete="email"
            placeholder="vous@entreprise.fr"
            value={form.email}
            onChange={(e) => set("email", e.target.value)}
          />
        </div>
        <div>
          <label htmlFor="password" className="mb-1 block text-sm font-medium text-slate-700">
            Mot de passe
          </label>
          <Input
            id="password"
            type="password"
            required
            autoComplete="new-password"
            value={form.password}
            onChange={(e) => set("password", e.target.value)}
          />
          <p className="mt-1 text-xs text-slate-400">
            Au moins 8 caractères, avec une majuscule ou un chiffre.
          </p>
        </div>
        <Button type="submit" className="w-full" disabled={submitting}>
          {submitting ? "Création…" : "Créer mon compte gratuit"}
        </Button>
      </form>
      <p className="mt-6 text-center text-sm text-slate-500">
        Déjà inscrit ?{" "}
        <Link href="/login" className="font-medium text-indigo-600 hover:text-indigo-500">
          Se connecter
        </Link>
      </p>
    </>
  );
}