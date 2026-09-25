"use client";

import { FormEvent, useEffect, useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { Alert, Button, Card, Input } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { Organization, User } from "@/types";

export default function SettingsPage() {
  const [user, setUser] = useState<User | null>(null);
  const [org, setOrg] = useState<Organization | null>(null);
  const [globalError, setGlobalError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.get<User>("/auth/me"), api.get<Organization>("/auth/me/org")])
      .then(([u, o]) => {
        setUser(u);
        setOrg(o);
      })
      .catch((e) => setGlobalError(errorMessage(e)));
  }, []);

  return (
    <>
      <PageHeader title="Paramètres" description="Votre profil et les informations de votre organisation." />
      {globalError ? (
        <Card>
          <p className="text-sm text-red-600">{globalError}</p>
        </Card>
      ) : null}
      <div className="grid gap-6 lg:grid-cols-2">
        {user ? (
          <>
            <ProfileCard user={user} onSaved={setUser} />
            <PasswordCard />
          </>
        ) : null}
        {org ? <OrgCard org={org} onSaved={setOrg} /> : null}
      </div>
    </>
  );
}

function ProfileCard({ user, onSaved }: { user: User; onSaved: (u: User) => void }) {
  const [first_name, setFirstName] = useState(user.first_name);
  const [last_name, setLastName] = useState(user.last_name);
  const [email, setEmail] = useState(user.email);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const u = await api.patch<User>("/auth/me", { first_name, last_name, email });
      onSaved(u);
      setMsg("Profil mis à jour.");
    } catch (e2) {
      setErr(errorMessage(e2));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h2 className="font-semibold text-slate-900">Profil</h2>
      <form onSubmit={submit} className="mt-4 space-y-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Prénom</label>
            <Input value={first_name} onChange={(e) => setFirstName(e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Nom</label>
            <Input value={last_name} onChange={(e) => setLastName(e.target.value)} />
          </div>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">Email</label>
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        {err ? <Alert>{err}</Alert> : null}
        {msg ? <Alert tone="green">{msg}</Alert> : null}
        <Button type="submit" disabled={busy}>
          {busy ? "Enregistrement…" : "Enregistrer"}
        </Button>
        <p className="text-xs text-slate-400">
          {user.email_verified_at
            ? `Email vérifié le ${formatDate(user.email_verified_at)}`
            : "Email non vérifié — vérifiez votre boîte mail."}
          {user.is_admin ? " · Compte administrateur" : ""}
        </p>
      </form>
    </Card>
  );
}

function PasswordCard() {
  const [current_password, setCurrent] = useState("");
  const [new_password, setNew] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const r = await api.post<{ message: string }>("/auth/me/password", { current_password, new_password });
      setMsg(r.message);
      setCurrent("");
      setNew("");
    } catch (e2) {
      setErr(errorMessage(e2));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h2 className="font-semibold text-slate-900">Mot de passe</h2>
      <form onSubmit={submit} className="mt-4 space-y-3">
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">Mot de passe actuel</label>
          <Input type="password" value={current_password} onChange={(e) => setCurrent(e.target.value)} />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">Nouveau mot de passe</label>
          <Input type="password" value={new_password} onChange={(e) => setNew(e.target.value)} />
        </div>
        {err ? <Alert>{err}</Alert> : null}
        {msg ? <Alert tone="green">{msg}</Alert> : null}
        <Button type="submit" disabled={busy}>
          {busy ? "Mise à jour…" : "Modifier le mot de passe"}
        </Button>
      </form>
    </Card>
  );
}

function OrgCard({ org, onSaved }: { org: Organization; onSaved: (o: Organization) => void }) {
  const [name, setName] = useState(org.name);
  const [email, setEmail] = useState(org.email);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const o = await api.patch<Organization>("/auth/me/org", { name, email });
      onSaved(o);
      setMsg("Organisation mise à jour.");
    } catch (e2) {
      setErr(errorMessage(e2));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h2 className="font-semibold text-slate-900">Organisation</h2>
      <form onSubmit={submit} className="mt-4 space-y-3">
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">Nom</label>
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">Email de facturation</label>
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        {err ? <Alert>{err}</Alert> : null}
        {msg ? <Alert tone="green">{msg}</Alert> : null}
        <Button type="submit" disabled={busy}>
          {busy ? "Enregistrement…" : "Enregistrer"}
        </Button>
        <p className="text-xs text-slate-400">Créée le {formatDate(org.created_at)}.</p>
      </form>
    </Card>
  );
}