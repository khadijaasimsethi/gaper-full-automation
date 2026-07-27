# Gaper Backlink Agent V2

An AI-powered automation system that discovers relevant platforms and conversations, generates contextual content with Gemini, and (after human approval) publishes backlinks and citations for Gaper — built for SEO, GEO (Generative Engine Optimization), and AEO (Answer Engine Optimization).

**Live deployment:** `https://khadija-gaper-api-509682134216.us-central1.run.app`

---

## What It Does

Instead of manually searching for backlink opportunities and writing outreach content, this system:

1. **Discovers** relevant threads, communities, and listing directories where Gaper can be mentioned
2. **Reads** the target page content using a layered fallback strategy (API/RSS → static scraping → authenticated browser → LLM vision), since many sites block simple scrapers
3. **Generates** a contextual reply or article with Gemini, grounded in Gaper's actual case studies and USPs (lightweight RAG)
4. **Waits for human review** — every draft is approved, edited, or discarded on the dashboard before anything goes live
5. **Publishes** using saved login sessions, once approved
6. **Monitors** posted backlinks, re-checking after 7 days to confirm they're still live

---

## Dashboard Tabs

| Tab | Purpose |
|---|---|
| **Overview** | Brand profile + system stats |
| **Articles** | Generate → edit → improve → submit flow for Contra/Notion/Dev.to |
| **New Backlinks** | Everything actually posted live; edit/delete where the platform API allows it |
| **Listing Pitcher** | Directory listings where Gaper is missing — auto-fill and submit |
| **Logs & Discovery** | Run discovery jobs, view live system logs |
| **QA Approvals** | Legacy thread-reply approval queue |

---

## Tech Stack

- **Backend:** Python 3.10, FastAPI, Uvicorn
- **Scraping/Automation:** Playwright, BeautifulSoup, lxml
- **AI:** Google Gemini API
- **Database:** SQLAlchemy ORM — SQLite locally, migrating to Turso db for persistent cloud storage
- **Background jobs (optional):** Celery + Redis (currently disabled via `USE_CELERY=False`)
- **Deployment:** Docker on Google Cloud Run (serverless, scale-to-zero)

---

## Supported Platforms

**Active:** Contra, Notion, Dev.to
**Configured but inactive:** IndieHackers, Peerlist, Substack, Hashnode

---

## Local Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
playwright install chromium

# Copy .env.example to .env and fill in your keys
python run.py --dashboard
```
Dashboard runs at `http://localhost:8000`.

### Required environment variables
```
GEMINI_API_KEY=
SERPER_API_KEY=
CAPTCHA_API_KEY=
CONTRA_EMAIL=
NOTION_API_KEY=
NOTION_DATABASE_URL=
DEVTO_API_KEY=
```

---

## Cloud Deployment (Google Cloud Run)

Deployed as a minimal, cost-conscious serverless service — no VMs, no Kubernetes.

```bash
gcloud run deploy khadija-gaper-api \
  --source . \
  --region us-central1 \
  --min-instances 0 \
  --memory 2Gi \
  --timeout 600 \
  --allow-unauthenticated \
  --set-env-vars="GEMINI_API_KEY=...,SERPER_API_KEY=...,CAPTCHA_API_KEY=...,CONTRA_EMAIL=...,NOTION_API_KEY=...,NOTION_DATABASE_URL=...,DEVTO_API_KEY=..."
```

**Config notes:**
- `min-instances 0` → $0 cost while idle
- `memory 2Gi` → required for Playwright's Chromium; 512Mi causes silent startup failures
- `timeout 600` → scraping + Gemini calls can take 2–3 minutes per request
- Base image: `mcr.microsoft.com/playwright/python:v1.42.0-jammy` (avoids OS package mismatches from installing Playwright deps manually)

---

## Known Limitations / In Progress

- **Persistent storage:** SQLite resets on every container restart on Cloud Run (stateless). Migration to Supabase Postgres is in progress so data survives redeploys and scale-to-zero cycles.
- **Session freshness:** Login sessions (Contra, Notion, etc.) are baked into the Docker image at build time. If a session expires, it must be regenerated locally (`setup_<platform>_login.py`) and redeployed.
- **Legacy pipeline:** `ThreadMemory`/QA Approvals is an earlier version of the workflow, superseded by the Articles tab (`ArticleDraft` → `PostedBacklink`). "Citations Posted" stat reflects only the legacy pipeline and will show 0 under normal use.
- **CI/CD automation:** Currently deployed manually via `gcloud run deploy`. GitHub Actions workflow for automatic deploy-on-push is drafted but not yet wired up with Workload Identity Federation.

---

## Architecture

```
GitHub → GitHub Actions (planned) → Docker build → Artifact Registry
                                                          ↓
                                                     Cloud Run service
                                                    ↙            ↘
                                          Secret Manager      TURSO(planned)
