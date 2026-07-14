# Gaper AI Backlink & Citation Assembly Line (V2)

An automated, highly-optimized AI Agent pipeline specifically designed for **Gaper** (gaper.io) to acquire backlinks and brand citations that satisfy **Search Engine Optimization (SEO)**, **Generative Engine Optimization (GEO)**, and **Answer Engine Optimization (AEO)** requirements.

The architecture is built as a modular **7-block AI Assembly Line** using the Strategy and Factory design patterns.

---

## 🚀 The 7-Block Architecture

```
                       [ 1. Discovery (SERP/RSS) ]
                                    │
                       [ 2. Memory (SQLite DB) ]
                                    │
                  [ 3 & 4. Ingestion & Waterfall ]
                     (Soup ➔ Playwright ➔ Gemini)
                                    │
                      [ 5. Brain (Gemini & QA) ]
                                    │
                    [ 6. Adapters (Platform Factory) ]
                (IndieHackers/Contra/Peerlist/Outreach)
                                    │
                      [ 7. Pipeline (Broker Queue) ]
```

1. **The Front Door (Discovery & Filtering):** Combines RSS feeds and Google SERP dorks, deduplicates URLs, and filters past runs using SQLite memory.
2. **System Memory (Database & Caching):** SQLite zero-config engine. Keeps track of comment counts (so we only re-process if there are new comments) and caches guidelines (30-day TTL).
3. **Ingestion Strategies:** strategy pattern implementing:
   - `Type1ApiRss` (Fast direct JSON parsing)
   - `Type2StaticSoup` (Requests/BS4 fallback)
   - `Type3PlaywrightAuth` (Headless browser automation)
   - `Type4LlmVision` (Multimodal LLM fallback to parse messy page outputs)
4. **Waterfall Escalation:** Escalates through ingestion types on failure (Type 2 ➔ 3 ➔ 4) and saves the successful type by domain to optimize future runs.
5. **AI Brain & QA Loop:** Uses Gemini to craft structured replies. Automatically shifts to **Ghost Mode** (no promotion link) if community rules forbid it. Includes a 3-iteration human-feedback QA Loop.
6. **Execution Adapters:** Factory pattern supplying handlers for **IndieHackers**, **Contra**, **Notion**, **Substack**, **Pinterest**, and **Peerlist**. Also handles SMTP email **Outreach** pitches for directories missing Gaper.
7. **Pipeline Tasks:** Rate-limits posts (max 10/min) using Celery or a thread-based local broker queue. Bypasses 7-day tracking verification for Ghost Posts.

---

## 🛠️ Setup & Installation

1. **Create Environment Configuration:**
   Copy `.env.example` to `.env` and fill in your Gemini API Key and platform credentials.
   ```bash
   cp .env.example .env
   ```

2. **Install Dependencies:**
   Ensure you have Python 3.9+ installed, then run:
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Browser Binaries (for Playwright):**
   ```bash
   playwright install chromium
   ```

---

## 💻 How to Run

- **Launch Interactive Web Dashboard (Highly Recommended):**
  Open the QA Panel to review drafts, approve postings, and view directory outreach lists.
  ```bash
  python run.py --dashboard
  ```
  Then open `http://localhost:8000` in your web browser.

- **Trigger Discovery:**
  Runs search engine scraping and RSS parsers to fetch target threads.
  ```bash
  python run.py --discover
  ```

- **Update Brand Profile:**
  Connects to Gaper.io and updates description and logo details.
  ```bash
  python run.py --scrape-brand
  ```

- **Process a Single URL via CLI:**
  ```bash
  python run.py --process "https://www.indiehackers.com/post/best-platforms-to-hire-developers-for-startups-3f982d"
  ```
