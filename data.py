import os
import pandas as pd
import yfinance as yf
from datetime import date, datetime

from config import CRYPTOS, TICKERS, GLOBAL_START, CACHE_FILE, get_global_end


def is_cache_stale(path: str) -> bool:
    if not os.path.exists(path):
        return True
    mtime = datetime.fromtimestamp(os.path.getmtime(path)).date()
    return mtime < date.today()


def fetch_from_yfinance() -> pd.DataFrame:
    end = get_global_end()
    # threads=False avoids SQLite "database is locked" in yfinance's tz cache
    df = yf.download(
        tickers=TICKERS,
        start=GLOBAL_START,
        end=end,
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    # Retry any tickers that came back empty due to transient errors
    if not df.empty:
        downloaded = df.columns.get_level_values(1).unique().tolist()
        missing = [t for t in TICKERS if t not in downloaded]
        for ticker in missing:
            try:
                single = yf.download(
                    tickers=ticker,
                    start=GLOBAL_START,
                    end=end,
                    auto_adjust=True,
                    progress=False,
                )
                if not single.empty:
                    single.columns = pd.MultiIndex.from_tuples(
                        [(col, ticker) for col in single.columns]
                    )
                    df = pd.concat([df, single], axis=1)
            except Exception:
                pass
    return df


def save_cache(df: pd.DataFrame, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    flat = df.copy()
    flat.columns = ["_".join(col).strip() for col in flat.columns.values]
    flat.to_parquet(path)


def load_cache(path: str) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df.columns = pd.MultiIndex.from_tuples(
        [tuple(c.split("_", 1)) for c in df.columns]
    )
    return df


def load_or_fetch_data(force: bool = False) -> pd.DataFrame:
    if not force and not is_cache_stale(CACHE_FILE):
        return load_cache(CACHE_FILE)
    df = fetch_from_yfinance()
    save_cache(df.copy(), CACHE_FILE)
    return df


def _get_field_series(df: pd.DataFrame, field: str, tickers: list, start: str, end: str) -> pd.DataFrame:
    """Extract a single field (e.g. 'Close') for selected tickers within date range."""
    available_fields = df.columns.get_level_values(0).unique().tolist()
    # yfinance with auto_adjust=True may return 'Price' instead of 'Close' in some versions
    resolved_field = field
    if field not in available_fields:
        if field == "Close" and "Price" in available_fields:
            resolved_field = "Price"
        else:
            return pd.DataFrame()

    result = {}
    for ticker in tickers:
        coin_start = CRYPTOS[ticker]["start"]
        effective_start = max(start, coin_start)
        try:
            if (resolved_field, ticker) in df.columns:
                series = df[resolved_field][ticker]
            else:
                continue
            series = series.loc[effective_start:end]
            if not series.dropna().empty:
                result[ticker] = series
        except (KeyError, TypeError):
            continue
    if not result:
        return pd.DataFrame()
    out = pd.DataFrame(result)
    out.index = pd.to_datetime(out.index)
    return out


def get_price_series(df: pd.DataFrame, tickers: list, start: str, end: str) -> pd.DataFrame:
    return _get_field_series(df, "Close", tickers, start, end)


def get_volume_series(df: pd.DataFrame, tickers: list, start: str, end: str) -> pd.DataFrame:
    return _get_field_series(df, "Volume", tickers, start, end)


def resample_ohlcv(price_s: pd.Series, volume_s: pd.Series, freq: str):
    """Resample daily price and volume to the given frequency."""
    if freq == "D":
        return price_s, volume_s
    price_r  = price_s.resample(freq).last().dropna()
    volume_r = volume_s.resample(freq).sum()
    volume_r = volume_r.reindex(price_r.index)
    return price_r, volume_r


def get_moving_averages(price_s: pd.Series, windows: dict) -> dict:
    """Return {label: SMA series} for each window."""
    return {label: price_s.rolling(w).mean() for label, w in windows.items()}


def get_bollinger_bands(price_s: pd.Series, window: int, num_std: float) -> dict:
    middle = price_s.rolling(window).mean()
    std    = price_s.rolling(window).std()
    return {
        "upper":  middle + num_std * std,
        "middle": middle,
        "lower":  middle - num_std * std,
    }


def get_rsi(price_s: pd.Series, period: int) -> pd.Series:
    delta = price_s.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss.replace(0, float("nan"))
    return 100 - 100 / (1 + rs)


def get_returns(price_s: pd.Series, return_type: str) -> pd.Series:
    if return_type == "Diário":
        return price_s.pct_change() * 100
    elif return_type == "Semanal":
        return price_s.resample("W").last().pct_change() * 100
    elif return_type == "Mensal":
        return price_s.resample("ME").last().pct_change() * 100
    else:  # Acumulado
        first = price_s.dropna().iloc[0] if not price_s.dropna().empty else 1
        return (price_s / first - 1) * 100


def get_stats(price_s: pd.Series, volume_s: pd.Series) -> dict:
    p = price_s.dropna()
    v = volume_s.dropna()
    if p.empty:
        return {}
    daily_ret = p.pct_change().dropna()
    vol_ann   = daily_ret.std() * (252 ** 0.5) * 100 if len(daily_ret) > 1 else 0
    drawdown  = (p.iloc[-1] / p.max() - 1) * 100 if p.max() != 0 else 0
    return {
        "price":      p.iloc[-1],
        "return_pct": (p.iloc[-1] / p.iloc[0] - 1) * 100 if p.iloc[0] != 0 else 0,
        "max":        p.max(),
        "min":        p.min(),
        "avg_volume": v.mean() if not v.empty else 0,
        "volatility": vol_ann,
        "drawdown":   drawdown,
    }


def get_normalized_series(df: pd.DataFrame, tickers: list, start: str, end: str) -> pd.DataFrame:
    price_df = get_price_series(df, tickers, start, end)
    if price_df.empty:
        return pd.DataFrame()
    result = pd.DataFrame(index=price_df.index)
    for col in price_df.columns:
        series = price_df[col].dropna()
        if series.empty:
            continue
        base = series.iloc[0]
        if base != 0:
            result[col] = (price_df[col] / base) * 100
    return result


def df_to_json(df: pd.DataFrame) -> str:
    return df.to_json(orient="split", date_format="iso")


def df_from_json(json_str: str) -> pd.DataFrame:
    df = pd.read_json(json_str, orient="split")
    df.columns = pd.MultiIndex.from_tuples(
        [tuple(c.split("_", 1)) for c in df.columns]
    )
    df.index = pd.to_datetime(df.index)
    return df


def serialize_for_store(df: pd.DataFrame) -> str:
    flat = df.copy()
    flat.columns = ["_".join(col).strip() for col in flat.columns.values]
    return flat.to_json(orient="split", date_format="iso")


def deserialize_from_store(json_str: str) -> pd.DataFrame:
    flat = pd.read_json(json_str, orient="split")
    flat.columns = pd.MultiIndex.from_tuples(
        [tuple(c.split("_", 1)) for c in flat.columns]
    )
    flat.index = pd.to_datetime(flat.index)
    return flat
