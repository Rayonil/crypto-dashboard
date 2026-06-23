# Bitcoin Dashboard

An interactive Bitcoin technical analysis dashboard built with Plotly Dash. Visualize price history, trading volume, and key technical indicators through a clean dark-themed interface.

**Live demo:** [crypto-dashboard on Render](https://crypto-dashboard-rp3n.onrender.com)

---

## Features

- **Price chart** — historical BTC/USD price with range slider
- **Volume chart** — daily trading volume as a bar chart
- **Return chart** — daily, weekly, monthly, or cumulative returns
- **Stat cards** — current price, period return, max/min, average volume, annualized volatility, and drawdown
- **Technical indicators** — MA 20, MA 50, MA 200, Bollinger Bands (20, 2σ), RSI (14)
- **Granularity selector** — daily, weekly, or monthly aggregation
- **Quick period shortcuts** — 1M, 3M, 6M, 1Y, 5Y, since 2017
- **Data refresh** — on-demand re-fetch from Yahoo Finance

## Tech stack

| Layer | Library |
|-------|---------|
| Web framework | [Dash](https://dash.plotly.com/) + [Dash Bootstrap Components](https://dash-bootstrap-components.opensource.faculty.ai/) |
| Charts | [Plotly](https://plotly.com/python/) |
| Data source | [yfinance](https://github.com/ranaroussi/yfinance) |
| Data processing | [pandas](https://pandas.pydata.org/) |
| Cache format | [Apache Parquet](https://parquet.apache.org/) via pyarrow |
| Production server | [Gunicorn](https://gunicorn.org/) |
| Hosting | [Render](https://render.com/) |

## Getting started

### Prerequisites

- Python 3.9+
- pip

### Installation

```bash
git clone https://github.com/Rayonil/crypto-dashboard.git
cd crypto-dashboard
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:8050` in your browser.

On first run the app fetches historical data from Yahoo Finance (from 2017 to today) and caches it to `cache/crypto_data.parquet`. Subsequent starts load from cache; the cache is refreshed automatically if it is from a previous day, or manually via the **Atualizar dados** button.

## Project structure

```
crypto_dashboard/
├── app.py              # Dash app: layout and callbacks
├── config.py           # Constants: tickers, colors, indicator params
├── data.py             # Data layer: cache, yfinance download, indicator math
├── assets/
│   └── custom.css      # Dark theme overrides
├── render.yaml         # Render deployment config
├── requirements.txt
└── cache/              # Auto-generated, excluded from git
    └── crypto_data.parquet
```

## Deployment

The app is configured for one-click deployment on Render via `render.yaml`.

1. Fork or clone this repo to your GitHub account
2. Go to [render.com](https://render.com) → **New → Web Service**
3. Connect the repository — Render will detect `render.yaml` automatically
4. Click **Deploy**

Every push to `master` triggers an automatic redeploy.

> **Note:** The free tier on Render sleeps after 15 minutes of inactivity and takes ~30 seconds to wake on the next request.

## License

MIT
