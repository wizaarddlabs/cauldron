# 🧉Cauldron
🧙 A modular, open-source torrent & debrid aggregation engine for Stremio

.Torrentio-Debrid
An open-source torrent search + debrid resolution service, It works as:
A Stremio addon — install your own personal URL (with your debrid API
key baked in) and get streams straight in the Stremio app.
A standalone REST API — `/api/search`, `/api/availability`,
`/api/resolve` for building your own frontend or scripts.
How it works
```
Stremio / your app
        │
        ▼
  FastAPI service  ──────►  Jackett (your own instance)  ──► indexers YOU configure
        │
        ▼
  Debrid provider (Real-Debrid / AllDebrid / Premiumize / TorBox)
        │
        ▼
  Direct playback link
```
This project does not scrape or hardcode any specific torrent tracker.
Instead it talks to Jackett, which you
run yourself and configure with whatever indexers you choose in its web UI.
This keeps the source-discovery layer pluggable and under your control —
the same architecture Comet and MediaFusion use.
Supported debrid providers
Real-Debrid
AllDebrid
Premiumize
TorBox
Adding another provider = implement `app/debrid/base.py`'s `DebridClient`
interface and register it in `app/debrid/factory.py`.
Quick start (Docker)
```bash
git clone <your-repo-url>
cd torrentio-debrid
cp .env.example .env

docker compose up -d
```
Open `http://localhost:9117` (Jackett), add the indexers you want,
copy its API key into `.env` as `JACKETT_API_KEY`, then
`docker compose up -d` again to pick it up.
The app is now live at `http://localhost:8000`.
Installing as a Stremio addon
Generate your personal config segment (embeds your debrid provider + key,
never stored server-side):
```bash
python scripts/make_config.py realdebrid YOUR_RD_API_KEY
```
This prints an install URL like:
```
http://localhost:8000/<config>/manifest.json
```
Paste that into Stremio's "Add addon via URL" field.
REST API
```bash
# Search across all configured scrapers
curl "http://localhost:8000/api/search?q=your+query"

# Check which results are instantly cached on your debrid account
curl "http://localhost:8000/api/availability?q=your+query&provider=realdebrid&api_key=YOUR_KEY"

# Resolve a magnet to a direct playback link
curl -X POST http://localhost:8000/api/resolve \
  -H "Content-Type: application/json" \
  -d '{"provider":"realdebrid","api_key":"YOUR_KEY","magnet":"magnet:?xt=urn:btih:..."}'
```
Full interactive docs at `http://localhost:8000/docs` (FastAPI's built-in
Swagger UI).
Local development (without Docker)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in JACKETT_URL / JACKETT_API_KEY

uvicorn app.main:app --reload
```
Project layout
```
app/
├── main.py                 FastAPI app + router registration
├── config.py                Settings (env-driven)
├── models.py                 Shared Pydantic models
├── api/
│   ├── routes.py            REST API: /search /availability /resolve
│   └── stremio.py           Stremio addon protocol: /manifest.json /stream/...
├── scrapers/
│   ├── base.py               Scraper interface — implement this to add a source
│   ├── jackett_scraper.py    Default source: your Jackett instance
│   └── aggregator.py         Fans queries out to all registered scrapers
├── debrid/
│   ├── base.py                DebridClient interface — implement to add a provider
│   ├── realdebrid.py / alldebrid.py / premiumize.py / torbox.py
│   └── factory.py             Provider name → client instance
└── cache/
    └── store.py               Redis-backed cache, in-memory fallback
```
Extending
Add a new torrent source: subclass `Scraper` in `app/scrapers/`,
implement `search()`, register it in `app/scrapers/aggregator.py`.
Add a new debrid provider: subclass `DebridClient` in `app/debrid/`,
implement the four abstract methods, register it in
`app/debrid/factory.py` and add it to the `DebridProvider` enum in
`app/models.py`.
Legal note
This project is infrastructure: it indexes what you point it at (via your
own Jackett config) and interfaces with debrid services you already have
accounts with. What you do with it, and whether that's lawful in your
jurisdiction, is your responsibility. No content is hosted or distributed
by this codebase itself.
