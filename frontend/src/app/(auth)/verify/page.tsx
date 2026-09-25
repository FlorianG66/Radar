"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button, Card } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";

export default function VerifyEmailPage() {
  const router = useRouter();
  const [status, setStatus] = useState<"loading" | "done" | "error">("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get("token");
    if (!token) {
      void Promise.reject(new Error("Aucun jeton de vérification fourni.")).catch((e: Error) => {
        setStatus("error");
        setMessage(e.message);
      });
      return;
    }
    api
      .post<{ message: string }>("/auth/verify-email", { token })
      .then((r) => {
        setStatus("done");
        setMessage(r.message);
      })
      .catch((e) => {
        setStatus("error");
        setMessage(errorMessage(e));
      });
  }, []);

  return (
    <div className="mt-4">
      <Card className="text-center">
        {status === "loading" ? (
          <p className="text-sm text-slate-500">Vérification de votre adresse e-mail…</p>
        ) : (
          <>
            <div className="text-3xl">{status === "done" ? "✅" : "⚠️"}</div>
            <h2
              className={
                status === "done" ? "mt-2 font-semibold text-emerald-700" : "mt-2 font-semibold text-red-700"
              }
            >
              {status === "done" ? "Email vérifié" : "Vérification impossible"}
            </h2>
            <p className="mt-2 text-sm text-slate-500">{message}</p>
            {status === "done" ? (
              <Link
                href="/dashboard"
                className="mt-4 inline-block rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
              >
                Aller au tableau de bord
              </Link>
            ) : null}
          </>
        )}
      </Card>
      <div className="mt-4 text-center">
        <Button variant="ghost" onClick={() => router.push("/login")}>
          Retour à la connexion
        </Button>
      </div>
    </div>
  );
}