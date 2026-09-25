import Link from "next/link";

const features = [
  {
    icon: "🔎",
    title: "Surveillance automatique",
    description:
      "Ajoutez un concurrent par URL et Radar vérifie la fiche produit à l'intervalle de votre plan (de 1 h à 24 h).",
  },
  {
    icon: "🛰️",
    title: "Détection de changements",
    description:
      "Baisse ou hausse de prix, retour à un ancien prix, rupture de stock, début ou fin de promotion, métadonnées produit.",
  },
  {
    icon: "📬",
    title: "Alertes par e-mail",
    description:
      "Soyez notifié en temps réel, avec des préférences par type d'événement et une protection anti-spam intelligente.",
  },
  {
    icon: "📊",
    title: "Historique & comparaison",
    description:
      "Un historique immutable par snapshot, vos propres prix en regard, et un score de variation calculé automatiquement.",
  },
  {
    icon: "📥",
    title: "Import en masse",
    description:
      "Ajoutez jusqu'à des centaines de produits en une fois grâce à l'import CSV — avec export en un clic.",
  },
  {
    icon: "💳",
    title: "Plans simples",
    description:
      "Trois offres Starter, Pro et Business avec facturation Stripe et période d'essai de 14 jours.",
  },
];

const plans = [
  {
    name: "Starter",
    price: "39 €",
    tag: "",
    features: ["50 produits", "1 vérification / jour", "Historique 30 jours", "Alertes e-mail"],
    cta: "Choisir Starter",
    highlight: false,
  },
  {
    name: "Pro",
    price: "79 €",
    tag: "Le plus populaire",
    features: ["250 produits", "4 vérifications / jour", "Historique 1 an", "Alertes avancées", "Export CSV"],
    cta: "Choisir Pro",
    highlight: true,
  },
  {
    name: "Business",
    price: "149 €",
    tag: "",
    features: ["1 000 produits", "24 vérifications / jour", "Historique illimité", "Accès API"],
    cta: "Choisir Business",
    highlight: false,
  },
];

const steps = [
  { n: "1", title: "Créez votre compte", text: "Inscription en 30 secondes, essai Pro de 14 jours sans carte bancaire." },
  { n: "2", title: "Ajoutez vos concurrents", text: "Collez les URL produits, en masse si besoin via le CSV." },
  { n: "3", title: "Recevez les alertes", text: "Radar surveille, détecte les variations et vous écrit à chaque changement important." },
];

export default function LandingPage() {
  return (
    <main className="flex-1">
      {/* Hero */}
      <section className="relative overflow-hidden">
        <div
          className="pointer-events-none absolute inset-0"
          aria-hidden="true"
          style={{
            background:
              "radial-gradient(60% 50% at 50% 0%, rgba(99,102,241,0.15) 0%, rgba(248,250,252,0) 70%)",
          }}
        />
        <div className="relative mx-auto w-full max-w-6xl px-4 pb-20 pt-20 text-center sm:pt-28">
          <p className="mb-4 inline-flex items-center gap-2 rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-600 shadow-sm ring-1 ring-slate-200">
            <span className="size-1.5 rounded-full bg-emerald-500" />
            Nouveau : import CSV et export en un clic
          </p>
          <h1 className="mx-auto max-w-3xl text-4xl font-bold tracking-tight text-slate-900 sm:text-6xl">
            Voyez le changement chez vos concurrents{" "}
            <span className="bg-gradient-to-r from-indigo-600 to-violet-600 bg-clip-text text-transparent">
              avant le marché.
            </span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-slate-600">
            Radar surveille les prix, la disponibilité et les promotions des produits de vos
            concurrents, détecte chaque variation et vous alerte automatiquement.
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link
              href="/register"
              className="rounded-xl bg-indigo-600 px-6 py-3 text-base font-semibold text-white shadow-sm hover:bg-indigo-500"
            >
              Démarrer l&apos;essai gratuit
            </Link>
            <Link
              href="/login"
              className="rounded-xl bg-white px-6 py-3 text-base font-semibold text-slate-700 shadow-sm ring-1 ring-inset ring-slate-300 hover:bg-slate-50"
            >
              Se connecter
            </Link>
          </div>
          <p className="mt-4 text-xs text-slate-400">14 jours offerts — sans carte bancaire</p>
        </div>
      </section>

      {/* Features */}
      <section id="fonctionnalites" className="mx-auto w-full max-w-6xl px-4 py-16">
        <h2 className="text-center text-3xl font-bold tracking-tight text-slate-900">
          Tout ce qu&apos;il faut pour garder un œil sur la concurrence
        </h2>
        <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f) => (
            <div key={f.title} className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="flex size-11 items-center justify-center rounded-lg bg-indigo-50 text-xl">
                {f.icon}
              </div>
              <h3 className="mt-4 font-semibold text-slate-900">{f.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-600">{f.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section id="comment" className="bg-white py-16">
        <div className="mx-auto w-full max-w-6xl px-4">
          <h2 className="text-center text-3xl font-bold tracking-tight text-slate-900">
            Comment ça marche
          </h2>
          <div className="mt-12 grid gap-8 md:grid-cols-3">
            {steps.map((s) => (
              <div key={s.n} className="relative text-center">
                <div className="mx-auto flex size-12 items-center justify-center rounded-full bg-indigo-600 text-lg font-bold text-white">
                  {s.n}
                </div>
                <h3 className="mt-4 font-semibold text-slate-900">{s.title}</h3>
                <p className="mx-auto mt-2 max-w-xs text-sm text-slate-600">{s.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="tarifs" className="mx-auto w-full max-w-6xl px-4 py-16">
        <h2 className="text-center text-3xl font-bold tracking-tight text-slate-900">
          Des plans simples, sans surprise
        </h2>
        <p className="mx-auto mt-3 max-w-xl text-center text-slate-600">
          Sans engagement, annulable à tout moment depuis votre espace de facturation.
        </p>
        <div className="mt-12 grid gap-6 lg:grid-cols-3">
          {plans.map((p) => (
            <div
              key={p.name}
              className={
                p.highlight
                  ? "relative rounded-2xl border-2 border-indigo-600 bg-white p-6 shadow-lg"
                  : "relative rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
              }
            >
              {p.tag ? (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-indigo-600 px-3 py-1 text-xs font-semibold text-white">
                  {p.tag}
                </span>
              ) : null}
              <h3 className="text-lg font-semibold text-slate-900">{p.name}</h3>
              <p className="mt-3 text-3xl font-bold text-slate-900">
                {p.price}
                <span className="text-sm font-normal text-slate-400"> / mois</span>
              </p>
              <ul className="mt-6 space-y-3">
                {p.features.map((f) => (
                  <li key={f} className="flex items-start gap-2 text-sm text-slate-700">
                    <span className="mt-0.5 text-emerald-600">✓</span>
                    {f}
                  </li>
                ))}
              </ul>
              <Link
                href="/register"
                className={
                  p.highlight
                    ? "mt-8 block rounded-xl bg-indigo-600 px-4 py-2.5 text-center text-sm font-semibold text-white hover:bg-indigo-500"
                    : "mt-8 block rounded-xl bg-white px-4 py-2.5 text-center text-sm font-semibold text-slate-700 ring-1 ring-inset ring-slate-300 hover:bg-slate-50"
                }
              >
                {p.cta}
              </Link>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="bg-slate-900 py-16 text-center">
        <div className="mx-auto w-full max-w-2xl px-4">
          <h2 className="text-3xl font-bold tracking-tight text-white">
            Prêt à surveiller vos concurrents ?
          </h2>
          <p className="mt-3 text-slate-300">
            Rejoignez Radar et ne ratez plus aucune baisse de prix stratégique.
          </p>
          <Link
            href="/register"
            className="mt-8 inline-block rounded-xl bg-indigo-500 px-6 py-3 text-base font-semibold text-white hover:bg-indigo-400"
          >
            Créer mon compte gratuit
          </Link>
        </div>
      </section>
    </main>
  );
}