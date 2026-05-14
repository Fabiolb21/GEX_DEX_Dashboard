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

st.set_page_config(page_title="GEX + DEX Dashboard", page_icon="📊", layout="wide")

# ---------------------------------------------------------------------------
# Preset symbol configuration  (expandido vs. original)
# ---------------------------------------------------------------------------
PRESET_SYMBOLS = {
    # ── Índices ──────────────────────────────────────────────────────────────
    "SPX":   {"option_prefix": "SPXW",  "default_price": 5800,  "increment": 5},
    "XSP":   {"option_prefix":  "XSP",  "default_price": 50,   "increment": 1},
    "NDX":   {"option_prefix": "NDXP",  "default_price": 20000, "increment": 25},
    "RUT":   {"option_prefix": "RUTW",  "default_price": 2100,  "increment": 5},
    "DJX":   {"option_prefix": "DJX",   "default_price": 430,   "increment": 1},
    "VIX":   {"option_prefix": "VIX",   "default_price": 18,    "increment": 0.5},
    # ── ETFs amplos ──────────────────────────────────────────────────────────
    "SPY":   {"option_prefix": "SPY",   "default_price": 580,   "increment": 1},
    "QQQ":   {"option_prefix": "QQQ",   "default_price": 490,   "increment": 1},
    "IWM":   {"option_prefix": "IWM",   "default_price": 210,   "increment": 1},
    "DIA":   {"option_prefix": "DIA",   "default_price": 430,   "increment": 1},
    # ── ETFs setoriais / temáticos ────────────────────────────────────────────
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
    # ── Ações com alta atividade em opções ────────────────────────────────────
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
}

DXFEED_URL = "wss://tasty-openapi-ws.dxfeed.com/realtime"


# ---------------------------------------------------------------------------
# DEX Calculator  (novo — Delta Exposure)
# ---------------------------------------------------------------------------
class DEXCalculator:
    """
    Delta Exposure por strike.

        DEX  =  |delta|  ×  OI  ×  100  ×  spot_price

    Calls: delta > 0  →  pressão comprada no underlying
    Puts:  delta < 0  →  pressão vendida no underlying
    Net DEX = Call DEX − Put DEX
    Zero-Delta Flip = strike onde Net DEX cruza zero (mesma lógica do Zero Gamma)
    """

    def __init__(self, spot_price: float):
        self.spot_price = spot_price
        self._data: dict[str, dict] = {}

    def update_delta(self, symbol: str, delta, oi) -> None:
        if delta is None or oi is None:
            return
        try:
            delta = float(delta)
            oi    = float(oi)
        except (ValueError, TypeError):
            return
        if math.isnan(delta) or math.isnan(oi):
            return
        self._data[symbol] = {"delta": delta, "oi": oi}

    def get_dex_by_strike(self) -> pd.DataFrame:
        rows: dict[float, dict] = {}
        for sym, d in self._data.items():
            parsed = parse_option_symbol(sym)
            if not parsed:
                continue
            strike   = parsed["strike"]
            opt_type = parsed["type"]
            dex      = abs(d["delta"]) * d["oi"] * 100 * self.spot_price

            if strike not in rows:
                rows[strike] = {"call_dex": 0.0, "put_dex": 0.0,
                                "call_oi":  0.0, "put_oi":  0.0}
            if opt_type == "C":
                rows[strike]["call_dex"] += dex
                rows[strike]["call_oi"]  += d["oi"]
            else:
                rows[strike]["put_dex"]  += dex
                rows[strike]["put_oi"]   += d["oi"]

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame([
            {
                "strike":   s,
                "call_dex": v["call_dex"],
                "put_dex":  v["put_dex"],
                "net_dex":  v["call_dex"] - v["put_dex"],
                "call_oi":  v["call_oi"],
                "put_oi":   v["put_oi"],
            }
            for s, v in rows.items()
        ]).sort_values("strike").reset_index(drop=True)
        return df

    def get_total_dex_metrics(self) -> dict:
        df = self.get_dex_by_strike()
        if df.empty:
            return {"total_call_dex": 0, "total_put_dex": 0,
                    "net_dex": 0, "num_options": 0,
                    "max_dex_strike": None, "zero_delta": None}

        total_call = df["call_dex"].sum()
        total_put  = df["put_dex"].sum()
        net        = total_call - total_put

        df["abs_net"] = df["net_dex"].abs()
        max_strike    = float(df.loc[df["abs_net"].idxmax(), "strike"])

        # Zero-Delta Flip via interpolação linear
        zero_delta = None
        for i in range(len(df) - 1):
            n1, n2 = df.iloc[i]["net_dex"], df.iloc[i + 1]["net_dex"]
            if n1 * n2 < 0:
                s1, s2    = df.iloc[i]["strike"], df.iloc[i + 1]["strike"]
                zero_delta = s1 + (s2 - s1) * (-n1) / (n2 - n1)
                break

        return {
            "total_call_dex": total_call,
            "total_put_dex":  total_put,
            "net_dex":        net,
            "num_options":    len(self._data),
            "max_dex_strike": max_strike,
            "zero_delta":     zero_delta,
        }


# ---------------------------------------------------------------------------
# WebSocket helpers
# ---------------------------------------------------------------------------
def connect_websocket(token):
    ws = create_connection(DXFEED_URL, timeout=10)
    ws.send(json.dumps({
        "type": "SETUP", "channel": 0,
        "keepaliveTimeout": 60, "acceptKeepaliveTimeout": 60, "version": "1.0.0"
    }))
    ws.recv()
    while True:
        msg = json.loads(ws.recv())
        if msg.get("type") == "AUTH_STATE":
            if msg["state"] == "UNAUTHORIZED":
                ws.send(json.dumps({"type": "AUTH", "channel": 0, "token": token}))
            elif msg["state"] == "AUTHORIZED":
                break
    ws.send(json.dumps({
        "type": "CHANNEL_REQUEST", "channel": 1,
        "service": "FEED", "parameters": {"contract": "AUTO"}
    }))
    ws.recv()
    return ws


def get_underlying_price(ws, symbol):
    ws.send(json.dumps({
        "type": "FEED_SUBSCRIPTION", "channel": 1,
        "add": [
            {"symbol": symbol, "type": "Trade"},
            {"symbol": symbol, "type": "Quote"},
        ]
    }))
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
        strike     = center + i * increment
        strike_str = str(int(strike)) if strike == int(strike) else str(strike)
        options.append(f".{option_prefix}{expiration}C{strike_str}")
        options.append(f".{option_prefix}{expiration}P{strike_str}")
    return options


def fetch_option_data(ws, symbols, wait_seconds=15):
    """
    Coleta Greeks (gamma + delta + IV), Summary (OI) e Trade (volume).
    Retorna dict com todos os campos necessários para GEX e DEX.
    """
    subs = []
    for sym in symbols:
        subs.extend([
            {"symbol": sym, "type": "Greeks"},
            {"symbol": sym, "type": "Summary"},
            {"symbol": sym, "type": "Trade"},
        ])
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
                    if sym not in data:
                        data[sym] = {}
                    if etype == "Greeks":
                        data[sym]["gamma"] = item.get("gamma")
                        data[sym]["delta"] = item.get("delta")   # ← novo
                        data[sym]["iv"]    = item.get("volatility")
                    elif etype == "Summary":
                        data[sym]["oi"]    = item.get("openInterest")
                    elif etype == "Trade":
                        data[sym]["volume"] = item.get("dayVolume", 0)
        except Exception:
            continue
    return data


# ---------------------------------------------------------------------------
# Aggregate helpers
# ---------------------------------------------------------------------------
def aggregate_by_strike(option_data):
    """Agrega OI, volume e IV por strike (igual ao original)."""
    strike_data = {}
    for symbol, data in option_data.items():
        parsed = parse_option_symbol(symbol)
        if not parsed:
            continue
        strike   = parsed["strike"]
        opt_type = parsed["type"]

        if strike not in strike_data:
            strike_data[strike] = {
                "call_oi": 0, "put_oi": 0,
                "call_volume": 0, "put_volume": 0,
                "call_iv": None, "put_iv": None,
            }

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
            if iv is not None and not math.isnan(iv):
                strike_data[strike]["call_iv"] = iv
        else:
            strike_data[strike]["put_oi"]      += oi
            strike_data[strike]["put_volume"]  += volume
            if iv is not None and not math.isnan(iv):
                strike_data[strike]["put_iv"] = iv

    return pd.DataFrame([
        {
            "strike":       s,
            "call_oi":      d["call_oi"],
            "put_oi":       d["put_oi"],
            "call_volume":  d["call_volume"],
            "put_volume":   d["put_volume"],
            "call_iv":      d["call_iv"],
            "put_iv":       d["put_iv"],
            "total_oi":     d["call_oi"]     + d["put_oi"],
            "total_volume": d["call_volume"] + d["put_volume"],
        }
        for s, d in strike_data.items()
    ]).sort_values("strike").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Chart builders  (reutilizados por GEX e DEX)
# ---------------------------------------------------------------------------
def build_exposure_chart(df, col_call, col_put, col_net,
                         spot, zero_level, symbol, expiration,
                         label, chart_type):
    """Gera figura Plotly para GEX ou DEX."""
    exp_display = expiration
    try:
        exp_display = datetime.strptime(expiration, "%y%m%d").strftime("%b %d, %Y")
    except Exception:
        pass

    fig = go.Figure()

    if chart_type == "Calls vs Puts":
        fig.add_trace(go.Bar(
            x=df["strike"], y=df[col_call],
            name=f"Call {label}", marker_color="green"
        ))
        fig.add_trace(go.Bar(
            x=df["strike"], y=-df[col_put],
            name=f"Put {label}", marker_color="red"
        ))
        barmode = "relative"
    else:  # Net
        colors = ["green" if x >= 0 else "red" for x in df[col_net]]
        fig.add_trace(go.Bar(
            x=df["strike"], y=df[col_net],
            name=f"Net {label}", marker_color=colors
        ))
        fig.add_hline(y=0, line_dash="dot", line_color="gray", line_width=1)
        barmode = "group"

    fig.add_vline(
        x=spot, line_dash="dash", line_color="orange", line_width=2,
        annotation_text=f"${spot:,.2f}", annotation_position="top"
    )
    if zero_level:
        fig.add_vline(
            x=zero_level, line_dash="dot", line_color="purple", line_width=2,
            annotation_text=f"Zero {label}: ${zero_level:,.2f}",
            annotation_position="bottom"
        )

    fig.update_layout(
        title=f"{symbol} {label} by Strike — Exp: {exp_display}",
        xaxis_title="Strike Price",
        yaxis_title=f"{label} ($)",
        barmode=barmode,
        template="plotly_white",
        height=500,
    )
    return fig


def build_iv_chart(strike_df, spot, symbol, expiration):
    exp_display = expiration
    try:
        exp_display = datetime.strptime(expiration, "%y%m%d").strftime("%b %d, %Y")
    except Exception:
        pass

    fig = go.Figure()
    call_iv = strike_df[strike_df["call_iv"].notna()]
    put_iv  = strike_df[strike_df["put_iv"].notna()]
    if not call_iv.empty:
        fig.add_trace(go.Scatter(
            x=call_iv["strike"], y=call_iv["call_iv"] * 100,
            mode="lines+markers", name="Call IV",
            line=dict(color="green", width=2), marker=dict(size=6)
        ))
    if not put_iv.empty:
        fig.add_trace(go.Scatter(
            x=put_iv["strike"], y=put_iv["put_iv"] * 100,
            mode="lines+markers", name="Put IV",
            line=dict(color="red", width=2), marker=dict(size=6)
        ))
    fig.add_vline(
        x=spot, line_dash="dash", line_color="orange", line_width=2,
        annotation_text=f"${spot:,.2f}", annotation_position="top"
    )
    fig.update_layout(
        title=f"{symbol} Implied Volatility Skew — Exp: {exp_display}",
        xaxis_title="Strike", yaxis_title="IV (%)",
        template="plotly_white", height=400, hovermode="x unified"
    )
    return fig


def build_oi_chart(strike_df, spot):
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=strike_df["strike"], y=strike_df["call_oi"],
        name="Call OI", marker_color="green"
    ))
    fig.add_trace(go.Bar(
        x=strike_df["strike"], y=-strike_df["put_oi"],
        name="Put OI", marker_color="red"
    ))
    fig.add_vline(
        x=spot, line_dash="dash", line_color="orange", line_width=2,
        annotation_text=f"${spot:,.2f}", annotation_position="top"
    )
    fig.update_layout(
        title="Open Interest by Strike",
        xaxis_title="Strike", yaxis_title="Open Interest",
        barmode="relative", template="plotly_white", height=400
    )
    return fig


def build_volume_chart(strike_df, spot, view):
    fig = go.Figure()
    if view == "Calls vs Puts":
        fig.add_trace(go.Bar(
            x=strike_df["strike"], y=strike_df["call_volume"],
            name="Call Vol", marker_color="lightgreen"
        ))
        fig.add_trace(go.Bar(
            x=strike_df["strike"], y=-strike_df["put_volume"],
            name="Put Vol", marker_color="lightcoral"
        ))
        barmode = "relative"
    else:
        fig.add_trace(go.Bar(
            x=strike_df["strike"],
            y=strike_df["call_volume"] + strike_df["put_volume"],
            name="Total Volume", marker_color="purple"
        ))
        barmode = "group"
    fig.add_vline(
        x=spot, line_dash="dash", line_color="orange", line_width=2,
        annotation_text=f"${spot:,.2f}", annotation_position="top"
    )
    fig.update_layout(
        title=f"Volume by Strike — {view}",
        xaxis_title="Strike", yaxis_title="Volume",
        barmode=barmode, template="plotly_white", height=400
    )
    return fig


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    st.title("📊 GEX + DEX Dashboard")
    st.caption("Gamma Exposure (GEX) e Delta Exposure (DEX) em tempo real")

    # ── Session state ────────────────────────────────────────────────────────
    for k, v in {
        "data_fetched": False,
        "gex_calculator": None,
        "dex_calculator": None,
        "underlying_price": None,
        "option_data": {},
        "auto_refresh": False,
        "volume_view": "Calls vs Puts",
        "symbol": "SPX",
        "expiration": datetime.now().strftime("%y%m%d"),
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # ── Sidebar ──────────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("⚙️ Configuração")

        # Ticker
        symbol = st.selectbox(
            "Underlying Symbol",
            list(PRESET_SYMBOLS.keys()),
            index=list(PRESET_SYMBOLS.keys()).index(
                st.session_state.symbol
                if st.session_state.symbol in PRESET_SYMBOLS else "SPX"
            ),
            help="Índice, ETF ou ação com opções ativas",
        )
        preset        = PRESET_SYMBOLS[symbol]
        option_prefix = preset["option_prefix"]
        default_price = preset["default_price"]
        increment     = preset["increment"]
        st.session_state.symbol = symbol

        # Expiration
        st.subheader("📅 Expiração")
        exp_type = st.radio("Tipo", ["Hoje (0DTE)", "Data customizada"], index=0)
        if exp_type == "Hoje (0DTE)":
            expiration = datetime.now().strftime("%y%m%d")
        else:
            custom_date = st.date_input(
                "Data de expiração",
                value=datetime.now(),
                min_value=datetime.now(),
                max_value=datetime.now() + timedelta(days=365),
            )
            expiration = custom_date.strftime("%y%m%d")
        st.session_state.expiration = expiration

        # Strikes
        st.subheader("🎯 Strikes")
        strikes_up   = st.number_input("Strikes acima",  min_value=5, max_value=100, value=25, step=5)
        strikes_down = st.number_input("Strikes abaixo", min_value=5, max_value=100, value=25, step=5)

        # Fetch
        st.subheader("🔄 Coleta de Dados")
        wait_seconds = st.slider(
            "Duração da coleta (seg)", min_value=5, max_value=30, value=15, step=5,
            help="Tempo de escuta do WebSocket. Mais tempo = dados mais completos."
        )
        auto_refresh = st.checkbox(
            "Auto-refresh",
            value=st.session_state.auto_refresh,
            help="Re-coleta automaticamente ao fim de cada ciclo"
        )
        st.session_state.auto_refresh = auto_refresh

        st.divider()

        if st.button("🔄 Buscar Dados", type="primary", use_container_width=True):
            with st.spinner("Conectando ao Tastytrade..."):
                try:
                    token = ensure_streamer_token()
                    ws    = connect_websocket(token)

                    st.info(f"Buscando preço de {symbol}...")
                    underlying_price = get_underlying_price(ws, symbol)
                    if not underlying_price:
                        st.warning(f"Preço não obtido — usando padrão: ${default_price}")
                        underlying_price = default_price
                    st.session_state.underlying_price = underlying_price
                    st.success(f"{symbol}: ${underlying_price:,.2f}")

                    st.info(f"Gerando símbolos de opções em torno de ${underlying_price:,.2f}...")
                    options = generate_option_symbols(
                        underlying_price, option_prefix, expiration,
                        strikes_up, strikes_down, increment
                    )
                    st.info(f"Coletando dados para {len(options)} opções ({wait_seconds}s)...")

                    option_data = fetch_option_data(ws, options, wait_seconds)
                    ws.close()

                    # ── GEX ─────────────────────────────────────────────────
                    st.info("Calculando Gamma Exposure (GEX)...")
                    gex_calc = GEXCalculator(spot_price=underlying_price)
                    for sym_str, d in option_data.items():
                        gamma = d.get("gamma")
                        oi    = d.get("oi")
                        if gamma is not None and oi is not None:
                            gex_calc.update_gamma(sym_str, gamma, oi)

                    # ── DEX ─────────────────────────────────────────────────
                    st.info("Calculando Delta Exposure (DEX)...")
                    dex_calc = DEXCalculator(spot_price=underlying_price)
                    for sym_str, d in option_data.items():
                        delta = d.get("delta")
                        oi    = d.get("oi")
                        if delta is not None and oi is not None:
                            dex_calc.update_delta(sym_str, delta, oi)

                    st.session_state.gex_calculator = gex_calc
                    st.session_state.dex_calculator = dex_calc
                    st.session_state.option_data    = option_data
                    st.session_state.data_fetched   = True
                    st.success("✅ Dados coletados com sucesso!")

                except Exception as e:
                    st.error(f"Erro: {e}")
                    st.session_state.data_fetched = False

    # ── Tela inicial ─────────────────────────────────────────────────────────
    if not st.session_state.data_fetched:
        st.info("👈 Configure os parâmetros na barra lateral e clique em 'Buscar Dados'")
        st.markdown("""
        ### Funcionalidades:
        - 📊 **GEX** — Gamma Exposure por strike (sensibilidade do dealer ao preço)
        - 📐 **DEX** — Delta Exposure por strike (posicionamento direcional líquido)
        - 🎯 **Zero Gamma / Zero Delta** — Níveis de flip do dealer
        - 📉 **Volume & Open Interest** por strike
        - 📈 **IV Skew** — Volatilidade implícita across strikes
        - 🔄 Auto-refresh para monitoramento contínuo

        ### Tickers disponíveis:
        **Índices:** SPX, NDX, RUT, DJX, VIX  
        **ETFs:** SPY, QQQ, IWM, DIA, GLD, SLV, TLT, XLE, XLF, XLK, EEM, EWZ, …  
        **Ações:** AAPL, MSFT, NVDA, TSLA, AMZN, GOOGL, META, AMD, COIN, MSTR, …
        """)
        return

    # ── Resultados ────────────────────────────────────────────────────────────
    gex_calc  = st.session_state.gex_calculator
    dex_calc  = st.session_state.dex_calculator
    gex_m     = gex_calc.get_total_gex_metrics()
    dex_m     = dex_calc.get_total_dex_metrics()
    strike_df = aggregate_by_strike(st.session_state.option_data)
    spot      = st.session_state.underlying_price
    sym       = st.session_state.symbol
    exp       = st.session_state.expiration

    # ── Header metrics ────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        st.metric(f"{sym} Price", f"${spot:,.2f}")
    with c2:
        st.metric("Opções Rastreadas", f"{gex_m['num_options']:,}")
    with c3:
        st.metric("Net GEX", f"${gex_m['net_gex']:,.0f}")
    with c4:
        st.metric(
            "Zero Gamma",
            f"${gex_m['zero_gamma']:,.2f}" if gex_m.get("zero_gamma") else "N/A"
        )
    with c5:
        st.metric("Net DEX", f"${dex_m['net_dex']:,.0f}")
    with c6:
        st.metric(
            "Zero Delta",
            f"${dex_m['zero_delta']:,.2f}" if dex_m.get("zero_delta") else "N/A"
        )

    st.divider()

    # ── Tabs principais ───────────────────────────────────────────────────────
    tab_gex, tab_dex, tab_oi, tab_iv = st.tabs([
        "📊 Gamma Exposure (GEX)",
        "📐 Delta Exposure (DEX)",
        "📉 Volume & Open Interest",
        "📈 IV Skew",
    ])

    # ════════════════════════════════════════════════════════════════════
    # TAB 1 — GEX
    # ════════════════════════════════════════════════════════════════════
    with tab_gex:
        gex_df = gex_calc.get_gex_by_strike()

        col_chart, col_stats = st.columns([3, 1])

        with col_chart:
            if gex_df.empty:
                st.warning("Nenhum dado de GEX disponível.")
            else:
                chart_type = st.radio(
                    "Visualização GEX",
                    ["Calls vs Puts", "Net GEX"],
                    horizontal=True,
                    key="gex_chart_type",
                )
                fig_gex = build_exposure_chart(
                    gex_df, "call_gex", "put_gex", "net_gex",
                    spot, gex_m.get("zero_gamma"), sym, exp,
                    "GEX", chart_type
                )
                st.plotly_chart(fig_gex, use_container_width=True)

        with col_stats:
            st.subheader("📈 GEX Total")
            st.metric("Call GEX",  f"${gex_m['total_call_gex']:,.0f}")
            st.metric("Put GEX",   f"${gex_m['total_put_gex']:,.0f}")
            st.metric("Net GEX",   f"${gex_m['net_gex']:,.0f}")
            if gex_m.get("max_gex_strike"):
                st.divider()
                st.metric("Maior Strike GEX", f"${gex_m['max_gex_strike']:,.0f}")
            if gex_m.get("zero_gamma"):
                st.divider()
                st.metric(
                    "Zero Gamma (Flip)",
                    f"${gex_m['zero_gamma']:,.2f}",
                    help="Strike onde Net GEX cruza zero. "
                         "Acima: dealers long gamma (compram queda, vendem alta). "
                         "Abaixo: dealers short gamma (amplificam movimentos).",
                )

        if not gex_df.empty:
            st.subheader("📋 Top Strikes — GEX")
            t1, t2 = st.tabs(["Por Call GEX", "Por Put GEX"])
            with t1:
                top = gex_df.nlargest(10, "call_gex")[["strike", "call_gex", "put_gex", "net_gex"]]
                top["strike"]   = top["strike"].apply(lambda x: f"${x:,.0f}")
                top["call_gex"] = top["call_gex"].apply(lambda x: f"${x:,.0f}")
                top["put_gex"]  = top["put_gex"].apply(lambda x: f"${x:,.0f}")
                top["net_gex"]  = top["net_gex"].apply(lambda x: f"${x:,.0f}")
                top.columns     = ["Strike", "Call GEX", "Put GEX", "Net GEX"]
                st.dataframe(top, hide_index=True, use_container_width=True)
            with t2:
                top = gex_df.nlargest(10, "put_gex")[["strike", "call_gex", "put_gex", "net_gex"]]
                top["strike"]   = top["strike"].apply(lambda x: f"${x:,.0f}")
                top["call_gex"] = top["call_gex"].apply(lambda x: f"${x:,.0f}")
                top["put_gex"]  = top["put_gex"].apply(lambda x: f"${x:,.0f}")
                top["net_gex"]  = top["net_gex"].apply(lambda x: f"${x:,.0f}")
                top.columns     = ["Strike", "Call GEX", "Put GEX", "Net GEX"]
                st.dataframe(top, hide_index=True, use_container_width=True)

    # ════════════════════════════════════════════════════════════════════
    # TAB 2 — DEX
    # ════════════════════════════════════════════════════════════════════
    with tab_dex:
        dex_df = dex_calc.get_dex_by_strike()

        col_chart, col_stats = st.columns([3, 1])

        with col_chart:
            if dex_df.empty:
                st.warning("Nenhum dado de DEX disponível.")
            else:
                chart_type = st.radio(
                    "Visualização DEX",
                    ["Calls vs Puts", "Net DEX"],
                    horizontal=True,
                    key="dex_chart_type",
                )
                fig_dex = build_exposure_chart(
                    dex_df, "call_dex", "put_dex", "net_dex",
                    spot, dex_m.get("zero_delta"), sym, exp,
                    "DEX", chart_type
                )
                st.plotly_chart(fig_dex, use_container_width=True)

        with col_stats:
            st.subheader("📐 DEX Total")
            st.metric("Call DEX",  f"${dex_m['total_call_dex']:,.0f}")
            st.metric("Put DEX",   f"${dex_m['total_put_dex']:,.0f}")
            st.metric("Net DEX",   f"${dex_m['net_dex']:,.0f}")
            if dex_m.get("max_dex_strike"):
                st.divider()
                st.metric("Maior Strike DEX", f"${dex_m['max_dex_strike']:,.0f}")
            if dex_m.get("zero_delta"):
                st.divider()
                st.metric(
                    "Zero Delta (Flip)",
                    f"${dex_m['zero_delta']:,.2f}",
                    help="Strike onde Net DEX cruza zero. "
                         "Indica nível onde posicionamento direcional líquido muda de sinal.",
                )

        if not dex_df.empty:
            st.subheader("📋 Top Strikes — DEX")
            t1, t2, t3 = st.tabs(["Por Call DEX", "Por Put DEX", "Por |Net DEX|"])
            with t1:
                top = dex_df.nlargest(10, "call_dex")[["strike", "call_dex", "put_dex", "net_dex"]]
            with t2:
                top = dex_df.nlargest(10, "put_dex")[["strike", "call_dex", "put_dex", "net_dex"]]
            with t3:
                dex_df_copy = dex_df.copy()
                dex_df_copy["abs_net"] = dex_df_copy["net_dex"].abs()
                top = dex_df_copy.nlargest(10, "abs_net")[["strike", "call_dex", "put_dex", "net_dex"]]

            # Formata e exibe a tabela da última aba ativa
            # (cada with já atribuiu `top`; mostra a última — t3)
            for tab_obj, sort_col in [(t1, "call_dex"), (t2, "put_dex")]:
                pass  # já atribuídos acima

            # Exibe tabela dentro de cada aba corretamente
            for tab_ref, col_sort in [(t1, "call_dex"), (t2, "put_dex"), (t3, "abs_net" if "abs_net" in dex_df.columns else "net_dex")]:
                with tab_ref:
                    pass  # blocos já fechados; usamos abordagem alternativa abaixo

        # Re-renderiza tabelas com contexto correto
        if not dex_df.empty:
            t_a, t_b, t_c = st.tabs(["Top Call DEX", "Top Put DEX", "Top |Net DEX|"])
            dex_df2 = dex_df.copy()
            dex_df2["abs_net_dex"] = dex_df2["net_dex"].abs()

            def _fmt_dex_table(df_in):
                out = df_in[["strike", "call_dex", "put_dex", "net_dex"]].copy()
                out["strike"]   = out["strike"].apply(lambda x: f"${x:,.0f}")
                out["call_dex"] = out["call_dex"].apply(lambda x: f"${x:,.0f}")
                out["put_dex"]  = out["put_dex"].apply(lambda x: f"${x:,.0f}")
                out["net_dex"]  = out["net_dex"].apply(lambda x: f"${x:,.0f}")
                out.columns     = ["Strike", "Call DEX", "Put DEX", "Net DEX"]
                return out

            with t_a:
                st.dataframe(_fmt_dex_table(dex_df2.nlargest(10, "call_dex")),
                             hide_index=True, use_container_width=True)
            with t_b:
                st.dataframe(_fmt_dex_table(dex_df2.nlargest(10, "put_dex")),
                             hide_index=True, use_container_width=True)
            with t_c:
                st.dataframe(_fmt_dex_table(dex_df2.nlargest(10, "abs_net_dex")),
                             hide_index=True, use_container_width=True)

        # Explicação
        with st.expander("ℹ️ Como interpretar o DEX"):
            st.markdown("""
            **Delta Exposure (DEX)** mede a posição direcional líquida dos dealers no underlying.

            | Fórmula | DEX = |delta| × OI × 100 × Spot |
            |---------|-----------------------------------|
            | **Call DEX** | Exposição comprada (delta positivo) |
            | **Put DEX**  | Exposição vendida (delta negativo, sinal invertido na dealer convention) |
            | **Net DEX**  | Call DEX − Put DEX |

            **Zero Delta (Flip Level)**
            - **Acima do Zero Delta**: Net DEX positivo → dealers comprados no underlying → tendem a vender rallies e comprar quedas (estabilizador)
            - **Abaixo do Zero Delta**: Net DEX negativo → dealers vendidos → tendem a amplificar movimentos

            **Diferença GEX × DEX**
            - **GEX** usa *gamma* → mede a *velocidade de rehedge* do dealer
            - **DEX** usa *delta* → mede o *tamanho da posição direcional* do dealer
            """)

    # ════════════════════════════════════════════════════════════════════
    # TAB 3 — OI & Volume
    # ════════════════════════════════════════════════════════════════════
    with tab_oi:
        if strike_df.empty:
            st.warning("Dados de OI/Volume indisponíveis.")
        else:
            col3, col4 = st.columns(2)
            with col3:
                st.plotly_chart(build_oi_chart(strike_df, spot), use_container_width=True)
            with col4:
                vol_view = st.radio(
                    "Volume View",
                    ["Calls vs Puts", "Total Volume"],
                    index=["Calls vs Puts", "Total Volume"].index(st.session_state.volume_view),
                    key="volume_view_radio",
                    horizontal=True,
                )
                st.session_state.volume_view = vol_view
                st.plotly_chart(build_volume_chart(strike_df, spot, vol_view), use_container_width=True)

            st.subheader("🔝 Top Strikes")
            tab_by_oi, tab_by_vol = st.tabs(["Por OI Total", "Por Volume Total"])
            with tab_by_oi:
                top_oi = strike_df.nlargest(10, "total_oi")[
                    ["strike", "call_oi", "put_oi", "total_oi"]
                ]
                top_oi["strike"] = top_oi["strike"].apply(lambda x: f"${x:,.0f}")
                top_oi.columns   = ["Strike", "Call OI", "Put OI", "Total OI"]
                st.dataframe(top_oi, hide_index=True, use_container_width=True)
            with tab_by_vol:
                top_vol = strike_df.nlargest(10, "total_volume")[
                    ["strike", "call_volume", "put_volume", "total_volume"]
                ]
                top_vol["strike"] = top_vol["strike"].apply(lambda x: f"${x:,.0f}")
                top_vol.columns   = ["Strike", "Call Vol", "Put Vol", "Total Vol"]
                st.dataframe(top_vol, hide_index=True, use_container_width=True)

    # ════════════════════════════════════════════════════════════════════
    # TAB 4 — IV Skew
    # ════════════════════════════════════════════════════════════════════
    with tab_iv:
        has_iv = (not strike_df.empty and
                  (strike_df["call_iv"].notna().any() or strike_df["put_iv"].notna().any()))
        if not has_iv:
            st.warning("Dados de IV indisponíveis.")
        else:
            st.plotly_chart(build_iv_chart(strike_df, spot, sym, exp), use_container_width=True)

    # ── Auto-refresh ──────────────────────────────────────────────────────────
    if st.session_state.auto_refresh:
        time.sleep(1)
        st.rerun()


if __name__ == "__main__":
    main()
