# Radar

Surveillez les prix, la disponibilité et les promotions chez vos concurrents — et soyez alerté automatiquement à chaque changement.

Radar est un SaaS de veille concurrentielle : il scrute périodiquement les fiches produits de vos concurrents, détecte les changements (baisse/hausse de prix, rupture de stock, début/fin de promotion…) et vous notifie en temps réel.

## Fonctionnalités

- **Surveillance de produits concurrents** : ajout par URL, scraping automatique à intervalle configurable (de 1 h à 24 h selon le plan).
- **Détection de changements** : prix, disponibilité, promotions, et métadonnées produit (nom, SKU, EAN), avec historique immutable par snapshot.
- **Alertes** : notifications par e-mail, filtrables par type d'événement (préférences par utilisateur).
- **Dashboard** : produits suivis, événements récents, état des scrapes, monitorings du service (`/health`, `/docs`).
- **Import** : ajout de produits en masse via URL ou CSV.
- **Comparaison** : saisie optionnelle de votre propre prix pour comparer face aux concurrents.
- **Billing Stripe** : 3 plans (Starter, Pro, Business) avec limites d'utilisation appliquées côté serveur, période d'essai de 14 jours.
- **Multi-organisation** : comptes utilisateurs rattachés à une organisation.
- **Kill-switch par domaine** : désactivation d'un domaine chez un concurrent en cas de requête abusive (admin).

## Architecture

```
┌─────────────┐   ┌──────────────────┐   ┌──────────────┐
│   frontend   │──▶│   backend (API)  │──▶│   Postgres   │
│   (Next.js)  │   │    FastAPI       │   └──────────────┘
└─────────────┘   └────────┬─────────┘   ┌──────────────┐
                           │              │    Redis      │
                     ┌─────▼─────┐        └──────┬───────┘
                     │  RQ queue  │◀─────── RQ schedulers
                     └─────┬─────┘        (scrape + notifications)
                           │
                    ┌──────▼──────┐
                    │   Worker     │
                    │  Playwright  │── scraping sites concurrents
                    └─────────────┘
```

- **API** : FastAPI, SQLAlchemy 2.0, Alembic pour les migrations, schémas Pydantic v2.
- **Scraping** : pipeline `fetch → extracteur spécifique domaine → extracteur générique → normalisation`. Réseau + navigation via `httpx` et **Playwright** pour les sites nécessitant du JavaScript. Un échec de scraping est tracé comme `ScrapeJob` échoué et ne produit jamais de changement de prix.
- **Pipeline de jobs** : Redis + **RQ**. Un worker traite les files `scrape` et `notifications` ; un scheduler planifie les prochaines vérifications.
- **Détection de changements** : moteur pur (`detection.py`) qui compare le dernier snapshot au précédent et émet des événements typés (priorisé `high` / `medium` / `low`).
- **Paiements** : Stripe (checkout + webhooks), plans définis côté serveur dans `app/core/plans.py`.

## Structure du dépôt

```
.
├── backend/                  # API FastAPI + workers RQ
│   ├── alembic/              # Migrations de base de données
│   ├── app/
│   │   ├── api/routes/       # health, auth, products, dashboard, imports, subscription, admin
│   │   ├── core/             # config, db, redis, security, plans, logging
│   │   ├── mail/             # envoi d'e-mails (backend console | smtp)
│   │   ├── models.py         # Schéma SQLAlchemy complet
│   │   ├── schemas.py        # Schémas Pydantic
│   │   ├── services/         # auth, scraper/, detection, product, import, notifications, stripe, subscription
│   │   └── workers/          # worker RQ, tasks, scheduler
│   ├── scripts/              # scripts d'administration
│   └── tests/
├── frontend/                 # Application Next.js (en cours d'implémentation)
└── .github/workflows/        # CI
```

## Démarrage rapide (back-end)

### Prérequis

- Python 3.11+
- PostgreSQL
- Redis

### Installation

```bash
cd backend
python -m venv .venv
# Windows : .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Configurer `.env` (Postgres, Redis, `SECRET_KEY` — voir section Configuration).

### Base de données

```bash
alembic upgrade head
```

### Lancer l'API

```bash
uvicorn app.main:app --reload --port 8000
```

- Docs Swagger : http://localhost:8000/docs
- Healthcheck : http://localhost:8000/health

### Lancer le worker et le scheduler

```bash
python -m app.workers.worker        # traite les scrapes + notifications
python -m app.workers.scheduler     # planifie les prochaines vérifications
```

### Playwright (scraping JavaScript)

```bash
playwright install chromium
```

### Tests

```bash
pytest
```

## Configuration (.env)

Les variables principales : `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `SMTP_BACKEND` (`console` pour afficher les e-mails en développement, `smtp` en production), clés Stripe (`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_*`), et les limites de scraping (`MAX_CONCURRENT_SCRAPES`, `SCRAPE_TIMEOUT_SECONDS`). Voir `backend/.env.example` pour la liste complète.

## Plans

| Plan      | Prix / mois | Produits | Vérifications / jour | Historique | Fonctions                        |
|-----------|-------------|----------|----------------------|------------|----------------------------------|
| Starter   | 39 €        | 50       | 1                    | 30 jours   | Alertes e-mail                   |
| Pro       | 79 €        | 250      | 4                    | 1 an       | + alertes avancées, export CSV   |
| Business  | 149 €       | 1000     | 24                   | Illimité   | + API                            |

## Roadmap

- [x] Backend : API, scraping, détection, notifications e-mail, billing Stripe
- [x] *Kill-switch* par domaine (désactivation admin en cas d'abus)
- [ ] Frontend Next.js (auth, dashboard produits, fil d'événements, page tarifs)
- [ ] Export CSV et API publique (plans Pro/Business)
- [ ] Notifications push / Slack / Discord

## Licence

Projet privé. Tous droits réservés.