"""
GEX + DEX Dashboard
Real-time options Gamma Exposure (GEX) and Delta Exposure (DEX) tracking
Supports all major indices, ETFs and single stocks via Tastytrade / dxFeed
"""
import streamlit as st
import json
import time
import math
from datetime import datetime, timedelta
from websocket import create_connection
import pandas as pd
import plotly.graph_objects as go
from utils.auth import ensure_streamer_token
from utils.gex_calculator import GEXCalculator, parse_option_symbol

st.set_page_config(page_title="GEX + DEX Dashboard", page_icon="\U0001f4ca", layout="wide")

PRESET_SYMBOLS = {
    "SPX":   {"option_prefix": "SPXW",  "default_price": 5800,  "increment": 5},
    "XSP":   {"option_prefix": "XSP",   "default_price": 580,   "increment": 1},
    "NDX":   {"option_prefix": "NDXP",  "default_price": 20000, "increment": 25},
    "RUT":   {"option_prefix": "RUTW",  "default_price": 2100,  "increment": 5},
    "DJX":   {"option_prefix": "DJX",   "default_price": 430,   "increment": 1},
    "VIX":   {"option_prefix": "VIX",   "default_price": 18,    "increment": 0.5},
    "SPY":   {"option_prefix": "SPY",   "default_price": 580,   "increment": 1},
    "QQQ":   {"option_prefix": "QQQ",   "default_price": 490,   "increment": 1},
    "IWM":   {"option_prefix": "IWM",   "default_price": 210,   "increment": 1},
    "DIA":   {"option_prefix": "DIA",   "default_price": 430,   "increment": 1},
    "GLD":   {"option_prefix": "GLD",   "default_price": 230,   "increment": 1},
    "SLV":   {"option_prefix": "SLV",   "default_price": 28,    "increment": 0.5},
    "TLT":   {"option_prefix": "TLT",   "default_price": 95,    "increment": 1},
    "HYG":   {"option_prefix": "HYG",   "default_price": 79,    "increment": 0.5},
    "XLE":   {"option_prefix": "XLE",   "default_price": 90,    "increment": 1},
    "XLF":   {"option_prefix": "XLF",   "default_price": 45,    "increment": 0.5},
    "XLK":   {"option_prefix": "XLK",   "default_price": 220,   "increment": 1},
    "XLU":   {"option_prefix": "XLU",   "default_price": 70,    "increment": 1},
    "XBI":   {"option_prefix": "XBI",   "default_price": 90,    "increment": 1},
    "EEM":   {"option_prefix": "EEM",   "default_price": 42,    "increment": 0.5},
    "EWZ":   {"option_prefix": "EWZ",   "default_price": 30,    "increment": 0.5},
    "FXI":   {"option_prefix": "FXI",   "default_price": 28,    "increment": 0.5},
    "USO":   {"option_prefix": "USO",   "default_price": 75,    "increment": 1},
    "UNG":   {"option_prefix": "UNG",   "default_price": 15,    "increment": 0.5},
    "AAPL":  {"option_prefix": "AAPL",  "default_price": 220,   "increment": 1},
    "MSFT":  {"option_prefix": "MSFT",  "default_price": 420,   "increment": 1},
    "NVDA":  {"option_prefix": "NVDA",  "default_price": 900,   "increment": 5},
    "TSLA":  {"option_prefix": "TSLA",  "default_price": 250,   "increment": 2},
    "AMZN":  {"option_prefix": "AMZN",  "default_price": 200,   "increment": 1},
    "GOOGL": {"option_prefix": "GOOGL", "default_price": 175,   "increment": 1},
    "META":  {"option_prefix": "META",  "default_price": 510,   "increment": 2},
    "AMD":   {"option_prefix": "AMD",   "default_price": 175,   "increment": 1},
    "COIN":  {"option_prefix": "COIN",  "default_price": 235,   "increment": 2},
    "MSTR":  {"option_prefix": "MSTR",  "default_price": 400,   "increment": 5},
    "PLTR":  {"option_prefix": "PLTR",  "default_price": 25,    "increment": 0.5},
    "UBER":  {"option_prefix": "UBER",  "default_price": 75,    "increment": 1},
    "NFLX":  {"option_prefix": "NFLX",  "default_price": 650,   "increment": 5},
    "BABA":  {"option_prefix": "BABA",  "default_price": 80,    "increment": 1},
    "BAC":   {"option_prefix": "BAC",   "default_price": 38,    "increment": 0.5},
    "JPM":   {"option_prefix": "JPM",   "default_price": 220,   "increment": 1},
    "XOM":   {"option_prefix": "XOM",   "default_price": 115,   "increment": 1},
    "GM":    {"option_prefix": "GM",    "default_price": 48,    "increment": 0.5},
    "F":     {"option_prefix": "F",     "default_price": 12,    "increment": 0.5},
    "SMH":   {"option_prefix": "SMH",   "default_price": 120,   "increment": 1},
    "HOOD":  {"option_prefix": "HOOD",  "default_price": 35,    "increment": 1},
    "NKE":   {"option_prefix": "NKE",   "default_price": 100,   "increment": 1},
    "INTC":  {"option_prefix": "INTC",  "default_price": 50,    "increment": 1},
    "ET":    {"option_prefix": "ET",    "default_price": 20,    "increment": 0.5},
    "NOK":   {"option_prefix": "NOK",   "default_price": 5,     "increment": 0.5},
    "IBIT":  {"option_prefix": "IBIT",  "default_price": 50,    "increment": 1},
    "ORCL":  {"option_prefix": "ORCL",  "default_price": 50,    "increment": 1},
    "IREN":  {"option_prefix": "IREN",  "default_price": 50,    "increment": 1},
    "SMCI":  {"option_prefix": "SMCI",  "default_price": 50,    "increment": 1},
    "SOFI":  {"option_prefix": "SOFI",  "default_price": 50,    "increment": 1},
    "SNAP":  {"option_prefix": "SNAP",  "default_price": 50,    "increment": 1},
    "SHOP":  {"option_prefix": "SHOP",  "default_price": 50,    "increment": 1},
    "SPCE":  {"option_prefix": "SPCE",  "default_price": 50,    "increment": 1},
    "QCOM":  {"option_prefix": "QCOM",  "default_price": 50,    "increment": 1},
    "IBM":   {"option_prefix": "IBM",   "default_price": 50,    "increment": 1},
    "BE":    {"option_prefix": "BE",    "default_price": 50,    "increment": 1},
    "PANW":  {"option_prefix": "PANW",  "default_price": 50,    "increment": 1},
    "COHR":  {"option_prefix": "COHR",  "default_price": 50,    "increment": 1},
    "SNOW":  {"option_prefix": "SNOW",  "default_price": 50,    "increment": 1},
    "CRM":   {"option_prefix": "CRM",   "default_price": 50,    "increment": 1},
    "NBIS":  {"option_prefix": "NBIS",  "default_price": 50,    "increment": 1},
    "WMT":   {"option_prefix": "WMT",   "default_price": 50,    "increment": 1},
    "HIMS":  {"option_prefix": "HIMS",  "default_price": 50,    "increment": 1},
    "DELL":  {"option_prefix": "DELL",  "default_price": 50,    "increment": 1},
    "CRMV":  {"option_prefix": "CRMV",  "default_price": 50,    "increment": 1},
    "MRVL":  {"option_prefix": "MRVL",  "default_price": 50,    "increment": 1},
    "UAL":   {"option_prefix": "UAL",   "default_price": 50,    "increment": 1},
    "VST":   {"option_prefix": "VST",   "default_price": 50,    "increment": 1},
    "ARM":   {"option_prefix": "ARM",   "default_price": 50,    "increment": 1},
    "CAVA":  {"option_prefix": "CAVA",  "default_price": 50,    "increment": 1},
    "SNDK":  {"option_prefix": "SNDK",  "default_price": 50,    "increment": 1},
}

DXFEED_URL = "wss://tasty-openapi-ws.dxfeed.com/realtime"

def generate_expirations_full(horizon_days: int = 365) -> list[str]:
    """
    Gera a lista completa de vencimentos cobrindo todos os tipos
    presentes na cadeia da Tastytrade:

      0DTE       : hoje (sempre primeiro)
      Diários    : todos os dias uteis nas primeiras 5 semanas
      Semanais   : todas as 6as-feiras de 35 a 90 dias
      Mensais    : 3a sexta-feira de cada mes ate horizon_days
                   (padrao OPEX — cobre AM, PM e trimestrais)

    Ativos sem opcoes em determinada data simplesmente nao retornam
    dados no dxFeed, sem gerar erro.
    """
    import calendar as _cal
    today = datetime.now().date()
    seen  = set()
    exps  = []

    def _add(d):
        s = d.strftime("%y%m%d")
        if s not in seen and d >= today:
            seen.add(s)
            exps.append(s)

    end = today + timedelta(days=horizon_days)

    # 0DTE — sempre primeiro
    _add(today)

    # Diarios: todos os dias uteis nas primeiras 5 semanas
    d = today + timedelta(days=1)
    cutoff_daily = today + timedelta(days=35)
    while d <= cutoff_daily:
        if d.weekday() < 5:
            _add(d)
        d += timedelta(days=1)

    # Semanais: todas as 6as de 35 a 90 dias
    d = cutoff_daily + timedelta(days=1)
    cutoff_weekly = today + timedelta(days=90)
    while d <= cutoff_weekly:
        if d.weekday() == 4:
            _add(d)
        d += timedelta(days=1)

    # Mensais: 3a sexta-feira de cada mes (OPEX)
    year, month = today.year, today.month
    while True:
        first_day    = datetime(year, month, 1).date()
        dow_first    = first_day.weekday()
        days_to_fri  = (4 - dow_first) % 7
        first_fri    = first_day + timedelta(days=days_to_fri)
        third_fri    = first_fri + timedelta(weeks=2)
        if third_fri > end:
            break
        _add(third_fri)
        month += 1
        if month > 12:
            month = 1
            year += 1

    exps.sort()
    return exps


class DEXCalculator:
    """Delta Exposure: DEX = |delta| x OI x 100 x spot"""

    def __init__(self, spot_price: float):
        self.spot_price = spot_price
        self._data: dict = {}

    def update_delta(self, symbol: str, delta, oi) -> None:
        if delta is None or oi is None:
            return
        try:
            delta, oi = float(delta), float(oi)
        except (ValueError, TypeError):
            return
        if math.isnan(delta) or math.isnan(oi):
            return
        self._data[symbol] = {"delta": delta, "oi": oi}

    def get_dex_by_strike(self) -> pd.DataFrame:
        rows: dict = {}
        for sym, d in self._data.items():
            parsed = parse_option_symbol(sym)
            if not parsed:
                continue
            strike   = parsed["strike"]
            opt_type = parsed["type"]
            dex      = abs(d["delta"]) * d["oi"] * 100 * self.spot_price
            if strike not in rows:
                rows[strike] = {"call_dex": 0.0, "put_dex": 0.0,
                                "call_oi": 0.0,  "put_oi": 0.0}
            if opt_type == "C":
                rows[strike]["call_dex"] += dex
                rows[strike]["call_oi"]  += d["oi"]
            else:
                rows[strike]["put_dex"]  += dex
                rows[strike]["put_oi"]   += d["oi"]
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([
            {"strike": s, "call_dex": v["call_dex"], "put_dex": v["put_dex"],
             "net_dex": v["call_dex"] - v["put_dex"],
             "call_oi": v["call_oi"], "put_oi": v["put_oi"]}
            for s, v in rows.items()
        ]).sort_values("strike").reset_index(drop=True)

    def get_total_dex_metrics(self) -> dict:
        df = self.get_dex_by_strike()
        if df.empty:
            return {"total_call_dex": 0, "total_put_dex": 0, "net_dex": 0,
                    "num_options": 0, "max_dex_strike": None, "zero_delta": None}
        total_call = df["call_dex"].sum()
        total_put  = df["put_dex"].sum()
        df["abs_net"] = df["net_dex"].abs()
        max_strike = float(df.loc[df["abs_net"].idxmax(), "strike"])
        zero_delta = None
        for i in range(len(df) - 1):
            n1, n2 = df.iloc[i]["net_dex"], df.iloc[i + 1]["net_dex"]
            if n1 * n2 < 0:
                s1, s2 = df.iloc[i]["strike"], df.iloc[i + 1]["strike"]
                zero_delta = s1 + (s2 - s1) * (-n1) / (n2 - n1)
                break
        return {"total_call_dex": total_call, "total_put_dex": total_put,
                "net_dex": total_call - total_put, "num_options": len(self._data),
                "max_dex_strike": max_strike, "zero_delta": zero_delta}


# WebSocket helpers (identicos ao original)
def connect_websocket(token):
    ws = create_connection(DXFEED_URL, timeout=10)
    ws.send(json.dumps({"type": "SETUP", "channel": 0,
                        "keepaliveTimeout": 60, "acceptKeepaliveTimeout": 60, "version": "1.0.0"}))
    ws.recv()
    while True:
        msg = json.loads(ws.recv())
        if msg.get("type") == "AUTH_STATE":
            if msg["state"] == "UNAUTHORIZED":
                ws.send(json.dumps({"type": "AUTH", "channel": 0, "token": token}))
            elif msg["state"] == "AUTHORIZED":
                break
    ws.send(json.dumps({"type": "CHANNEL_REQUEST", "channel": 1,
                        "service": "FEED", "parameters": {"contract": "AUTO"}}))
    ws.recv()
    return ws


def get_underlying_price(ws, symbol):
    ws.send(json.dumps({"type": "FEED_SUBSCRIPTION", "channel": 1,
                        "add": [{"symbol": symbol, "type": "Trade"},
                                {"symbol": symbol, "type": "Quote"}]}))
    trade_price = quote_mid = None
    start = time.time()
    while time.time() - start < 5:
        try:
            ws.settimeout(1)
            msg = json.loads(ws.recv())
            if msg.get("type") == "FEED_DATA":
                for data in msg.get("data", []):
                    if data.get("eventSymbol") == symbol:
                        if data.get("eventType") == "Trade" and data.get("price"):
                            trade_price = float(data["price"])
                        elif data.get("eventType") == "Quote":
                            try:
                                bid = float(data.get("bidPrice") or 0)
                                ask = float(data.get("askPrice") or 0)
                                if bid and ask:
                                    quote_mid = (bid + ask) / 2
                            except (ValueError, TypeError):
                                pass
            if trade_price:
                return trade_price
            if quote_mid:
                return quote_mid
        except Exception:
            continue
    return trade_price or quote_mid


def generate_option_symbols(center_price, option_prefix, expiration,
                             strikes_up, strikes_down, increment):
    center = round(center_price / increment) * increment
    options = []
    for i in range(-strikes_down, strikes_up + 1):
        strike = center + i * increment
        strike_str = str(int(strike)) if strike == int(strike) else str(strike)
        options.append(f".{option_prefix}{expiration}C{strike_str}")
        options.append(f".{option_prefix}{expiration}P{strike_str}")
    return options


def fetch_option_data(ws, symbols, wait_seconds=15):
    """Coleta Greeks (gamma+delta+IV), OI e Volume via WebSocket."""
    # Envia em lotes de 200 para respeitar limites do dxFeed
    BATCH = 200
    for i in range(0, len(symbols), BATCH):
        subs = []
        for sym in symbols[i:i + BATCH]:
            subs.extend([{"symbol": sym, "type": "Greeks"},
                         {"symbol": sym, "type": "Summary"},
                         {"symbol": sym, "type": "Trade"}])
        ws.send(json.dumps({"type": "FEED_SUBSCRIPTION", "channel": 1, "add": subs}))

    data = {}
    start = time.time()
    while time.time() - start < wait_seconds:
        try:
            ws.settimeout(0.5)
            msg = json.loads(ws.recv())
            if msg.get("type") == "FEED_DATA":
                for item in msg.get("data", []):
                    sym   = item.get("eventSymbol")
                    etype = item.get("eventType")
                    if not sym:
                        continue
                    if sym not in data:
                        data[sym] = {}
                    if etype == "Greeks":
                        data[sym]["gamma"] = item.get("gamma")
                        data[sym]["delta"] = item.get("delta")
                        data[sym]["iv"]    = item.get("volatility")
                    elif etype == "Summary":
                        data[sym]["oi"]    = item.get("openInterest")
                    elif etype == "Trade":
                        data[sym]["volume"] = item.get("dayVolume", 0)
        except Exception:
            continue
    return data


def aggregate_by_strike(option_data):
    strike_data = {}
    for symbol, data in option_data.items():
        parsed = parse_option_symbol(symbol)
        if not parsed:
            continue
        strike   = parsed["strike"]
        opt_type = parsed["type"]
        if strike not in strike_data:
            strike_data[strike] = {"call_oi": 0, "put_oi": 0,
                                   "call_volume": 0, "put_volume": 0,
                                   "call_iv": None, "put_iv": None}
        try:
            oi = float(data.get("oi", 0) or 0)
            oi = 0 if math.isnan(oi) else oi
        except (ValueError, TypeError):
            oi = 0
        try:
            volume = float(data.get("volume", 0) or 0)
            volume = 0 if math.isnan(volume) else volume
        except (ValueError, TypeError):
            volume = 0
        iv = data.get("iv")
        if opt_type == "C":
            strike_data[strike]["call_oi"]     += oi
            strike_data[strike]["call_volume"] += volume
            if iv is not None:
                try:
                    iv_f = float(iv)
                    if not math.isnan(iv_f):
                        strike_data[strike]["call_iv"] = iv_f
                except (ValueError, TypeError):
                    pass
        else:
            strike_data[strike]["put_oi"]      += oi
            strike_data[strike]["put_volume"]  += volume
            if iv is not None:
                try:
                    iv_f = float(iv)
                    if not math.isnan(iv_f):
                        strike_data[strike]["put_iv"] = iv_f
                except (ValueError, TypeError):
                    pass
    if not strike_data:
        return pd.DataFrame()
    return pd.DataFrame([
        {"strike": s, "call_oi": d["call_oi"], "put_oi": d["put_oi"],
         "call_volume": d["call_volume"], "put_volume": d["put_volume"],
         "call_iv": d["call_iv"], "put_iv": d["put_iv"],
         "total_oi": d["call_oi"] + d["put_oi"],
         "total_volume": d["call_volume"] + d["put_volume"]}
        for s, d in strike_data.items()
    ]).sort_values("strike").reset_index(drop=True)


# Chart builders
def build_exposure_chart(df, col_call, col_put, col_net,
                         spot, zero_level, symbol, exp_label, label, chart_type):
    fig = go.Figure()
    if chart_type == "Calls vs Puts":
        fig.add_trace(go.Bar(x=df["strike"], y=df[col_call],
                             name=f"Call {label}", marker_color="green"))
        fig.add_trace(go.Bar(x=df["strike"], y=-df[col_put],
                             name=f"Put {label}", marker_color="red"))
        barmode = "relative"
    else:
        colors = ["green" if x >= 0 else "red" for x in df[col_net]]
        fig.add_trace(go.Bar(x=df["strike"], y=df[col_net],
                             name=f"Net {label}", marker_color=colors))
        fig.add_hline(y=0, line_dash="dot", line_color="gray", line_width=1)
        barmode = "group"
    fig.add_vline(x=spot, line_dash="dash", line_color="orange", line_width=2,
                  annotation_text=f"${spot:,.2f}", annotation_position="top")
    if zero_level:
        fig.add_vline(x=zero_level, line_dash="dot", line_color="purple", line_width=2,
                      annotation_text=f"Zero {label}: ${zero_level:,.2f}",
                      annotation_position="bottom")
    fig.update_layout(title=f"{symbol} {label} by Strike | {exp_label}",
                      xaxis_title="Strike", yaxis_title=f"{label} ($)",
                      barmode=barmode, template="plotly_white", height=500)
    return fig


def build_iv_chart(strike_df, spot, symbol, exp_label):
    fig = go.Figure()
    call_iv = strike_df[strike_df["call_iv"].notna()]
    put_iv  = strike_df[strike_df["put_iv"].notna()]
    if not call_iv.empty:
        fig.add_trace(go.Scatter(x=call_iv["strike"], y=call_iv["call_iv"] * 100,
                                 mode="lines+markers", name="Call IV",
                                 line=dict(color="green", width=2), marker=dict(size=5)))
    if not put_iv.empty:
        fig.add_trace(go.Scatter(x=put_iv["strike"], y=put_iv["put_iv"] * 100,
                                 mode="lines+markers", name="Put IV",
                                 line=dict(color="red", width=2), marker=dict(size=5)))
    fig.add_vline(x=spot, line_dash="dash", line_color="orange", line_width=2,
                  annotation_text=f"${spot:,.2f}", annotation_position="top")
    fig.update_layout(title=f"{symbol} IV Skew | {exp_label}",
                      xaxis_title="Strike", yaxis_title="IV (%)",
                      template="plotly_white", height=400, hovermode="x unified")
    return fig


def build_oi_chart(strike_df, spot):
    fig = go.Figure()
    fig.add_trace(go.Bar(x=strike_df["strike"], y=strike_df["call_oi"],
                         name="Call OI", marker_color="green"))
    fig.add_trace(go.Bar(x=strike_df["strike"], y=-strike_df["put_oi"],
                         name="Put OI", marker_color="red"))
    fig.add_vline(x=spot, line_dash="dash", line_color="orange", line_width=2,
                  annotation_text=f"${spot:,.2f}", annotation_position="top")
    fig.update_layout(title="Open Interest by Strike", xaxis_title="Strike",
                      yaxis_title="Open Interest", barmode="relative",
                      template="plotly_white", height=400)
    return fig


def build_volume_chart(strike_df, spot, view):
    fig = go.Figure()
    if view == "Calls vs Puts":
        fig.add_trace(go.Bar(x=strike_df["strike"], y=strike_df["call_volume"],
                             name="Call Vol", marker_color="lightgreen"))
        fig.add_trace(go.Bar(x=strike_df["strike"], y=-strike_df["put_volume"],
                             name="Put Vol", marker_color="lightcoral"))
        barmode = "relative"
    else:
        fig.add_trace(go.Bar(x=strike_df["strike"],
                             y=strike_df["call_volume"] + strike_df["put_volume"],
                             name="Total Volume", marker_color="purple"))
        barmode = "group"
    fig.add_vline(x=spot, line_dash="dash", line_color="orange", line_width=2,
                  annotation_text=f"${spot:,.2f}", annotation_position="top")
    fig.update_layout(title=f"Volume by Strike | {view}", xaxis_title="Strike",
                      yaxis_title="Volume", barmode=barmode,
                      template="plotly_white", height=400)
    return fig


def fmt_table(df_in, cols):
    out = df_in[list(cols.keys())].copy()
    for col in cols:
        if col == "strike":
            out[col] = out[col].apply(lambda x: f"${x:,.2f}")
        else:
            out[col] = out[col].apply(lambda x: f"${x:,.0f}")
    out.columns = list(cols.values())
    return out


def exp_label(exp_str: str) -> str:
    """Converte YYMMDD para display legivel."""
    try:
        return datetime.strptime(exp_str, "%y%m%d").strftime("%b %d, %Y")
    except Exception:
        return exp_str


# =============================================================================
# Main
# =============================================================================
def main():
    st.title("\U0001f4ca GEX + DEX Dashboard")
    st.caption("Gamma Exposure e Delta Exposure em tempo real — single ou acumulado por vencimento")

    for k, v in {
        "data_fetched":          False,
        "gex_calculator":        None,
        "dex_calculator":        None,
        "underlying_price":      None,
        "option_data":           {},
        "auto_refresh":          False,
        "volume_view":           "Calls vs Puts",
        "symbol":                "SPX",
        "expiration":            datetime.now().strftime("%y%m%d"),
        "is_acumulado":          False,
        "acum_expirations_used": [],
        "acum_breakdown":        {},   # {exp_str: {"gex": GEXCalculator, "dex": DEXCalculator}}
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # =========================================================================
    # Sidebar
    # =========================================================================
    with st.sidebar:
        st.header("\u2699\ufe0f Configuracao")

        symbol = st.selectbox(
            "Underlying Symbol",
            list(PRESET_SYMBOLS.keys()),
            index=list(PRESET_SYMBOLS.keys()).index(
                st.session_state.symbol
                if st.session_state.symbol in PRESET_SYMBOLS else "SPX"
            ),
        )
        preset        = PRESET_SYMBOLS[symbol]
        option_prefix = preset["option_prefix"]
        default_price = preset["default_price"]
        increment     = preset["increment"]
        st.session_state.symbol = symbol

        # ── Modo de coleta ────────────────────────────────────────────────────
        st.subheader("Modo")
        modo = st.radio("Modo de coleta",
                        ["Vencimento unico", "Acumulado (multiplos vencimentos)"],
                        index=0)
        is_acumulado = (modo == "Acumulado (multiplos vencimentos)")

        # ── Expiracao ─────────────────────────────────────────────────────────
        st.subheader("\U0001f4c5 Expiracao")
        if not is_acumulado:
            exp_type = st.radio("Tipo", ["Hoje (0DTE)", "Data customizada"], index=0)
            if exp_type == "Hoje (0DTE)":
                expiration = datetime.now().strftime("%y%m%d")
            else:
                custom_date = st.date_input(
                    "Data de expiracao",
                    value=datetime.now(),
                    min_value=datetime.now(),
                    max_value=datetime.now() + timedelta(days=365),
                )
                expiration = custom_date.strftime("%y%m%d")
            st.session_state.expiration = expiration
            st.caption(f"Vencimento: {exp_label(expiration)}")

        else:
            # Acumulado: mostra todos os vencimentos reais
            all_exps_full = generate_expirations_full(365)

            # Agrupa por categoria para facilitar selecao
            from datetime import date as _date
            today_d = datetime.now().date()
            cut35   = today_d + timedelta(days=35)
            cut90   = today_d + timedelta(days=90)

            def _cat(e):
                d = datetime.strptime(e, "%y%m%d").date()
                if d == today_d:         return "0DTE (hoje)"
                elif d <= cut35:         return "Diarios (ate 5 sem)"
                elif d <= cut90:         return "Semanais (5 sem - 90d)"
                else:                    return "Mensais (90d+)"

            # Filtro por categoria
            cats_disponiveis = ["0DTE (hoje)", "Diarios (ate 5 sem)",
                                "Semanais (5 sem - 90d)", "Mensais (90d+)"]
            cats_sel = st.multiselect(
                "Categorias de vencimento",
                cats_disponiveis,
                default=["0DTE (hoje)", "Diarios (ate 5 sem)", "Semanais (5 sem - 90d)", "Mensais (90d+)"],
                help="Selecione quais grupos de vencimento incluir no acumulado."
            )

            all_exps_filtered = [e for e in all_exps_full if _cat(e) in cats_sel]

            # Multiselect individual (com todos pre-selecionados)
            all_exps = st.multiselect(
                f"Vencimentos ({len(all_exps_filtered)} disponiveis)",
                options=all_exps_filtered,
                default=all_exps_filtered,
                format_func=lambda e: (
                    f"[0DTE] {exp_label(e)}" if e == datetime.now().strftime("%y%m%d")
                    else exp_label(e)
                ),
                help="Desmarque vencimentos especificos para excluir da coleta."
            )

            if all_exps:
                st.caption(
                    f"{len(all_exps)} vencimentos selecionados: "
                    f"{exp_label(all_exps[0])} → {exp_label(all_exps[-1])}"
                )
            else:
                st.warning("Selecione ao menos um vencimento.")

        # ── Strikes ───────────────────────────────────────────────────────────
        st.subheader("\U0001f3af Strikes")
        strikes_up   = st.number_input("Strikes acima",  min_value=5, max_value=100, value=25, step=5)
        strikes_down = st.number_input("Strikes abaixo", min_value=5, max_value=100, value=25, step=5)

        # ── Coleta ────────────────────────────────────────────────────────────
        st.subheader("\U0001f504 Coleta de Dados")
        if not is_acumulado:
            wait_seconds = st.slider("Duracao (seg)", min_value=5, max_value=60, value=15, step=5)
        else:
            wait_per_exp = st.slider(
                "Segundos por vencimento",
                min_value=5, max_value=30, value=10, step=5,
                help="Cada vencimento recebe este tempo de escuta. "
                     "Total = N vencimentos x segundos."
            )

        auto_refresh = st.checkbox("Auto-refresh", value=st.session_state.auto_refresh)
        st.session_state.auto_refresh = auto_refresh

        st.divider()

        btn_label    = "\U0001f504 Buscar Dados" if not is_acumulado else "\U0001f504 Buscar Acumulado"
        btn_disabled = is_acumulado and (not all_exps if is_acumulado else False)
        if st.button(btn_label, type="primary", use_container_width=True,
                     disabled=btn_disabled):
            with st.spinner("Conectando ao Tastytrade..."):
                try:
                    token = ensure_streamer_token()
                    ws    = connect_websocket(token)

                    # Preco do underlying
                    st.info(f"Buscando preco de {symbol}...")
                    price = get_underlying_price(ws, symbol)
                    if not price:
                        st.warning(f"Preco nao obtido — usando padrao: ${default_price}")
                        price = default_price
                    st.session_state.underlying_price = price
                    st.success(f"{symbol}: ${price:,.2f}")

                    if not is_acumulado:
                        # ── Modo vencimento unico ─────────────────────────────
                        options = generate_option_symbols(
                            price, option_prefix, expiration,
                            strikes_up, strikes_down, increment
                        )
                        st.info(f"Coletando {len(options)} opcoes por {wait_seconds}s...")
                        option_data = fetch_option_data(ws, options, wait_seconds)
                        ws.close()

                        gex_calc = GEXCalculator(spot_price=price)
                        dex_calc = DEXCalculator(spot_price=price)
                        for sym_str, d in option_data.items():
                            g, delta, oi = d.get("gamma"), d.get("delta"), d.get("oi")
                            if g     is not None and oi is not None:
                                gex_calc.update_gamma(sym_str, g, oi)
                            if delta is not None and oi is not None:
                                dex_calc.update_delta(sym_str, delta, oi)

                        st.session_state.gex_calculator        = gex_calc
                        st.session_state.dex_calculator        = dex_calc
                        st.session_state.option_data           = option_data
                        st.session_state.is_acumulado          = False
                        st.session_state.acum_expirations_used = []
                        st.session_state.acum_breakdown        = {}
                        st.session_state.data_fetched          = True
                        st.success("\u2705 Dados coletados!")

                    else:
                        # ── Modo acumulado ─────────────────────────────────────
                        gex_acum     = GEXCalculator(spot_price=price)
                        dex_acum     = DEXCalculator(spot_price=price)
                        all_data     = {}
                        breakdown    = {}
                        progress_bar = st.progress(0, text="Iniciando coleta acumulada...")

                        for idx, exp_str in enumerate(all_exps):
                            pct = int(idx / len(all_exps) * 100)
                            progress_bar.progress(
                                pct,
                                text=f"[{idx+1}/{len(all_exps)}] {exp_label(exp_str)} — coletando..."
                            )
                            options = generate_option_symbols(
                                price, option_prefix, exp_str,
                                strikes_up, strikes_down, increment
                            )
                            exp_data = fetch_option_data(ws, options, wait_per_exp)
                            all_data.update(exp_data)

                            # Calculadores individuais para breakdown
                            gex_exp = GEXCalculator(spot_price=price)
                            dex_exp = DEXCalculator(spot_price=price)
                            for sym_str, d in exp_data.items():
                                g, delta, oi = d.get("gamma"), d.get("delta"), d.get("oi")
                                if g     is not None and oi is not None:
                                    gex_exp.update_gamma(sym_str, g, oi)
                                    gex_acum.update_gamma(sym_str, g, oi)
                                if delta is not None and oi is not None:
                                    dex_exp.update_delta(sym_str, delta, oi)
                                    dex_acum.update_delta(sym_str, delta, oi)
                            breakdown[exp_str] = {"gex": gex_exp, "dex": dex_exp}

                        ws.close()
                        progress_bar.progress(100, text="Calculando exposicao acumulada...")

                        st.session_state.gex_calculator        = gex_acum
                        st.session_state.dex_calculator        = dex_acum
                        st.session_state.option_data           = all_data
                        st.session_state.is_acumulado          = True
                        st.session_state.acum_expirations_used = all_exps
                        st.session_state.acum_breakdown        = breakdown
                        st.session_state.data_fetched          = True
                        progress_bar.empty()
                        st.success(
                            f"\u2705 Acumulado: {len(all_exps)} vencimentos, "
                            f"{len(all_data)} opcoes rastreadas."
                        )

                except Exception as e:
                    st.error(f"Erro: {e}")
                    st.session_state.data_fetched = False

    # =========================================================================
    # Tela inicial
    # =========================================================================
    if not st.session_state.data_fetched:
        st.info("\U0001f448 Configure os parametros na barra lateral e clique em Buscar Dados")
        st.markdown("""
### Funcionalidades
- **GEX** — Gamma Exposure por strike
- **DEX** — Delta Exposure por strike
- **Zero Gamma / Zero Delta** — niveis de flip do dealer
- **Acumulado** — soma GEX + DEX de multiplos vencimentos com breakdown por data
- **Volume & OI** por strike
- **IV Skew**
        """)
        return

    # =========================================================================
    # Dashboard
    # =========================================================================
    gex_calc  = st.session_state.gex_calculator
    dex_calc  = st.session_state.dex_calculator
    gex_m     = gex_calc.get_total_gex_metrics()
    dex_m     = dex_calc.get_total_dex_metrics()
    strike_df = aggregate_by_strike(st.session_state.option_data)
    spot      = st.session_state.underlying_price
    sym       = st.session_state.symbol
    is_acum   = st.session_state.is_acumulado
    acum_exps = st.session_state.acum_expirations_used
    breakdown = st.session_state.acum_breakdown

    if is_acum:
        exp_lbl = f"{len(acum_exps)} vencimentos acumulados ({exp_label(acum_exps[0])} → {exp_label(acum_exps[-1])})"
        st.info(f"**Modo Acumulado** — {exp_lbl}")
    else:
        exp_lbl = exp_label(st.session_state.expiration)
        st.info(f"**Vencimento:** {exp_lbl}")

    # Header metrics
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        st.metric(f"{sym} Price", f"${spot:,.2f}")
    with c2:
        st.metric("Opcoes Rastreadas", f"{gex_m['num_options']:,}")
    with c3:
        st.metric("Net GEX", f"${gex_m['net_gex']:,.0f}",
                  help="+ dealers long gamma (mercado estabiliza) | - dealers short gamma")
    with c4:
        zg = gex_m.get("zero_gamma")
        st.metric("Zero Gamma", f"${zg:,.2f}" if zg else "N/A",
                  help="Strike onde Net GEX = 0")
    with c5:
        st.metric("Net DEX", f"${dex_m['net_dex']:,.0f}",
                  help="+ dealers comprados | - dealers vendidos")
    with c6:
        zd = dex_m.get("zero_delta")
        st.metric("Zero Delta", f"${zd:,.2f}" if zd else "N/A",
                  help="Strike onde Net DEX = 0")

    st.divider()

    tab_gex, tab_dex, tab_acum, tab_oi, tab_iv = st.tabs([
        "\U0001f4ca Gamma Exposure (GEX)",
        "\U0001f4d0 Delta Exposure (DEX)",
        "\U0001f4c5 Acumulado por Vencimento",
        "\U0001f4c9 Volume & OI",
        "\U0001f4c8 IV Skew",
    ])

    # ── TAB GEX ──────────────────────────────────────────────────────────────
    with tab_gex:
        gex_df = gex_calc.get_gex_by_strike()
        col_chart, col_stats = st.columns([3, 1])
        with col_chart:
            if gex_df.empty:
                st.warning("Nenhum dado de GEX disponivel.")
            else:
                ct = st.radio("Visualizacao", ["Calls vs Puts", "Net GEX"],
                              horizontal=True, key="gex_ct")
                st.plotly_chart(
                    build_exposure_chart(gex_df, "call_gex", "put_gex", "net_gex",
                                         spot, gex_m.get("zero_gamma"), sym, exp_lbl, "GEX", ct),
                    use_container_width=True)
        with col_stats:
            st.subheader("GEX Total")
            st.metric("Call GEX", f"${gex_m['total_call_gex']:,.0f}")
            st.metric("Put GEX",  f"${gex_m['total_put_gex']:,.0f}")
            st.metric("Net GEX",  f"${gex_m['net_gex']:,.0f}")
            if gex_m.get("max_gex_strike"):
                st.divider()
                st.metric("Maior Strike GEX", f"${gex_m['max_gex_strike']:,.0f}")
            if gex_m.get("zero_gamma"):
                st.divider()
                st.metric("Zero Gamma", f"${gex_m['zero_gamma']:,.2f}",
                          help="Acima: dealers long gamma. Abaixo: dealers short gamma.")
        if not gex_df.empty:
            cols_g = {"strike": "Strike", "call_gex": "Call GEX", "put_gex": "Put GEX", "net_gex": "Net GEX"}
            t1, t2 = st.tabs(["Top Call GEX", "Top Put GEX"])
            with t1:
                st.dataframe(fmt_table(gex_df.nlargest(15, "call_gex"), cols_g),
                             hide_index=True, use_container_width=True)
            with t2:
                st.dataframe(fmt_table(gex_df.nlargest(15, "put_gex"), cols_g),
                             hide_index=True, use_container_width=True)

    # ── TAB DEX ──────────────────────────────────────────────────────────────
    with tab_dex:
        dex_df = dex_calc.get_dex_by_strike()
        col_chart, col_stats = st.columns([3, 1])
        with col_chart:
            if dex_df.empty:
                st.warning("Nenhum dado de DEX disponivel.")
            else:
                ct = st.radio("Visualizacao", ["Calls vs Puts", "Net DEX"],
                              horizontal=True, key="dex_ct")
                st.plotly_chart(
                    build_exposure_chart(dex_df, "call_dex", "put_dex", "net_dex",
                                         spot, dex_m.get("zero_delta"), sym, exp_lbl, "DEX", ct),
                    use_container_width=True)
        with col_stats:
            st.subheader("DEX Total")
            st.metric("Call DEX", f"${dex_m['total_call_dex']:,.0f}")
            st.metric("Put DEX",  f"${dex_m['total_put_dex']:,.0f}")
            st.metric("Net DEX",  f"${dex_m['net_dex']:,.0f}")
            if dex_m.get("max_dex_strike"):
                st.divider()
                st.metric("Maior Strike DEX", f"${dex_m['max_dex_strike']:,.0f}")
            if dex_m.get("zero_delta"):
                st.divider()
                st.metric("Zero Delta", f"${dex_m['zero_delta']:,.2f}",
                          help="Acima: dealers comprados. Abaixo: dealers vendidos.")
        if not dex_df.empty:
            dex_cp = dex_df.copy()
            dex_cp["abs_net"] = dex_cp["net_dex"].abs()
            cols_d = {"strike": "Strike", "call_dex": "Call DEX", "put_dex": "Put DEX", "net_dex": "Net DEX"}
            t1, t2, t3 = st.tabs(["Top Call DEX", "Top Put DEX", "Top |Net DEX|"])
            with t1:
                st.dataframe(fmt_table(dex_cp.nlargest(15, "call_dex"), cols_d),
                             hide_index=True, use_container_width=True)
            with t2:
                st.dataframe(fmt_table(dex_cp.nlargest(15, "put_dex"), cols_d),
                             hide_index=True, use_container_width=True)
            with t3:
                st.dataframe(fmt_table(dex_cp.nlargest(15, "abs_net"), cols_d),
                             hide_index=True, use_container_width=True)
        with st.expander("Como interpretar o DEX"):
            st.markdown("""
| | Calculo |
|---|---|
| **DEX por opcao** | `|delta| x OI x 100 x spot` |
| **Call DEX** | exposicao comprada |
| **Put DEX** | exposicao vendida |
| **Net DEX** | `Call DEX - Put DEX` |

**Zero Delta**: acima → dealers comprados (mercado estabiliza) | abaixo → dealers vendidos (amplificam)
            """)

    # ── TAB ACUMULADO ─────────────────────────────────────────────────────────
    with tab_acum:
        if not is_acum or not breakdown:
            st.info("Execute o modo **Acumulado** na barra lateral para ver o breakdown por vencimento.")
        else:
            st.subheader(f"Breakdown por vencimento — {sym}")
            st.caption(f"{len(acum_exps)} vencimentos | spot: ${spot:,.2f}")

            # Tabela resumo
            rows = []
            for exp_str in acum_exps:
                bd  = breakdown.get(exp_str)
                if not bd:
                    continue
                gm  = bd["gex"].get_total_gex_metrics()
                dm  = bd["dex"].get_total_dex_metrics()
                rows.append({
                    "Vencimento": exp_label(exp_str),
                    "Opcoes":     gm["num_options"],
                    "Call GEX":   f"${gm['total_call_gex']:,.0f}",
                    "Put GEX":    f"${gm['total_put_gex']:,.0f}",
                    "Net GEX":    f"${gm['net_gex']:,.0f}",
                    "Zero Gamma": f"${gm['zero_gamma']:,.2f}" if gm.get("zero_gamma") else "N/A",
                    "Call DEX":   f"${dm['total_call_dex']:,.0f}",
                    "Put DEX":    f"${dm['total_put_dex']:,.0f}",
                    "Net DEX":    f"${dm['net_dex']:,.0f}",
                    "Zero Delta": f"${dm['zero_delta']:,.2f}" if dm.get("zero_delta") else "N/A",
                })
            if rows:
                st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

            st.divider()

            # Graficos por vencimento
            st.subheader("GEX por vencimento")
            view_exp = st.selectbox(
                "Selecione o vencimento para detalhar",
                acum_exps,
                format_func=exp_label,
                key="acum_detail_exp"
            )
            bd = breakdown.get(view_exp)
            if bd:
                gdf = bd["gex"].get_gex_by_strike()
                ddf = bd["dex"].get_dex_by_strike()
                gm2 = bd["gex"].get_total_gex_metrics()
                dm2 = bd["dex"].get_total_dex_metrics()

                c_g, c_d = st.columns(2)
                with c_g:
                    if not gdf.empty:
                        ct_g = st.radio("GEX view", ["Calls vs Puts", "Net GEX"],
                                        horizontal=True, key="acum_gex_ct")
                        st.plotly_chart(
                            build_exposure_chart(
                                gdf, "call_gex", "put_gex", "net_gex",
                                spot, gm2.get("zero_gamma"), sym,
                                exp_label(view_exp), "GEX", ct_g),
                            use_container_width=True)
                with c_d:
                    if not ddf.empty:
                        ct_d = st.radio("DEX view", ["Calls vs Puts", "Net DEX"],
                                        horizontal=True, key="acum_dex_ct")
                        st.plotly_chart(
                            build_exposure_chart(
                                ddf, "call_dex", "put_dex", "net_dex",
                                spot, dm2.get("zero_delta"), sym,
                                exp_label(view_exp), "DEX", ct_d),
                            use_container_width=True)

    # ── TAB OI & VOLUME ───────────────────────────────────────────────────────
    with tab_oi:
        if strike_df.empty:
            st.warning("Dados de OI/Volume indisponiveis.")
        else:
            c3, c4 = st.columns(2)
            with c3:
                st.plotly_chart(build_oi_chart(strike_df, spot), use_container_width=True)
            with c4:
                vol_view = st.radio(
                    "Volume View", ["Calls vs Puts", "Total Volume"],
                    index=["Calls vs Puts", "Total Volume"].index(st.session_state.volume_view),
                    key="vol_view_radio", horizontal=True)
                st.session_state.volume_view = vol_view
                st.plotly_chart(build_volume_chart(strike_df, spot, vol_view), use_container_width=True)
            st.subheader("Top Strikes")
            t_oi, t_vol = st.tabs(["Por OI Total", "Por Volume Total"])
            with t_oi:
                top = strike_df.nlargest(15, "total_oi")[["strike", "call_oi", "put_oi", "total_oi"]]
                top["strike"] = top["strike"].apply(lambda x: f"${x:,.2f}")
                top.columns = ["Strike", "Call OI", "Put OI", "Total OI"]
                st.dataframe(top, hide_index=True, use_container_width=True)
            with t_vol:
                top = strike_df.nlargest(15, "total_volume")[["strike", "call_volume", "put_volume", "total_volume"]]
                top["strike"] = top["strike"].apply(lambda x: f"${x:,.2f}")
                top.columns = ["Strike", "Call Vol", "Put Vol", "Total Vol"]
                st.dataframe(top, hide_index=True, use_container_width=True)

    # ── TAB IV SKEW ───────────────────────────────────────────────────────────
    with tab_iv:
        has_iv = (not strike_df.empty and
                  (strike_df["call_iv"].notna().any() or strike_df["put_iv"].notna().any()))
        if not has_iv:
            st.warning("Dados de IV indisponiveis.")
        else:
            st.plotly_chart(build_iv_chart(strike_df, spot, sym, exp_lbl),
                            use_container_width=True)

    if st.session_state.auto_refresh:
        time.sleep(1)
        st.rerun()


if __name__ == "__main__":
    main()
