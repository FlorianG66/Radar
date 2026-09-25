"use client";

import { useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { Button, Card, Input } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import type { CsvPreview, CsvResult } from "@/types";

export default function ImportPage() {
  const [preview, setPreview] = useState<CsvPreview | null>(null);
  const [result, setResult] = useState<CsvResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onFile(file: File | undefined) {
    if (!file) return;
    setError(null);
    setResult(null);
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", file);
      setPreview(await api.upload<CsvPreview>("/imports/csv/preview", form));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function confirm() {
    if (!preview) return;
    setBusy(true);
    setError(null);
    try {
      const r = await api.post<CsvResult>("/imports/csv", {
        rows: preview.valid_rows,
        ignore_invalid: true,
      });
      setResult(r);
      setPreview(null);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Import / Export"
        description="Importez vos produits concurrents en masse depuis un fichier CSV, ou exportez votre liste actuelle."
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <h2 className="font-semibold text-slate-900">Importer un CSV</h2>
          <p className="mt-1 text-sm text-slate-500">
            Format : <code className="rounded bg-slate-100 px-1 text-xs">url,nom,concurrent,categorie,sku</code>. Seule la
            colonne <code className="rounded bg-slate-100 px-1 text-xs">url</code> est obligatoire.
          </p>
          <div className="mt-4">
            <Input
              type="file"
              accept=".csv,.txt"
              disabled={busy}
              onChange={(e) => void onFile(e.target.files?.[0])}
            />
          </div>

          {error ? (
            <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
          ) : null}

          {preview ? (
            <div className="mt-5">
              <p className="text-sm text-slate-700">
                <strong className="text-emerald-600">{preview.valid_rows.length}</strong> ligne(s) valide(s)
                {preview.invalid_rows.length > 0 ? (
                  <span className="text-red-600"> · {preview.invalid_rows.length} invalide(s)</span>
                ) : null}
              </p>
              {preview.errors.length > 0 ? (
                <ul className="mt-2 list-inside list-disc space-y-0.5 text-xs text-red-600">
                  {preview.errors.slice(0, 10).map((e, i) => (
                    <li key={i}>{e}</li>
                  ))}
                </ul>
              ) : null}
              {preview.valid_rows.length > 0 ? (
                <div className="mt-3 max-h-48 overflow-y-auto rounded-lg border border-slate-200">
                  <table className="min-w-full text-xs">
                    <thead className="bg-slate-50 text-left text-slate-500">
                      <tr>
                        <th className="px-3 py-2 font-medium">URL</th>
                        <th className="px-3 py-2 font-medium">Nom</th>
                        <th className="px-3 py-2 font-medium">Concurrent</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {preview.valid_rows.slice(0, 20).map((r, i) => (
                        <tr key={i}>
                          <td className="max-w-[200px] truncate px-3 py-1.5">{r.url}</td>
                          <td className="px-3 py-1.5">{r.name || "—"}</td>
                          <td className="px-3 py-1.5">{r.competitor || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
              <Button className="mt-4" onClick={() => void confirm()} disabled={busy || preview.valid_rows.length === 0}>
                {busy ? "Import en cours…" : "Confirmer l'import"}
              </Button>
            </div>
          ) : null}

          {result ? (
            <div className="mt-5 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-3 text-sm text-emerald-700">
              Import terminé : <strong>{result.imported}</strong> ajouté(s), <strong>{result.skipped}</strong> ignoré(s).
              {result.errors.length > 0 ? (
                <ul className="mt-2 list-inside list-disc text-xs">
                  {result.errors.slice(0, 5).map((e, i) => (
                    <li key={i}>{e}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}
        </Card>

        <Card>
          <h2 className="font-semibold text-slate-900">Exporter</h2>
          <p className="mt-1 text-sm text-slate-500">
            Téléchargez la liste de vos produits actuellement surveillés (nom, URL, concurrent, dernier prix…).
          </p>
          <Button
            className="mt-4"
            variant="outline"
            onClick={() => {
              fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/exports/products.csv`, {
                headers: { Authorization: `Bearer ${localStorage.getItem("radar.access_token") ?? ""}` },
              })
                .then((r) => (r.ok ? r.text() : Promise.reject(new Error("Export impossible"))))
                .then((csv) => {
                  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = "radar-products.csv";
                  a.click();
                  URL.revokeObjectURL(url);
                })
                .catch(() => undefined);
            }}
          >
            Télécharger radar-products.csv
          </Button>
        </Card>
      </div>
    </>
  );
}