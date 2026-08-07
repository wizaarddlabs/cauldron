# 🧙🏻‍♂️Cauldron
A modular, open-source torrent & debrid aggregation engine for Stremio

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
  FastAPI service  ──────►  Public Torrent Sites (TPB, 1337x, YTS, Nyaa)
        │
        ▼
  Debrid provider (Real-Debrid / AllDebrid / Premiumize / TorBox)
        │
        ▼
  Direct playback link
```
This project uses built-in scrapers for public torrent sites (The Pirate Bay,
1337x, YTS, Nyaa) to find content, which is then resolved through your debrid
provider for premium streaming. This keeps the architecture simple and
doesn't require external indexer management like Jackett or Prowlarr.
Supported debrid providers
- Real-Debrid
- AllDebrid
- Premiumize
- TorBox
Adding another provider = implement `app/debrid/base.py`'s `DebridClient`
interface and register it in `app/debrid/factory.py`.
Quick start (Docker)
```bash
git clone <your-repo-url>
cd cauldron
cp .env.example .env

docker compose up -d
```
The app is now live at `http://localhost:8000`. No additional configuration needed - it uses public torrent search APIs by default.
Installing as a Stremio addon
Generate your personal config segment (embeds your debrid provider + key,
never stored server-side):
```bash
# For Real-Debrid
python scripts/make_config.py realdebrid YOUR_RD_API_KEY

# For AllDebrid
python scripts/make_config.py alldebrid YOUR_AD_API_KEY

# For Premiumize
python scripts/make_config.py premiumize YOUR_PM_API_KEY

# For TorBox
python scripts/make_config.py torbox YOUR_TB_API_KEY
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
curl "http://localhost:8000/api/availability?q=your+query&provider=alldebrid&api_key=YOUR_KEY"

# Resolve a magnet to a direct playback link
curl -X POST http://localhost:8000/api/resolve \
  -H "Content-Type: application/json" \
  -d '{"provider":"alldebrid","api_key":"YOUR_KEY","magnet":"magnet:?xt=urn:btih:..."}'
```
Full interactive docs at `http://localhost:8000/docs` (FastAPI's built-in
Swagger UI).
Local development (without Docker)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

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
│   ├── public_scraper.py     Built-in scrapers for TPB, 1337x, YTS, Nyaa
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
This project is infrastructure: it searches public torrent sites and
interfaces with debrid services you already have accounts with. What you
do with it, and whether that's lawful in your jurisdiction, is your
responsibility. No content is hosted or distributed by this codebase itself.
