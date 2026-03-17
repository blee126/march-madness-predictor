# March Madness AI Bracket

Fullstack AI application for predicting March Madness: build your bracket, fill it with AI, and export (JSON or print/PDF). Runs on **web and mobile** (responsive + PWA).

## Stack

- **Frontend**: Next.js 14 (React), Tailwind CSS, responsive layout, PWA manifest for “Add to Home Screen”
- **Backend**: FastAPI (Python), scikit-learn classifier
- **Model**: Team1 features + Team2 features + round → P(Team1 wins). Train with your own CSVs or use seed data.

**Deploying and payments:** For production deployment to a domain and adding secure payments (Stripe), see **[DEPLOY_AND_PAYMENTS.md](DEPLOY_AND_PAYMENTS.md)**.

## Quick start

### 1. Install dependencies

```bash
npm run install:all
cd backend && pip install -r requirements.txt
```

### 2. Train the model (generates seed teams + bracket template)

```bash
cd backend
python train_model.py
```

This creates `backend/data/teams.json`, `backend/data/bracket_2026.json`, and `backend/model.pkl`. Each region (East, Midwest, South, West) gets different schools. To regenerate with fresh region-specific teams, run:

```bash
python train_model.py --refresh
```

### 3. Run the app

**Option A – both servers**

```bash
# From repo root
npm run dev
```

Runs frontend at [http://localhost:3000](http://localhost:3000) and backend at [http://localhost:8000](http://localhost:8000). Next.js rewrites `/api/*` to the backend.

**Option B – separate terminals**

```bash
# Terminal 1 – backend
cd backend && uvicorn main:app --reload

# Terminal 2 – frontend
cd frontend && npm run dev
```

### 4. Use the app

- Open [http://localhost:3000](http://localhost:3000).
- Click **Build my bracket**.
- Use **Full bracket** (default) to see the entire bracket with zoom and pan; or **By region** for a list view.
- Adjust **Preferences** (seed weight, offense weight) if desired, then click **Fill with AI**.
- Export with **Export JSON** or **Print / Save as PDF**. Your **Bracket ID** is saved in the browser for reference.

## Data and model

- **Seed data**: `train_model.py` generates 64 placeholder teams (4 regions × 16 seeds) with KenPom-style stats so the app runs without external files.
- **Real data for this year’s bracket**: To predict the current tournament you need (1) bracket structure (`gamedata/{year}.json`) and (2) team stats (e.g. offensive efficiency, AdjEM, tempo, four factors). **See [backend/DATA_SOURCES.md](backend/DATA_SOURCES.md)** for where to get them (KenPom, Bart Torvik, etc.) and the exact CSV/file format the app expects.
- **Other sources**: [Kaggle – March Madness](https://www.kaggle.com/datasets/nishaanamin/march-madness-data), [danvk/march-madness-data](https://github.com/danvk/march-madness-data), [KenPom](https://kenpom.com/blog/stats-explained/) (AdjEM, AdjO, AdjD, tempo).

**Feature set** (see `backend/model.py` and `backend/train_model.py`): seed, adj_em, adj_o, adj_d, efg_pct, to_pct, orb_pct, ftr, opp_* stats, tempo, round (64/32/16/8/4/2). You can add coach experience, conference, etc. by extending the feature list and training table.

**Training table**: Build rows = (Team1 features, Team2 features as *diff*, round) and target = 1 if Team1 wins. Use historical game results from the JSON/CSV sources above; `train_model.py` currently uses synthetic data for a working demo.

## API

- `GET /health` – health check
- `GET /teams` – list teams and features
- `GET /bracket` – bracket template (2026)
- `POST /predict` – body: `{ "team1_id", "team2_id", "round_of", "preferences?" }` → win probability
- `POST /fill-bracket` – body: `{ "preferences?" }` → full predicted bracket (predictions, region winners, champion)

## Mobile

- Layout is responsive; bracket uses region tabs and list-style games for small screens.
- Add to home screen: use the PWA manifest at `/manifest.json` for an app-like experience.

## Export

- **Export JSON**: Downloads a file with bracket template, all predictions, region winners, and champion.
- **Print / Save as PDF**: Opens a print-friendly page; use “Save as PDF” in the print dialog to export as PDF.

## Implemented next steps

- **User preferences**: Sliders for seed weight and offense weight; passed to the API and used to blend model probability with seed/offense advantage.
- **Bracket ID**: Generated on fill and stored in localStorage so you can reference your prediction.
- **Bracket scoring**: "How bracket scoring works" explains standard NCAA points; "Score your bracket" lets you paste actual results (JSON) and get your total and per-round score.
- **Odds placeholder**: Game slots show an "Odds: —" line ready for betting odds when you add a data source.

## Implemented (additional)

- **Score your bracket**: After the tournament, paste actual results or load a JSON file (array of `{ round_of, team1, team2, winner }`) and get your total score and per-round breakdown (1-2-4-8-16-32 pts). API: `POST /score-bracket`.
- **Rate limit**: "Fill with AI" is limited to once per 2 minutes (per browser). "Clear cooldown" link appears during the wait.

## Optional: Ollama LLM (local, free)

The app can call a local LLM via [Ollama](https://ollama.com/) for chat or bracket commentary—no API keys or cost.

### 1. Install Ollama

- **Windows / macOS / Linux**: Download from [https://ollama.com](https://ollama.com) and install.
- Or with winget (Windows): `winget install Ollama.Ollama`

### 2. Start Ollama and pull a model

In a terminal:

```bash
# Start the server (often starts automatically after install)
ollama serve

# Pull a model (pick one; smaller = faster, less RAM)
ollama pull llama3.2          # ~2GB, good default
ollama pull llama3.2:1b       # ~1.3GB, lighter
ollama pull mistral            # ~4GB
ollama pull phi3              # ~2.3GB
```

### 3. Configure the backend

Optional env vars (defaults work if Ollama runs on the same machine):

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API base URL |
| `OLLAMA_MODEL` | `llama3.2` | Model name (must match `ollama pull <name>`) |

Example (PowerShell):

```powershell
$env:OLLAMA_BASE_URL = "http://localhost:11434"
$env:OLLAMA_MODEL = "llama3.2"
cd backend; uvicorn main:app --reload
```

Example (bash):

```bash
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_MODEL=llama3.2
cd backend && uvicorn main:app --reload
```

### 4. Use the LLM API

- **Check status**: `GET /llm/status` — returns `enabled`, `reachable`, `base_url`, `model`.
- **Chat**: `POST /llm/chat` with body `{ "messages": [ { "role": "user", "content": "Why did you pick Duke?" } ] }` → returns `{ "ok": true, "reply": "..." }`.

The frontend can call these when you add an “Ask AI” or “Explain picks” feature. If Ollama isn’t running or isn’t configured, the rest of the app (bracket, Fill with AI, scoring) still works.

---

## Possible next steps (from your notes)

- Ingest real CSVs/JSON (Kaggle, danvk, etc.) into a training table and retrain.
- LLM pipeline: scrape articles/Reddit, parameterized prompts → extracted features → add to training or weighting.
- Betting odds: wire a real odds API and display in the bracket.

## License

MIT.
