from datetime import date

# --- Bitcoin focus ---
BTC_TICKER = "BTC-USD"
BTC_COLOR  = "#F7931A"

# --- Technical indicators ---
MA_WINDOWS = {"MA 20": 20, "MA 50": 50, "MA 200": 200}
MA_COLORS  = {"MA 20": "#00d4ff", "MA 50": "#ffdd57", "MA 200": "#ff6b6b"}

BOLLINGER_WINDOW = 20
BOLLINGER_STD    = 2

RSI_PERIOD = 14

# --- UI options ---
GRANULARITIES = {"Diária": "D", "Semanal": "W", "Mensal": "ME"}
RETURN_TYPES  = ["Diário", "Semanal", "Mensal", "Acumulado"]

# --- Legacy multi-coin data (kept for cache compatibility) ---
CRYPTOS = {
    "BTC-USD": {
        "name": "Bitcoin",
        "symbol": "BTC",
        "color": "#F7931A",
        "start": "2017-01-01",
    },
    "ETH-USD": {
        "name": "Ethereum",
        "symbol": "ETH",
        "color": "#627EEA",
        "start": "2017-01-01",
    },
    "BNB-USD": {
        "name": "Binance Coin",
        "symbol": "BNB",
        "color": "#F3BA2F",
        "start": "2017-07-25",
    },
    "SOL-USD": {
        "name": "Solana",
        "symbol": "SOL",
        "color": "#9945FF",
        "start": "2020-03-20",
    },
    "USDT-USD": {
        "name": "Tether",
        "symbol": "USDT",
        "color": "#26A17B",
        "start": "2017-01-01",
    },
    "USDC-USD": {
        "name": "USD Coin",
        "symbol": "USDC",
        "color": "#2775CA",
        "start": "2018-09-26",
    },
    "PAXG-USD": {
        "name": "PAX Gold",
        "symbol": "PAXG",
        "color": "#C9A84C",
        "start": "2019-09-27",
    },
}

TICKERS = list(CRYPTOS.keys())

GLOBAL_START = "2017-01-01"

def get_global_end():
    return date.today().strftime("%Y-%m-%d")

CACHE_FILE = "cache/crypto_data.parquet"

QUICK_PERIODS = {
    "1M": 30,
    "3M": 90,
    "6M": 180,
    "1A": 365,
    "5A": 1825,
    "Desde 2017": None,
}
