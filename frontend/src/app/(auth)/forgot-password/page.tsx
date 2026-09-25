"use client";

import { FormEvent, useState } from "react";

import { Alert, Button, Input } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api.post<{ message: string }>("/auth/forgot-password", { email });
      setSent(true);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  if (sent) {
    return (
      <div className="text-center">
        <div className="text-3xl">📬</div>
        <h1 className="mt-3 text-lg font-semibold text-slate-900">Email envoyé</h1>
        <p className="mt-2 text-sm text-slate-500">
          Si un compte existe pour cette adresse, un lien de réinitialisation vient d&apos;être envoyé.
        </p>
        <Button variant="ghost" className="mt-5 w-full" onClick={() => (window.location.replace("/login"))}>
          Retour à la connexion
        </Button>
      </div>
    );
  }

  return (
    <>
      <h1 className="text-xl font-semibold text-slate-900">Mot de passe oublié</h1>
      <p className="mt-1 text-sm text-slate-500">
        Saisissez votre email, nous vous enverrons un lien de réinitialisation.
      </p>
      {error ? (
        <div className="mt-4">
          <Alert>{error}</Alert>
        </div>
      ) : null}
      <form onSubmit={onSubmit} className="mt-6 space-y-4">
        <div>
          <label htmlFor="email" className="mb-1 block text-sm font-medium text-slate-700">
            Email
          </label>
          <Input
            id="email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <Button type="submit" className="w-full" disabled={submitting}>
          {submitting ? "Envoi…" : "Envoyer le lien"}
        </Button>
      </form>
    </>
  );
}