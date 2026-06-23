# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

Single-page Bitcoin technical analysis dashboard built with Plotly Dash.

## Running locally

```bash
pip install -r requirements.txt
python app.py
# Opens at http://127.0.0.1:8050
```

On first run (or when the cache is stale), `app.py` fetches data from Yahoo Finance via `yfinance` and writes it to `cache/crypto_data.parquet`. Subsequent starts load from cache unless the file's mtime is from a previous day or the user clicks "Atualizar dados".

## Architecture

Three modules, no framework beyond Dash:

| File | Role |
|------|------|
| `config.py` | All constants and tunables: tickers, colors, indicator params, granularities, quick-period shortcuts |
| `data.py` | Data layer — cache management, yfinance download, OHLCV resampling, all indicator math (MA, Bollinger, RSI, returns, stats) |
| `app.py` | Dash layout + two callbacks |

### Data flow

`app.py` holds a module-level `_DATA` dict containing the raw multi-level-column DataFrame (loaded once at startup). Callbacks read from `_DATA["df"]` directly — there is intentionally no `dcc.Store` round-trip for the main dataset to avoid large JSON serialization.

### Callback structure

**Callback 1** (`handle_controls`) — handles quick-period buttons and the refresh button. Updates `DatePickerRange` dates and/or triggers a forced re-fetch by incrementing a counter in `dcc.Store(id="refresh-store")`.

**Callback 2** (`update_all`) — driven by date range, granularity, indicator checkboxes, return type, and the refresh-store counter. Produces all four outputs: price chart, volume chart, return chart, and stat cards.

### Cache / MultiIndex convention

The parquet cache flattens the yfinance MultiIndex columns (`(field, ticker)`) into `"field_ticker"` strings on write and reconstructs the MultiIndex on load. Any function touching the raw DataFrame must account for yfinance occasionally returning `"Price"` instead of `"Close"` (handled in `_get_field_series`).

### Styling

`assets/custom.css` is auto-loaded by Dash. All chart theming uses `plotly_dark` with transparent backgrounds; color palette is defined via constants in `config.py` (`BTC_COLOR`, `MA_COLORS`).

## GitHub repository

`https://github.com/Rayonil/crypto-dashboard` — public repo, branch `master`.

After any change to the project, commit and push:

```powershell
git add <changed files>
git commit -m "description of change"
git push
```

If `git` is not found in a fresh PowerShell session inside Claude Code, reload the PATH first:

```powershell
$env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH","User")
```

## Deploy — Render

The app is deployed on **Render** (render.com) as a Python web service.

- Start command: `gunicorn app:server`
- `app.server` is the Flask instance exposed at the bottom of `app.py`
- `render.yaml` at the repo root defines the service (name `crypto-dashboard`, Python env, build and start commands)
- `cache/` is excluded from git (`.gitignore`); on Render the app fetches fresh data from yfinance on first boot

### Connecting to Render (first time)

1. Go to render.com → New → Web Service
2. Connect the GitHub repo `Rayonil/crypto-dashboard`
3. Render will auto-detect `render.yaml` and configure the service
4. Click **Deploy** — the live URL will appear in the Render dashboard

### Updating the deploy

Every `git push` to `master` triggers an automatic redeploy on Render (if auto-deploy is enabled in the Render dashboard).
