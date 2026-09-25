# Radar 📡

Surveillance de la concurrence : Radar suit les prix, la disponibilité et les
promotions des produits de vos concurrents, détecte chaque variation et vous
alerte automatiquement par e-mail.

## Architecture

```
frontend/   Next.js 16 (App Router, TypeScript, Tailwind v4)
backend/    FastAPI + SQLAlchemy 2 + Alembic + RQ + Playwright
docker-compose.yml
```

```
API                 (FastAPI — ne scrape jamais dans les handlers)
  ↓
Scheduler  ───────►  Redis queue (RQ)  ───────►  Workers  ──────►  DB / notifications
  │
  └─ maintenance : élagage de l'historique, nettoyage des jobs
```

| Service  | Techno                                                    |
|----------|-----------------------------------------------------------|
| API      | FastAPI (`/docs` Swagger), SQLAlchemy, Alembic migrations |
| Queue    | RQ + Redis                                                |
| Scraper  | HTTP + BeautifulSoup + extracteurs dédiés, fallback Playwright |
| Worker   | consomme la file, recalcule les détections (baisse/hausse, promo, stock) |
| Notif.   | e-mail (SMTP), préférences par événement, anti-spam 12 h   |
| Factu.   | Stripe (checkout + portail client), essai 14 jours        |
| Frontend | Next.js 16 App Router, auth par JWT (access + refresh)    |

## Démarrage local (sans Docker)

Prérequis : Python 3.12, Node 20+.

1. **Backend**

   ```bash
   cd backend
   python -m venv .venv
   .venv\Scripts\activate        # Windows (sinon : source .venv/bin/activate)
   pip install -r requirements.txt
   copy .env.example .env        # puis adaptez si besoin (SMTP console par défaut)
   cd ..
   ```

   Lancement tout-en-un (API :8000 + scheduler + worker + boutique de démo :8080) :

   ```bash
   cd backend
   python -m scripts.dev_local
   ```

   Le compte de démonstration est `demo@radar.app` / `demo12345!`.

   Pour séparer les processus en production :

   ```bash
   alembic upgrade head
   uvicorn app.main:app --host 0.0.0.0 --port 8000   # API
   python -m app.workers.worker                       # worker RQ
   python -m app.workers.scheduler                    # scheduler
   ```

2. **Frontend**

   ```bash
   cd frontend
   npm install
   copy .env.example .env.local     # NEXT_PUBLIC_API_URL=http://localhost:8000
   npm run dev                      # http://localhost:3000
   ```

   Validation : `npm run lint` puis `npm run build`.

## Démarrage avec Docker

```bash
cp .env.example backend/.env          # adaptez SECRET_KEY / Stripe si besoin
docker compose up --build
```

Services exposés :

- Frontend : http://localhost:3000
- API + Swagger : http://localhost:8000/docs

Postgres et Redis restent internes au réseau compose. Les migrations Alembic
sont appliquées automatiquement au démarrage de l'API. Pour activer Stripe,
renseignez `STRIPE_SECRET_KEY` (et les prix) dans votre environnement.

## Tests

```bash
cd backend
.venv\Scripts\activate
python -m pytest            # 113 tests : API, auth, produits, scraping, workers…
```

## Fonctionnalités

- **Dashboard** : produits suivis, changements détectés (7 j), statut du scraping.
- **Produits** : ajout par URL (une ou plusieurs à la fois), détection auto du nom/prix/promo, historique, graphe d'évolution, comparaison avec votre propre prix de référence.
- **Changements** : journal filtrable (baisse, hausse, retour au prix initial, rupture/retour en stock, promotions, échecs de scraping).
- **Import/Export CSV** : `url,nom,concurrent,categorie,sku`.
- **Notifications** : préférences par type d'événement, historique des envois.
- **Facturation** : plans Starter (XX €) / Pro (XX €) / Business (XX €) / mois, essai 14 jours, portail Stripe.
- **Administration** : stats globales, listes des organisations, activation/désactivation des extracteurs par domaine.

## Extend the platform

Les extracteurs par domaine vivent dans `backend/app/services/scraper/`
(registry `domains.py` keyé par nom d'hôte, générique dans `extractor.py`).
Les plans se configurent dans `backend/app/core/plans.py`.

## Licence

Code source publié pour consultation. **Tous droits réservés** — aucune licence
ouverte n'est accordée : la reproduction, la modification et la réutilisation du
code, en tout ou partie, sont interdites sans autorisation écrite préalable.

Projet en cours de développement, non achevé.