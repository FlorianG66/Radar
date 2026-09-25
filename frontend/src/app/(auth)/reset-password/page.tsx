"use client";

import { FormEvent, useState } from "react";

import { Alert, Button, Input } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";

export default function ResetPasswordPage() {
  const [password, setPassword] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const token = new URLSearchParams(window.location.search).get("token");
    if (!token) {
      setLocalError("Aucun jeton de réinitialisation fourni.");
      return;
    }
    setSubmitting(true);
    setLocalError(null);
    try {
      const r = await api.post<{ message: string }>("/auth/reset-password", {
        token,
        new_password: password,
      });
      setMessage(r.message);
      setTimeout(() => (window.location.replace("/login")), 1500);
    } catch (err) {
      setLocalError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  if (message) {
    return (
      <div className="text-center">
        <div className="text-3xl">✅</div>
        <h1 className="mt-3 text-lg font-semibold text-emerald-700">Mot de passe réinitialisé</h1>
        <p className="mt-2 text-sm text-slate-500">Redirection vers la connexion…</p>
      </div>
    );
  }

  return (
    <>
      <h1 className="text-xl font-semibold text-slate-900">Nouveau mot de passe</h1>
      <p className="mt-1 text-sm text-slate-500">Choisissez un nouveau mot de passe sécurisé.</p>
      {localError ? (
        <div className="mt-4">
          <Alert>{localError}</Alert>
        </div>
      ) : null}
      <form onSubmit={onSubmit} className="mt-6 space-y-4">
        <div>
          <label htmlFor="password" className="mb-1 block text-sm font-medium text-slate-700">
            Nouveau mot de passe
          </label>
          <Input
            id="password"
            type="password"
            required
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <p className="mt-1 text-xs text-slate-400">Au moins 8 caractères.</p>
        </div>
        <Button type="submit" className="w-full" disabled={submitting}>
          {submitting ? "Réinitialisation…" : "Réinitialiser"}
        </Button>
      </form>
    </>
  );
}