# Πυξίδα ΑΕΙ — Deploy guide

Three pieces, because GitHub Pages serves **static files only** (it cannot run
the Python backend):

| Piece | Where | Cost | Notes |
|---|---|---|---|
| HTML forecast (`docs/index.html`) | GitHub Pages | free | always-on, no cold start |
| FastAPI backend (`api/`) | Render free | free | sleeps after 15 min idle |
| React app (`web/`) | Render static or Pages | free | points at the backend URL |

---

## 0. One-time: push this folder as its own repo

This `pyxida/` folder currently lives inside the parent `BPAN` git repo. The new
`pyxida.git` repo needs its **own** git root here. Run from `pyxida/`:

```bash
cd ~/Dropbox/BPAN/pyxida

# make pyxida/ its own repo (independent of the parent BPAN repo)
git init
git branch -M main
git remote add origin https://github.com/StergiosCha/pyxida.git

git add -A
git commit -m "Πυξίδα ΑΕΙ: app + 2026 forecast + deploy config"
git push -u origin main
```

If git complains the folder is already tracked by the parent repo, that's fine —
a nested `git init` creates an independent repo; the parent simply ignores it.
(`.gitignore` already excludes `.venv-pyxida/`, `web/node_modules/`, and the
168 MB `data/raw/` — only the 8.8 MB DuckDB is committed.)

---

## 1. HTML forecast → GitHub Pages (live, always-on)

In the repo on GitHub: **Settings → Pages → Build and deployment**
- Source: **GitHub Actions** (the included `.github/workflows/pages.yml` does the rest)

On the next push it publishes `docs/` and the forecast goes live at:

    https://stergioscha.github.io/pyxida/

(Alternatively, Source = "Deploy from a branch" → `main` / `docs` folder — same result without Actions.)

---

## 2. FastAPI backend → Render free

1. render.com → **New → Blueprint** → connect the `pyxida` repo.
   Render reads `render.yaml` automatically (Frankfurt region, free plan,
   `uvicorn api.main:app`). Build installs only `requirements-api.txt`
   (matplotlib dropped — runtime ~150-250 MB, well under the 512 MB limit).
2. First deploy takes ~2-3 min. You get a URL like `https://pyxida-api.onrender.com`.
3. Free tier sleeps after 15 min idle; first request after that cold-starts in ~30-50 s.

**LLM advisor:** left OFF server-side. Visitors add their own key in the app UI
(stored in their browser only). To use a server key instead, in the Render
dashboard set `PYXIDA_ENABLE_RAG=1`, `PYXIDA_LLM_BACKEND=openrouter`,
`OPENROUTER_API_KEY=<secret>`, and uncomment `openai` in `requirements-api.txt`.

---

## 3. React app → point it at the backend

The frontend reads `VITE_API_BASE` (defaults to `/api`). For production, build
with the Render URL:

```bash
cd web
echo "VITE_API_BASE=https://pyxida-api.onrender.com" > .env.production
npm run build      # outputs web/dist/
```

Deploy `web/dist/` as a Render **Static Site** (or push it to a `gh-pages`
branch). Done — the app is live and talks to the backend.

---

## The LLM key feature (what changed)

- Users paste their own OpenRouter/Anthropic/OpenAI key in the σύμβουλος and
  Σύγκριση panels. Stored in `localStorage` only — never sent anywhere except
  the LLM provider, never logged server-side, never committed.
- A user key **bypasses** the server RAG flag, so the advisor works on a hosted
  deployment with **zero server secrets**.
- No key → the advisor still works via the deterministic grounded template
  (the LLM only rephrases; it never invents βάσεις/ΕΒΕ).
