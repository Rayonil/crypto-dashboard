from datetime import date, timedelta

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, callback_context, dcc, html
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config import (
    BTC_TICKER, BTC_COLOR, GLOBAL_START, QUICK_PERIODS,
    MA_WINDOWS, MA_COLORS, BOLLINGER_WINDOW, BOLLINGER_STD, RSI_PERIOD,
    GRANULARITIES, RETURN_TYPES, get_global_end,
)
from data import (
    load_or_fetch_data,
    get_price_series,
    get_volume_series,
    resample_ohlcv,
    get_moving_averages,
    get_bollinger_bands,
    get_rsi,
    get_returns,
    get_stats,
)

# ---------------------------------------------------------------------------
# Module-level data store — avoids large JSON serialization through dcc.Store
# ---------------------------------------------------------------------------
print("Carregando dados Bitcoin...")
_DATA: dict = {"df": load_or_fetch_data(), "updated": date.today().strftime("%d/%m/%Y")}
print("Pronto.")

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY],
    title="Bitcoin Dashboard",
    suppress_callback_exceptions=True,
)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
_QUICK_LABELS = list(QUICK_PERIODS.keys())
_QUICK_IDS    = [f"btn-{l.lower().replace(' ', '-')}" for l in _QUICK_LABELS]

sidebar = html.Div(
    id="sidebar",
    children=[
        html.Div([
            html.Span("₿", className="btc-icon"),
            html.Span(" Bitcoin Dashboard", className="btc-title-text"),
        ], className="btc-title"),
        html.P("Análise técnica histórica", className="dashboard-subtitle"),

        html.Div("Período", className="sidebar-section-label"),
        dcc.DatePickerRange(
            id="date-picker",
            min_date_allowed=GLOBAL_START,
            max_date_allowed=get_global_end(),
            start_date=GLOBAL_START,
            end_date=get_global_end(),
            display_format="DD/MM/YYYY",
            start_date_placeholder_text="Início",
            end_date_placeholder_text="Fim",
            style={"width": "100%", "marginBottom": "8px"},
        ),
        html.Div(
            [dbc.Button(l, id=bid, color="secondary", outline=True, size="sm", className="period-btn")
             for l, bid in zip(_QUICK_LABELS, _QUICK_IDS)],
            style={"display": "flex", "flexWrap": "wrap", "gap": "4px", "marginBottom": "4px"},
        ),

        html.Div("Granularidade", className="sidebar-section-label"),
        dbc.RadioItems(
            id="granularity-radio",
            options=[{"label": k, "value": v} for k, v in GRANULARITIES.items()],
            value="D",
            inline=False,
            inputStyle={"marginRight": "6px"},
            labelStyle={"display": "block", "marginBottom": "4px", "fontSize": "0.88rem"},
        ),

        html.Div("Indicadores técnicos", className="sidebar-section-label"),
        dbc.Checklist(
            id="indicators-checklist",
            options=[
                {"label": "MA 20",           "value": "MA 20"},
                {"label": "MA 50",           "value": "MA 50"},
                {"label": "MA 200",          "value": "MA 200"},
                {"label": "Bollinger Bands", "value": "Bollinger"},
                {"label": "RSI (14)",        "value": "RSI"},
            ],
            value=[],
            inputStyle={"marginRight": "6px"},
            labelStyle={"display": "block", "marginBottom": "5px", "fontSize": "0.88rem"},
        ),

        html.Div("Tipo de retorno", className="sidebar-section-label"),
        dbc.RadioItems(
            id="return-type-radio",
            options=[{"label": r, "value": r} for r in RETURN_TYPES],
            value="Diário",
            inline=False,
            inputStyle={"marginRight": "6px"},
            labelStyle={"display": "block", "marginBottom": "4px", "fontSize": "0.88rem"},
        ),

        html.Hr(style={"borderColor": "#3a3a55", "margin": "16px 0 10px"}),
        html.P(id="last-update-label", className="last-update-label",
               children=f"Última atualização: {_DATA['updated']}"),
        dbc.Button("Atualizar dados", id="refresh-btn", color="warning",
                   outline=True, size="sm", className="w-100 mt-1"),
    ],
)

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
app.layout = dbc.Container(
    fluid=True,
    children=[
        # Refresh signal store — only carries a counter, not the full DataFrame
        dcc.Store(id="refresh-store", data=0),
        dbc.Row([
            dbc.Col(sidebar, width=3, style={"padding": "0"}),
            dbc.Col(
                id="main-panel",
                width=9,
                children=[
                    html.Div(id="stats-row", className="stats-row"),
                    html.Div(dcc.Graph(id="price-chart",  config={"displayModeBar": True,  "scrollZoom": True}), className="graph-card"),
                    html.Div(dcc.Graph(id="volume-chart", config={"displayModeBar": False}), className="graph-card"),
                    html.Div(dcc.Graph(id="return-chart", config={"displayModeBar": False}), className="graph-card"),
                ],
                style={"padding": "0"},
            ),
        ], style={"margin": "0"}),
    ],
    style={"padding": "0"},
)

# ---------------------------------------------------------------------------
# Shared layout defaults
# ---------------------------------------------------------------------------
_BASE = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#b0b0cc", size=12),
    hovermode="x unified",
)
_GRID = dict(showgrid=True, gridcolor="#2e2e4a", gridwidth=1)


def _empty_fig(title: str, height: int) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        **_BASE, title=title, height=height,
        margin=dict(l=60, r=20, t=40, b=40),
        annotations=[dict(text="Sem dados para o período selecionado",
                          xref="paper", yref="paper", x=0.5, y=0.5,
                          showarrow=False, font=dict(size=13, color="#6666aa"))],
    )
    return fig


# ---------------------------------------------------------------------------
# Callback 1 — Quick period buttons + Refresh → DatePicker + refresh signal
# ---------------------------------------------------------------------------
@app.callback(
    Output("date-picker",     "start_date"),
    Output("date-picker",     "end_date"),
    Output("refresh-store",   "data"),
    Output("last-update-label", "children"),
    [Input(bid, "n_clicks") for bid in _QUICK_IDS] + [Input("refresh-btn", "n_clicks")],
    prevent_initial_call=True,
)
def handle_controls(*_args):
    ctx   = callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate
    tid   = ctx.triggered[0]["prop_id"].split(".")[0]
    today = date.today()

    if tid == "refresh-btn":
        _DATA["df"]      = load_or_fetch_data(force=True)
        _DATA["updated"] = today.strftime("%d/%m/%Y %H:%M")
        return (dash.no_update, dash.no_update,
                (_DATA.get("_counter", 0) or 0) + 1,
                f"Última atualização: {_DATA['updated']}")

    for label, bid in zip(_QUICK_LABELS, _QUICK_IDS):
        if tid == bid:
            days  = QUICK_PERIODS[label]
            start = GLOBAL_START if days is None else (today - timedelta(days=days)).strftime("%Y-%m-%d")
            return start, today.strftime("%Y-%m-%d"), dash.no_update, dash.no_update

    raise dash.exceptions.PreventUpdate


# ---------------------------------------------------------------------------
# Callback 2 — Filters → Charts + Stats
# ---------------------------------------------------------------------------
@app.callback(
    Output("price-chart",  "figure"),
    Output("volume-chart", "figure"),
    Output("return-chart", "figure"),
    Output("stats-row",    "children"),
    Input("refresh-store",        "data"),
    Input("date-picker",          "start_date"),
    Input("date-picker",          "end_date"),
    Input("granularity-radio",    "value"),
    Input("indicators-checklist", "value"),
    Input("return-type-radio",    "value"),
)
def update_all(_refresh, start_date, end_date, granularity, indicators, return_type):
    indicators  = indicators or []
    granularity = granularity or "D"
    return_type = return_type or "Diário"
    start = (start_date or GLOBAL_START)[:10]
    end   = (end_date   or get_global_end())[:10]

    df = _DATA["df"]
    price_df  = get_price_series(df, [BTC_TICKER], start, end)
    volume_df = get_volume_series(df, [BTC_TICKER], start, end)

    if price_df.empty or BTC_TICKER not in price_df.columns:
        emp = _empty_fig("Preço Bitcoin (USD)", 500)
        return emp, _empty_fig("Volume", 200), _empty_fig("Retorno", 280), []

    price_raw  = price_df[BTC_TICKER].dropna()
    volume_raw = (volume_df[BTC_TICKER].dropna()
                  if not volume_df.empty and BTC_TICKER in volume_df.columns
                  else price_raw * 0)

    price_s, volume_s = resample_ohlcv(price_raw, volume_raw, granularity)

    # ── Stats ──────────────────────────────────────────────────────────────
    stats = get_stats(price_s, volume_s)

    def _fmt_price(v): return f"${float(v):,.2f}"
    def _fmt_vol(v):
        v = float(v)
        if v >= 1e9:  return f"${v/1e9:.2f}B"
        if v >= 1e6:  return f"${v/1e6:.2f}M"
        return f"${v:,.0f}"
    def _pct_cls(v): return "stat-positive" if float(v) > 0 else ("stat-negative" if float(v) < 0 else "stat-neutral")

    def _card(label, val_str, cls="stat-neutral"):
        return html.Div([
            html.Div(label, className="stat-label"),
            html.Div(val_str, className=f"stat-value {cls}"),
        ], className="stats-card")

    ret_pct  = float(stats.get("return_pct", 0))
    drawdown = float(stats.get("drawdown", 0))

    stat_cards = [
        _card("Preço atual",        _fmt_price(stats.get("price", 0))),
        _card("Retorno no período", f"{ret_pct:+.2f}%",  _pct_cls(ret_pct)),
        _card("Máxima",             _fmt_price(stats.get("max",  0))),
        _card("Mínima",             _fmt_price(stats.get("min",  0))),
        _card("Vol. médio",         _fmt_vol(stats.get("avg_volume", 0))),
        _card("Volatilidade",       f"{float(stats.get('volatility', 0)):.1f}% a.a."),
        _card("Drawdown",           f"{drawdown:.2f}%", _pct_cls(drawdown)),
    ]

    # ── Price chart ────────────────────────────────────────────────────────
    show_rsi = "RSI" in indicators
    if show_rsi:
        fig_price = make_subplots(
            rows=2, cols=1, shared_xaxes=True,
            row_heights=[0.70, 0.30], vertical_spacing=0.04,
        )
    else:
        fig_price = go.Figure()

    def _add(trace, row=1):
        if show_rsi:
            fig_price.add_trace(trace, row=row, col=1)
        else:
            fig_price.add_trace(trace)

    # Bollinger Bands (drawn first — behind price line)
    if "Bollinger" in indicators:
        bb = get_bollinger_bands(price_s, BOLLINGER_WINDOW, BOLLINGER_STD)
        _add(go.Scatter(x=list(bb["upper"].index), y=list(bb["upper"].values),
            name="BB Superior", line=dict(color="rgba(140,140,220,0.5)", width=1, dash="dot"),
            hoverinfo="skip", showlegend=False))
        _add(go.Scatter(x=list(bb["lower"].index), y=list(bb["lower"].values),
            name="BB Inferior", line=dict(color="rgba(140,140,220,0.5)", width=1, dash="dot"),
            fill="tonexty", fillcolor="rgba(100,100,200,0.07)",
            hoverinfo="skip", showlegend=False))
        _add(go.Scatter(x=list(bb["middle"].index), y=list(bb["middle"].values),
            name="BB Média", line=dict(color="rgba(140,140,220,0.7)", width=1),
            hoverinfo="skip", showlegend=False))

    # BTC price line
    _add(go.Scatter(
        x=list(price_s.index), y=list(price_s.values),
        name="BTC/USD",
        line=dict(color=BTC_COLOR, width=2),
        hovertemplate="%{x|%d %b %Y}<br><b>$%{y:,.2f}</b><extra>BTC</extra>",
    ))

    # Moving averages
    active_mas = {k: v for k, v in MA_WINDOWS.items() if k in indicators}
    if active_mas:
        mas = get_moving_averages(price_s, active_mas)
        for lbl, series in mas.items():
            s = series.dropna()
            if not s.empty:
                _add(go.Scatter(
                    x=list(s.index), y=list(s.values),
                    name=lbl, line=dict(color=MA_COLORS[lbl], width=1.5),
                    hovertemplate=f"%{{x|%d %b %Y}}<br><b>${{y:,.2f}}</b><extra>{lbl}</extra>",
                ))

    # RSI subplot
    if show_rsi:
        rsi_s = get_rsi(price_raw, RSI_PERIOD).dropna()
        fig_price.add_hrect(y0=0,  y1=30,  fillcolor="rgba(0,200,100,0.07)", line_width=0, row=2, col=1)
        fig_price.add_hrect(y0=70, y1=100, fillcolor="rgba(255,80,80,0.07)",  line_width=0, row=2, col=1)
        fig_price.add_hline(y=70, line_dash="dash", line_color="#ff5566", line_width=1, row=2, col=1)
        fig_price.add_hline(y=30, line_dash="dash", line_color="#44dd88", line_width=1, row=2, col=1)
        fig_price.add_trace(go.Scatter(
            x=list(rsi_s.index), y=list(rsi_s.values),
            name="RSI (14)", line=dict(color="#ddddff", width=1.5),
            hovertemplate="%{x|%d %b %Y}<br><b>RSI: %{y:.1f}</b><extra></extra>",
        ), row=2, col=1)
        fig_price.update_yaxes(range=[0, 100], title_text="RSI", row=2, col=1, **_GRID)

    price_layout = dict(
        **_BASE,
        title="Preço Bitcoin (USD)",
        height=650 if show_rsi else 500,
        margin=dict(l=60, r=20, t=44, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    if show_rsi:
        fig_price.update_layout(**price_layout)
        fig_price.update_xaxes(**_GRID)
        fig_price.update_yaxes(title_text="Preço (USD)", row=1, col=1, **_GRID)
    else:
        fig_price.update_layout(
            **price_layout,
            xaxis=dict(rangeslider=dict(visible=True, thickness=0.05), **_GRID),
            yaxis=dict(title="Preço (USD)", **_GRID),
        )

    # ── Volume chart ───────────────────────────────────────────────────────
    fig_vol = go.Figure([go.Bar(
        x=list(volume_s.index), y=list(volume_s.values),
        name="Volume", marker_color=BTC_COLOR, opacity=0.65,
        hovertemplate="%{x|%d %b %Y}<br><b>%{y:,.0f}</b><extra>Volume</extra>",
    )])
    fig_vol.update_layout(
        **_BASE, title="Volume negociado (USD)", height=200, showlegend=False,
        margin=dict(l=60, r=20, t=36, b=30),
        xaxis=dict(**_GRID), yaxis=dict(title="Volume (USD)", **_GRID),
    )

    # ── Return chart ───────────────────────────────────────────────────────
    returns_s = get_returns(price_raw, return_type).dropna()
    fig_ret   = go.Figure()
    if returns_s.empty:
        fig_ret = _empty_fig(f"Retorno {return_type}", 280)
    elif return_type == "Acumulado":
        last_val = float(returns_s.iloc[-1])
        lc = "#44dd88" if last_val >= 0 else "#ff5566"
        fc = "rgba(0,200,100,0.12)" if last_val >= 0 else "rgba(255,80,80,0.12)"
        fig_ret.add_trace(go.Scatter(
            x=list(returns_s.index), y=list(returns_s.values),
            name="Retorno acumulado", line=dict(color=lc, width=2),
            fill="tozeroy", fillcolor=fc,
            hovertemplate="%{x|%d %b %Y}<br><b>%{y:+.2f}%</b><extra></extra>",
        ))
        fig_ret.add_hline(y=0, line_color="#555577", line_width=1)
        fig_ret.update_layout(
            **_BASE, title="Retorno Acumulado (%)", height=280, showlegend=False,
            margin=dict(l=60, r=20, t=36, b=30),
            xaxis=dict(**_GRID), yaxis=dict(title="Retorno (%)", **_GRID),
        )
    else:
        colors = ["#44dd88" if float(v) >= 0 else "#ff5566" for v in returns_s.values]
        fig_ret.add_trace(go.Bar(
            x=list(returns_s.index), y=list(returns_s.values),
            name=f"Retorno {return_type}", marker_color=colors,
            hovertemplate="%{x|%d %b %Y}<br><b>%{y:+.2f}%</b><extra></extra>",
        ))
        fig_ret.add_hline(y=0, line_color="#555577", line_width=1)
        fig_ret.update_layout(
            **_BASE, title=f"Retorno {return_type} (%)", height=280, showlegend=False,
            margin=dict(l=60, r=20, t=36, b=30),
            xaxis=dict(**_GRID), yaxis=dict(title="Retorno (%)", **_GRID),
        )

    return fig_price, fig_vol, fig_ret, stat_cards


server = app.server  # exposed for gunicorn: gunicorn app:server

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8050))
    app.run(debug=False, host="0.0.0.0", port=port)
