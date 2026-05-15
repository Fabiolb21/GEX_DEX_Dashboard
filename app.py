"""
GEX + DEX Dashboard
Gamma Exposure (GEX) e Delta Exposure (DEX) em tempo real
- Ticker digitado livremente
- Expirações e strikes buscados diretamente na cadeia de opcoes da Tastytrade
- Sem Put/Call Ratio
"""
import streamlit as st
import json
import time
import math
import requests
from datetime import datetime, timedelta
from websocket import create_connection
import pandas as pd
import plotly.graph_objects as go
from utils.auth import ensure_streamer_token
from utils.gex_calculator import GEXCalculator, parse_option_symbol

st.set_page_config(page_title="GEX + DEX Dashboard", page_icon="📊", layout="wide")

DXFEED_URL    = "wss://tasty-openapi-ws.dxfeed.com/realtime"
TASTY_API_URL = "https://api.tastytrade.com"


# ==============================================================================
# DEX Calculator
# ==============================================================================
class DEXCalculator:
    """
    Delta Exposure por strike.
        DEX  =  |delta|  x  OI  x  100  x  spot_price
    Call DEX  -> exposicao comprada (delta > 0)
    Put  DEX  -> exposicao vendida  (delta < 0, sinal convencional invertido)
    Net  DEX  =  Call DEX - Put DEX
    """

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
                                "call_oi":  0.0, "put_oi":  0.0}
            if opt_type == "C":
                rows[strike]["call_dex"] += dex
                rows[strike]["call_oi"]  += d["oi"]
            else:
                rows[strike]["put_dex"]  += dex
                rows[strike]["put_oi"]   += d["oi"]

        if not rows:
            return pd.DataFrame()

        return pd.DataFrame([
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

    def get_total_dex_metrics(self) -> dict:
        df = self.get_dex_by_strike()
        if df.empty:
            return {"total_call_dex": 0, "total_put_dex": 0, "net_dex": 0,
                    "num_options": 0, "max_dex_strike": None, "zero_delta": None}

        total_call = df["call_dex"].sum()
        total_put  = df["put_dex"].sum()
        df["abs_net"]  = df["net_dex"].abs()
        max_strike     = float(df.loc[df["abs_net"].idxmax(), "strike"])

        zero_delta = None
        for i in range(len(df) - 1):
            n1, n2 = df.iloc[i]["net_dex"], df.iloc[i + 1]["net_dex"]
            if n1 * n2 < 0:
                s1, s2     = df.iloc[i]["strike"], df.iloc[i + 1]["strike"]
                zero_delta = s1 + (s2 - s1) * (-n1) / (n2 - n1)
                break

        return {
            "total_call_dex": total_call,
            "total_put_dex":  total_put,
            "net_dex":        total_call - total_put,
            "num_options":    len(self._data),
            "max_dex_strike": max_strike,
            "zero_delta":     zero_delta,
        }


# ==============================================================================
# Tastytrade REST — cadeia de opcoes
# ==============================================================================


@st.cache_data(ttl=1200, show_spinner=False)
def _get_tasty_session_token() -> str:
    """
    Faz login na API Tastytrade via POST /sessions e retorna o session-token.
    A API usa o token diretamente no header Authorization (sem prefixo Bearer).
    Credenciais lidas dos st.secrets (Streamlit Cloud) ou variáveis de ambiente.
    """
    import os

    # Tenta st.secrets primeiro (Streamlit Cloud), depois env vars (local)
    def _get(key: str) -> str:
        try:
            return st.secrets[key]
        except Exception:
            pass
        val = os.environ.get(key, "")
        if not val:
            raise ValueError(
                f"Credencial '{key}' nao encontrada em st.secrets nem em variavel de ambiente. "
                "Configure CLIENT_ID, CLIENT_SECRET e REFRESH_TOKEN."
            )
        return val

    client_id     = _get("CLIENT_ID")
    client_secret = _get("CLIENT_SECRET")
    refresh_token = _get("REFRESH_TOKEN")

    # 1. Troca refresh_token por access_token via OAuth
    oauth_resp = requests.post(
        f"{TASTY_API_URL}/oauth/token",
        json={
            "grant_type":    "refresh_token",
            "client_id":     client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        },
        headers={"Content-Type": "application/json"},
        timeout=15,
    )
    if oauth_resp.status_code != 200:
        raise RuntimeError(
            f"OAuth falhou ({oauth_resp.status_code}): {oauth_resp.text[:200]}"
        )
    access_token = oauth_resp.json().get("access_token", "")
    if not access_token:
        raise RuntimeError("access_token vazio na resposta OAuth")

    return access_token


@st.cache_data(ttl=300, show_spinner=False)
def fetch_option_chain(symbol: str) -> dict:
    """
    Busca a cadeia completa de opcoes do ticker via API Tastytrade.
    Retorna dict com:
      - expirations        : lista de "YYYY-MM-DD"
      - strikes_by_exp     : { "YYYY-MM-DD": [float, ...] }
      - option_prefix      : prefixo dxFeed  (ex: "SPXW", "SPY")
      - is_index           : bool
    """
    try:
        access_token = _get_tasty_session_token()
        # A API Tastytrade aceita o access_token diretamente — sem prefixo "Bearer"
        headers = {"Authorization": access_token}

        # Endpoint nested retorna estrutura agrupada por expiracao
        url  = f"{TASTY_API_URL}/option-chains/{symbol.upper()}/nested"
        resp = requests.get(url, headers=headers, timeout=15)

        if resp.status_code == 404:
            url  = f"{TASTY_API_URL}/option-chains/{symbol.upper()}"
            resp = requests.get(url, headers=headers, timeout=15)

        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code} — ticker nao encontrado ou sem opcoes"}

        payload = resp.json().get("data", {})
        items   = payload.get("items", []) if isinstance(payload, dict) else []

        if not items:
            return {"error": "Cadeia vazia — verifique se o ticker possui opcoes listadas"}

        expirations: list    = []
        strikes_by_exp: dict = {}
        option_prefix        = symbol.upper()

        for chain in items:
            # Prefixo do root symbol (ex: SPXW para SPX)
            root = (chain.get("option-root-symbol")
                    or chain.get("underlying-symbol")
                    or symbol.upper())
            if root:
                option_prefix = root

            exp_date = (chain.get("expiration-date")
                        or chain.get("expiration")
                        or "")
            exp_str  = str(exp_date)[:10]
            if not exp_str or len(exp_str) < 8:
                continue

            if exp_str not in expirations:
                expirations.append(exp_str)

            # Strikes podem estar em "strikes" ou nas opcoes individuais
            raw_strikes = chain.get("strikes", [])
            values = []
            for s in raw_strikes:
                val = s.get("strike-price") if isinstance(s, dict) else s
                try:
                    values.append(float(val))
                except (ValueError, TypeError):
                    pass

            if exp_str in strikes_by_exp:
                strikes_by_exp[exp_str] = sorted(
                    set(strikes_by_exp[exp_str]) | set(values)
                )
            else:
                strikes_by_exp[exp_str] = sorted(set(values))

        if not expirations:
            return {"error": "Nenhuma expiracao encontrada — tente outro ticker"}

        expirations.sort()
        is_index = symbol.upper() in {
            "SPX", "NDX", "RUT", "DJX", "VIX", "SPXW", "NDXP", "RUTW"
        }

        return {
            "expirations":    expirations,
            "strikes_by_exp": strikes_by_exp,
            "option_prefix":  option_prefix,
            "is_index":       is_index,
        }

    except requests.exceptions.RequestException as e:
        return {"error": f"Erro de rede: {e}"}
    except Exception as e:
        return {"error": f"Erro inesperado: {e}"}


def exp_to_dxfeed(exp_date: str) -> str:
    """Converte 'YYYY-MM-DD' para 'YYMMDD'."""
    return datetime.strptime(exp_date, "%Y-%m-%d").strftime("%y%m%d")


def exp_display(exp_date: str) -> str:
    """Converte 'YYYY-MM-DD' para 'Mon DD, YYYY'."""
    try:
        return datetime.strptime(exp_date, "%Y-%m-%d").strftime("%b %d, %Y")
    except Exception:
        return exp_date


def build_option_symbols_from_chain(option_prefix: str,
                                    expiration_dxfeed: str,
                                    strikes: list) -> list:
    """Gera simbolos dxFeed para todos os strikes (call + put)."""
    symbols = []
    for strike in strikes:
        strike_str = str(int(strike)) if strike == int(strike) else str(strike)
        symbols.append(f".{option_prefix}{expiration_dxfeed}C{strike_str}")
        symbols.append(f".{option_prefix}{expiration_dxfeed}P{strike_str}")
    return symbols


# ==============================================================================
# WebSocket helpers
# ==============================================================================

def connect_websocket(token: str):
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


def get_underlying_price(ws, symbol: str):
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
                for item in msg.get("data", []):
                    if item.get("eventSymbol") == symbol:
                        if item.get("eventType") == "Trade" and item.get("price"):
                            trade_price = float(item["price"])
                        elif item.get("eventType") == "Quote":
                            try:
                                bid = float(item.get("bidPrice") or 0)
                                ask = float(item.get("askPrice") or 0)
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


def fetch_option_data(ws, symbols: list, wait_seconds: int = 20) -> dict:
    """
    Coleta Greeks (gamma+delta+IV), Summary (OI) e Trade (volume).
    Envia subscriptions em lotes de 200 para respeitar limites do dxFeed.
    """
    BATCH = 200
    for i in range(0, len(symbols), BATCH):
        batch = symbols[i: i + BATCH]
        subs  = []
        for sym in batch:
            subs.extend([
                {"symbol": sym, "type": "Greeks"},
                {"symbol": sym, "type": "Summary"},
                {"symbol": sym, "type": "Trade"},
            ])
        ws.send(json.dumps({"type": "FEED_SUBSCRIPTION", "channel": 1, "add": subs}))

    data: dict = {}
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


# ==============================================================================
# Agregadores
# ==============================================================================

def _safe_float(val, default=0.0) -> float:
    try:
        v = float(val or default)
        return default if math.isnan(v) else v
    except (ValueError, TypeError):
        return default


def aggregate_by_strike(option_data: dict) -> pd.DataFrame:
    rows: dict = {}
    for symbol, d in option_data.items():
        parsed = parse_option_symbol(symbol)
        if not parsed:
            continue
        strike   = parsed["strike"]
        opt_type = parsed["type"]

        if strike not in rows:
            rows[strike] = {"call_oi": 0.0, "put_oi": 0.0,
                            "call_volume": 0.0, "put_volume": 0.0,
                            "call_iv": None, "put_iv": None}

        oi  = _safe_float(d.get("oi"))
        vol = _safe_float(d.get("volume"))
        iv  = d.get("iv")

        if opt_type == "C":
            rows[strike]["call_oi"]     += oi
            rows[strike]["call_volume"] += vol
            if iv is not None:
                try:
                    iv_f = float(iv)
                    if not math.isnan(iv_f):
                        rows[strike]["call_iv"] = iv_f
                except (ValueError, TypeError):
                    pass
        else:
            rows[strike]["put_oi"]      += oi
            rows[strike]["put_volume"]  += vol
            if iv is not None:
                try:
                    iv_f = float(iv)
                    if not math.isnan(iv_f):
                        rows[strike]["put_iv"] = iv_f
                except (ValueError, TypeError):
                    pass

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame([
        {
            "strike":       s,
            "call_oi":      v["call_oi"],
            "put_oi":       v["put_oi"],
            "call_volume":  v["call_volume"],
            "put_volume":   v["put_volume"],
            "call_iv":      v["call_iv"],
            "put_iv":       v["put_iv"],
            "total_oi":     v["call_oi"]     + v["put_oi"],
            "total_volume": v["call_volume"] + v["put_volume"],
        }
        for s, v in rows.items()
    ]).sort_values("strike").reset_index(drop=True)


# ==============================================================================
# Chart builders
# ==============================================================================

def build_exposure_chart(df, col_call, col_put, col_net,
                         spot, zero_level, symbol, exp_label,
                         metric_label, chart_type):
    fig = go.Figure()
    if chart_type == "Calls vs Puts":
        fig.add_trace(go.Bar(x=df["strike"], y=df[col_call],
                             name=f"Call {metric_label}", marker_color="green"))
        fig.add_trace(go.Bar(x=df["strike"], y=-df[col_put],
                             name=f"Put {metric_label}", marker_color="red"))
        barmode = "relative"
    else:
        colors = ["green" if x >= 0 else "red" for x in df[col_net]]
        fig.add_trace(go.Bar(x=df["strike"], y=df[col_net],
                             name=f"Net {metric_label}", marker_color=colors))
        fig.add_hline(y=0, line_dash="dot", line_color="gray", line_width=1)
        barmode = "group"

    fig.add_vline(x=spot, line_dash="dash", line_color="orange", line_width=2,
                  annotation_text=f"${spot:,.2f}", annotation_position="top")
    if zero_level:
        fig.add_vline(x=zero_level, line_dash="dot", line_color="purple", line_width=2,
                      annotation_text=f"Zero {metric_label}: ${zero_level:,.2f}",
                      annotation_position="bottom")
    fig.update_layout(
        title=f"{symbol} {metric_label} by Strike — Exp: {exp_label}",
        xaxis_title="Strike", yaxis_title=f"{metric_label} ($)",
        barmode=barmode, template="plotly_white", height=500
    )
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
    fig.update_layout(title=f"{symbol} IV Skew — Exp: {exp_label}",
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
    fig.update_layout(title=f"Volume by Strike — {view}", xaxis_title="Strike",
                      yaxis_title="Volume", barmode=barmode,
                      template="plotly_white", height=400)
    return fig


def _fmt_table(df_in, cols_map: dict) -> pd.DataFrame:
    out = df_in[list(cols_map.keys())].copy()
    for col in cols_map:
        if col == "strike":
            out[col] = out[col].apply(lambda x: f"${x:,.2f}")
        else:
            out[col] = out[col].apply(lambda x: f"${x:,.0f}")
    out.columns = list(cols_map.values())
    return out


# ==============================================================================
# Main
# ==============================================================================

def main():
    st.title("📊 GEX + DEX Dashboard")
    st.caption("Gamma Exposure (GEX) e Delta Exposure (DEX) — cadeia completa de strikes")

    # Session state defaults
    for k, v in {
        "data_fetched":          False,
        "gex_calculator":        None,
        "dex_calculator":        None,
        "underlying_price":      None,
        "option_data":           {},
        "auto_refresh":          False,
        "volume_view":           "Calls vs Puts",
        "symbol":                "",
        "expiration":            "",
        "chain":                 None,
        "chain_symbol":          "",
        # Modo acumulado (todos os vencimentos)
        "acum_mode":             False,
        "acum_gex_calculator":   None,
        "acum_dex_calculator":   None,
        "acum_option_data":      {},
        "acum_expirations_used": [],
        "acum_fetched":          False,
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # ==========================================================================
    # Sidebar
    # ==========================================================================
    with st.sidebar:
        st.header("Configuracao")

        # ── 1. Ticker ──────────────────────────────────────────────────────────
        st.subheader("Ticker")
        ticker_input = st.text_input(
            "Digite o simbolo",
            value=st.session_state.symbol,
            placeholder="Ex: SPX, AAPL, EWZ, NVDA...",
            help="Qualquer ativo com opcoes na Tastytrade",
        ).upper().strip()

        if st.button("Buscar cadeia de opcoes", use_container_width=True):
            if ticker_input:
                st.session_state.symbol       = ticker_input
                st.session_state.chain_symbol = ticker_input
                st.session_state.chain        = None
                st.session_state.data_fetched = False
                # Limpa cache do Streamlit para este ticker
                fetch_option_chain.clear()
                with st.spinner(f"Buscando cadeia de {ticker_input}..."):
                    chain = fetch_option_chain(ticker_input)
                if "error" in chain:
                    st.error(f"Erro: {chain['error']}")
                else:
                    st.session_state.chain = chain
                    n_exp = len(chain["expirations"])
                    all_strikes = sum(len(v) for v in chain["strikes_by_exp"].values())
                    avg = all_strikes // n_exp if n_exp else 0
                    st.success(
                        f"{ticker_input}: {n_exp} expirações, "
                        f"~{avg} strikes por expiracao"
                    )
            else:
                st.warning("Digite um ticker antes de buscar.")

        chain = st.session_state.chain

        # ── 2. Expiracao ───────────────────────────────────────────────────────
        if chain:
            st.subheader("Expiracao")
            exp_options = chain["expirations"]
            today_str   = datetime.now().strftime("%Y-%m-%d")

            default_idx = 0
            if today_str in exp_options:
                default_idx = exp_options.index(today_str)

            selected_exp = st.selectbox(
                "Data de expiracao",
                exp_options,
                index=default_idx,
                format_func=lambda d: (
                    f"[0DTE] {exp_display(d)}" if d == today_str
                    else exp_display(d)
                ),
            )
            st.session_state.expiration = selected_exp

            strikes_for_exp = chain["strikes_by_exp"].get(selected_exp, [])
            n_strikes = len(strikes_for_exp)
            st.caption(f"{n_strikes} strikes disponiveis nesta expiracao")

            # ── 3. Filtro de strikes ───────────────────────────────────────────
            st.subheader("Strikes")
            filter_mode = st.radio(
                "Incluir",
                ["Todos os strikes", "Apenas ATM +/- N"],
                index=0,
                help="Todos: cadeia completa. ATM +/- N: filtra em torno do preco atual.",
            )
            atm_range = None
            if filter_mode == "Apenas ATM +/- N":
                atm_range = st.number_input(
                    "Strikes acima/abaixo do ATM",
                    min_value=5, max_value=500, value=40, step=5,
                )

            # ── 4. Coleta ──────────────────────────────────────────────────────
            st.subheader("Coleta de Dados")
            wait_seconds = st.slider(
                "Duracao da coleta (seg)",
                min_value=10, max_value=90, value=25, step=5,
                help="Cadeias grandes (500+ strikes) precisam de mais tempo.",
            )
            auto_refresh = st.checkbox("Auto-refresh", value=st.session_state.auto_refresh)
            st.session_state.auto_refresh = auto_refresh

            # ── Modo de coleta ────────────────────────────────────────────
            st.subheader("Modo de Coleta")
            acum_mode = st.toggle(
                "Acumulado (todos os vencimentos)",
                value=st.session_state.acum_mode,
                help="Coleta e soma GEX + DEX de TODOS os vencimentos disponíveis na cadeia.",
            )
            st.session_state.acum_mode = acum_mode

            if acum_mode:
                # Seletor de quantos vencimentos incluir
                max_exps = len(exp_options)
                n_exps_to_use = st.number_input(
                    "Quantos vencimentos incluir",
                    min_value=1, max_value=max_exps, value=min(12, max_exps), step=1,
                    help="Ordena do mais próximo ao mais distante.",
                )
                exps_to_use = exp_options[:n_exps_to_use]
                st.caption(
                    f"Vencimentos: {exp_display(exps_to_use[0])} "
                    f"→ {exp_display(exps_to_use[-1])}"
                )

            st.divider()
            fetch_disabled = (n_strikes == 0)
            fetch_btn = st.button(
                "Buscar Dados GEX + DEX" if not acum_mode else "Buscar Acumulado (todos vencimentos)",
                type="primary",
                use_container_width=True,
                disabled=fetch_disabled,
            )

            if fetch_btn:
                option_prefix = chain["option_prefix"]

                with st.spinner("Conectando ao dxFeed..."):
                    try:
                        token = ensure_streamer_token()
                        ws    = connect_websocket(token)

                        st.info(f"Buscando preco de {st.session_state.symbol}...")
                        price = get_underlying_price(ws, st.session_state.symbol)
                        if not price:
                            price = (strikes_for_exp[len(strikes_for_exp) // 2]
                                     if strikes_for_exp else 100.0)
                            st.warning(f"Preco nao obtido — usando strike central: ${price:,.2f}")
                        st.session_state.underlying_price = price
                        st.success(f"{st.session_state.symbol}: ${price:,.2f}")

                        if not acum_mode:
                            # ── Modo normal: um vencimento ────────────────────
                            expiration_dxfeed = exp_to_dxfeed(selected_exp)
                            if atm_range is not None and strikes_for_exp:
                                diffs   = [abs(s - price) for s in strikes_for_exp]
                                atm_idx = diffs.index(min(diffs))
                                lo      = max(0, atm_idx - atm_range)
                                hi      = min(len(strikes_for_exp), atm_idx + atm_range + 1)
                                strikes = strikes_for_exp[lo:hi]
                            else:
                                strikes = strikes_for_exp

                            options = build_option_symbols_from_chain(
                                option_prefix, expiration_dxfeed, strikes
                            )
                            st.info(
                                f"Coletando {len(options)} opcoes "
                                f"({len(strikes)} strikes x 2) por {wait_seconds}s..."
                            )
                            option_data = fetch_option_data(ws, options, wait_seconds)
                            ws.close()

                            gex_calc = GEXCalculator(spot_price=price)
                            dex_calc = DEXCalculator(spot_price=price)
                            for sym_str, d in option_data.items():
                                g     = d.get("gamma")
                                delta = d.get("delta")
                                oi    = d.get("oi")
                                if g     is not None and oi is not None:
                                    gex_calc.update_gamma(sym_str, g, oi)
                                if delta is not None and oi is not None:
                                    dex_calc.update_delta(sym_str, delta, oi)

                            st.session_state.gex_calculator = gex_calc
                            st.session_state.dex_calculator = dex_calc
                            st.session_state.option_data    = option_data
                            st.session_state.data_fetched   = True
                            st.session_state.acum_fetched   = False
                            st.success("Dados coletados com sucesso!")

                        else:
                            # ── Modo acumulado: todos os vencimentos ──────────
                            all_option_data: dict = {}
                            progress_bar = st.progress(0, text="Iniciando coleta acumulada...")
                            total_exps   = len(exps_to_use)

                            for idx, exp_date in enumerate(exps_to_use):
                                exp_dx  = exp_to_dxfeed(exp_date)
                                s_list  = chain["strikes_by_exp"].get(exp_date, [])
                                if not s_list:
                                    continue

                                if atm_range is not None:
                                    diffs   = [abs(s - price) for s in s_list]
                                    atm_idx = diffs.index(min(diffs))
                                    lo      = max(0, atm_idx - atm_range)
                                    hi      = min(len(s_list), atm_idx + atm_range + 1)
                                    s_list  = s_list[lo:hi]

                                syms = build_option_symbols_from_chain(
                                    option_prefix, exp_dx, s_list
                                )
                                pct  = int((idx / total_exps) * 100)
                                progress_bar.progress(
                                    pct,
                                    text=f"[{idx+1}/{total_exps}] {exp_display(exp_date)} "
                                         f"— {len(syms)} opcoes..."
                                )
                                # Cada vencimento recebe wait_seconds / total_exps
                                # mínimo de 5s para não perder dados
                                exp_wait = max(5, wait_seconds // total_exps)
                                batch_data = fetch_option_data(ws, syms, exp_wait)
                                all_option_data.update(batch_data)

                            ws.close()
                            progress_bar.progress(100, text="Calculando GEX + DEX acumulado...")

                            acum_gex = GEXCalculator(spot_price=price)
                            acum_dex = DEXCalculator(spot_price=price)
                            for sym_str, d in all_option_data.items():
                                g     = d.get("gamma")
                                delta = d.get("delta")
                                oi    = d.get("oi")
                                if g     is not None and oi is not None:
                                    acum_gex.update_gamma(sym_str, g, oi)
                                if delta is not None and oi is not None:
                                    acum_dex.update_delta(sym_str, delta, oi)

                            st.session_state.acum_gex_calculator   = acum_gex
                            st.session_state.acum_dex_calculator   = acum_dex
                            st.session_state.acum_option_data      = all_option_data
                            st.session_state.acum_expirations_used = exps_to_use
                            st.session_state.acum_fetched          = True
                            # Também popula o vencimento individual com o mais próximo
                            st.session_state.gex_calculator = acum_gex
                            st.session_state.dex_calculator = acum_dex
                            st.session_state.option_data    = all_option_data
                            st.session_state.data_fetched   = True
                            progress_bar.empty()
                            st.success(
                                f"Acumulado calculado: {len(exps_to_use)} vencimentos, "
                                f"{len(all_option_data)} opcoes rastreadas."
                            )

                    except Exception as e:
                        st.error(f"Erro: {e}")
                        st.session_state.data_fetched = False
        else:
            st.info("Digite um ticker e clique em Buscar cadeia de opcoes.")

    # ==========================================================================
    # Tela inicial
    # ==========================================================================
    if not st.session_state.data_fetched:
        if not chain:
            st.info("Digite um ticker na barra lateral e clique em Buscar cadeia de opcoes.")
            st.markdown("""
### Como usar
1. **Digite o ticker** — qualquer ativo com opcoes na Tastytrade (ex: `SPX`, `AAPL`, `EWZ`)
2. **Buscar cadeia** — carrega todas as expirações e **todos os strikes** disponíveis
3. **Selecione a expiração** — 0DTE destacado quando disponível
4. **Filtro de strikes** — use *Todos* para a cadeia completa ou *ATM +/- N* para filtrar
5. **Buscar Dados GEX + DEX** — conecta ao dxFeed e calcula em tempo real

### Calculos
| Metrica | Formula | Interpretacao |
|---------|---------|---------------|
| **GEX** | gamma × OI × 100 × spot | Velocidade de rehedge do dealer |
| **DEX** | delta × OI × 100 × spot | Posicao direcional liquida do dealer |
| **Zero Gamma** | Net GEX = 0 | Flip de comportamento (GEX) |
| **Zero Delta** | Net DEX = 0 | Flip de posicao direcional (DEX) |
            """)
        else:
            st.info(
                f"Cadeia de **{st.session_state.chain_symbol}** carregada. "
                "Selecione a expiracao e clique em Buscar Dados GEX + DEX."
            )
        return

    # ==========================================================================
    # Dashboard
    # ==========================================================================
    gex_calc  = st.session_state.gex_calculator
    dex_calc  = st.session_state.dex_calculator
    gex_m     = gex_calc.get_total_gex_metrics()
    dex_m     = dex_calc.get_total_dex_metrics()
    strike_df = aggregate_by_strike(st.session_state.option_data)
    spot      = st.session_state.underlying_price
    sym       = st.session_state.symbol
    exp_lbl   = exp_display(st.session_state.expiration)

    # Header metrics
    is_acum   = st.session_state.acum_fetched
    acum_exps = st.session_state.acum_expirations_used

    if is_acum:
        st.info(
            f"**Modo Acumulado** — {len(acum_exps)} vencimentos somados: "
            f"{exp_display(acum_exps[0])} → {exp_display(acum_exps[-1])}"
        )
    else:
        st.info(f"**Vencimento:** {exp_lbl}")

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        st.metric(f"{sym} Price", f"${spot:,.2f}")
    with c2:
        st.metric("Opcoes Rastreadas", f"{gex_m['num_options']:,}")
    with c3:
        st.metric("Net GEX", f"${gex_m['net_gex']:,.0f}",
                  help="Positivo: dealers long gamma (mercado estabiliza). "
                       "Negativo: dealers short gamma (movimentos se amplificam).")
    with c4:
        zg_val = gex_m.get("zero_gamma")
        st.metric("Zero Gamma",
                  f"${zg_val:,.2f}" if zg_val else "N/A",
                  help="Strike onde Net GEX = 0 (Gamma Flip).")
    with c5:
        st.metric("Net DEX", f"${dex_m['net_dex']:,.0f}",
                  help="Positivo: dealers comprados. Negativo: dealers vendidos.")
    with c6:
        zd_val = dex_m.get("zero_delta")
        st.metric("Zero Delta",
                  f"${zd_val:,.2f}" if zd_val else "N/A",
                  help="Strike onde Net DEX = 0 (Delta Flip).")

    st.divider()

    acum_suffix = " — Acumulado" if is_acum else ""
    tab_gex, tab_dex, tab_oi, tab_iv = st.tabs([
        f"Gamma Exposure (GEX){acum_suffix}",
        f"Delta Exposure (DEX){acum_suffix}",
        "Volume & Open Interest",
        "IV Skew",
    ])

    # ==========================================================================
    # TAB GEX
    # ==========================================================================
    with tab_gex:
        gex_df = gex_calc.get_gex_by_strike()
        col_chart, col_stats = st.columns([3, 1])

        with col_chart:
            if gex_df.empty:
                st.warning("Nenhum dado de GEX disponivel.")
            else:
                ct_gex = st.radio("Visualizacao GEX", ["Calls vs Puts", "Net GEX"],
                                  horizontal=True, key="gex_ct")
                gex_exp_label = (
                    f"{len(acum_exps)} vencimentos acumulados" if is_acum else exp_lbl
                )
                st.plotly_chart(
                    build_exposure_chart(gex_df, "call_gex", "put_gex", "net_gex",
                                         spot, gex_m.get("zero_gamma"), sym,
                                         gex_exp_label, "GEX", ct_gex),
                    use_container_width=True,
                )

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
                st.metric("Zero Gamma (Flip)", f"${gex_m['zero_gamma']:,.2f}",
                          help="Acima: dealers long gamma. Abaixo: dealers short gamma.")

        if not gex_df.empty:
            st.subheader("Top Strikes — GEX")
            ta, tb = st.tabs(["Por Call GEX", "Por Put GEX"])
            cols_gex = {"strike": "Strike", "call_gex": "Call GEX",
                        "put_gex": "Put GEX", "net_gex": "Net GEX"}
            with ta:
                st.dataframe(_fmt_table(gex_df.nlargest(15, "call_gex"), cols_gex),
                             hide_index=True, use_container_width=True)
            with tb:
                st.dataframe(_fmt_table(gex_df.nlargest(15, "put_gex"), cols_gex),
                             hide_index=True, use_container_width=True)

    # ==========================================================================
    # TAB DEX
    # ==========================================================================
    with tab_dex:
        dex_df = dex_calc.get_dex_by_strike()
        col_chart, col_stats = st.columns([3, 1])

        with col_chart:
            if dex_df.empty:
                st.warning("Nenhum dado de DEX disponivel.")
            else:
                ct_dex = st.radio("Visualizacao DEX", ["Calls vs Puts", "Net DEX"],
                                  horizontal=True, key="dex_ct")
                dex_exp_label = (
                    f"{len(acum_exps)} vencimentos acumulados" if is_acum else exp_lbl
                )
                st.plotly_chart(
                    build_exposure_chart(dex_df, "call_dex", "put_dex", "net_dex",
                                         spot, dex_m.get("zero_delta"), sym,
                                         dex_exp_label, "DEX", ct_dex),
                    use_container_width=True,
                )

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
                st.metric("Zero Delta (Flip)", f"${dex_m['zero_delta']:,.2f}",
                          help="Acima: dealers comprados. Abaixo: dealers vendidos.")

        if not dex_df.empty:
            st.subheader("Top Strikes — DEX")
            dex_copy = dex_df.copy()
            dex_copy["abs_net_dex"] = dex_copy["net_dex"].abs()
            ta, tb, tc = st.tabs(["Top Call DEX", "Top Put DEX", "Top |Net DEX|"])
            cols_dex = {"strike": "Strike", "call_dex": "Call DEX",
                        "put_dex": "Put DEX", "net_dex": "Net DEX"}
            with ta:
                st.dataframe(_fmt_table(dex_copy.nlargest(15, "call_dex"), cols_dex),
                             hide_index=True, use_container_width=True)
            with tb:
                st.dataframe(_fmt_table(dex_copy.nlargest(15, "put_dex"), cols_dex),
                             hide_index=True, use_container_width=True)
            with tc:
                st.dataframe(_fmt_table(dex_copy.nlargest(15, "abs_net_dex"), cols_dex),
                             hide_index=True, use_container_width=True)

        # Breakdown por vencimento no modo acumulado
        if is_acum and acum_exps:
            with st.expander(f"Breakdown por vencimento ({len(acum_exps)} expirações)", expanded=False):
                breakdown_rows = []
                for exp_date in acum_exps:
                    exp_dx  = exp_to_dxfeed(exp_date)
                    # filtra opções deste vencimento a partir do option_data acumulado
                    exp_data = {
                        k: v for k, v in st.session_state.acum_option_data.items()
                        if exp_dx in k
                    }
                    if not exp_data:
                        continue
                    tmp_gex = GEXCalculator(spot_price=spot)
                    tmp_dex = DEXCalculator(spot_price=spot)
                    for sym_str, d in exp_data.items():
                        g     = d.get("gamma")
                        delta = d.get("delta")
                        oi    = d.get("oi")
                        if g     is not None and oi is not None:
                            tmp_gex.update_gamma(sym_str, g, oi)
                        if delta is not None and oi is not None:
                            tmp_dex.update_delta(sym_str, delta, oi)
                    gm = tmp_gex.get_total_gex_metrics()
                    dm = tmp_dex.get_total_dex_metrics()
                    breakdown_rows.append({
                        "Vencimento": exp_display(exp_date),
                        "Opcoes":     gm["num_options"],
                        "Call GEX":   f"${gm['total_call_gex']:,.0f}",
                        "Put GEX":    f"${gm['total_put_gex']:,.0f}",
                        "Net GEX":    f"${gm['net_gex']:,.0f}",
                        "Call DEX":   f"${dm['total_call_dex']:,.0f}",
                        "Put DEX":    f"${dm['total_put_dex']:,.0f}",
                        "Net DEX":    f"${dm['net_dex']:,.0f}",
                    })
                if breakdown_rows:
                    st.dataframe(
                        pd.DataFrame(breakdown_rows),
                        hide_index=True,
                        use_container_width=True,
                    )

        with st.expander("Como interpretar o DEX"):
            st.markdown("""
**Delta Exposure (DEX)** mede a posicao direcional liquida dos dealers no underlying.

| | Calculo |
|---|---|
| **DEX por opcao** | `|delta| x OI x 100 x spot` |
| **Call DEX** | Soma das calls — exposicao comprada |
| **Put DEX** | Soma das puts — exposicao vendida |
| **Net DEX** | `Call DEX - Put DEX` |

**Zero Delta (Flip Level)**
- Spot **acima** do Zero Delta: dealers comprados, vendem rallies / compram quedas — mercado estabiliza
- Spot **abaixo** do Zero Delta: dealers vendidos, amplificam movimentos

**GEX vs DEX**

| | GEX | DEX |
|---|---|---|
| Greek | gamma | delta |
| Mede | Velocidade de rehedge | Tamanho da posicao direcional |
| Flip | Zero Gamma | Zero Delta |
            """)

    # ==========================================================================
    # TAB OI & Volume
    # ==========================================================================
    with tab_oi:
        if strike_df.empty:
            st.warning("Dados de OI/Volume indisponiveis.")
        else:
            c3, c4 = st.columns(2)
            with c3:
                st.plotly_chart(build_oi_chart(strike_df, spot),
                                use_container_width=True)
            with c4:
                vol_view = st.radio(
                    "Volume View", ["Calls vs Puts", "Total Volume"],
                    index=["Calls vs Puts", "Total Volume"].index(
                        st.session_state.volume_view),
                    key="vol_view_radio", horizontal=True,
                )
                st.session_state.volume_view = vol_view
                st.plotly_chart(build_volume_chart(strike_df, spot, vol_view),
                                use_container_width=True)

            st.subheader("Top Strikes")
            t_oi, t_vol = st.tabs(["Por OI Total", "Por Volume Total"])
            with t_oi:
                top = strike_df.nlargest(15, "total_oi")[
                    ["strike", "call_oi", "put_oi", "total_oi"]]
                top["strike"] = top["strike"].apply(lambda x: f"${x:,.2f}")
                top.columns   = ["Strike", "Call OI", "Put OI", "Total OI"]
                st.dataframe(top, hide_index=True, use_container_width=True)
            with t_vol:
                top = strike_df.nlargest(15, "total_volume")[
                    ["strike", "call_volume", "put_volume", "total_volume"]]
                top["strike"] = top["strike"].apply(lambda x: f"${x:,.2f}")
                top.columns   = ["Strike", "Call Vol", "Put Vol", "Total Vol"]
                st.dataframe(top, hide_index=True, use_container_width=True)

    # ==========================================================================
    # TAB IV Skew
    # ==========================================================================
    with tab_iv:
        has_iv = (not strike_df.empty and
                  (strike_df["call_iv"].notna().any() or
                   strike_df["put_iv"].notna().any()))
        if not has_iv:
            st.warning("Dados de IV indisponiveis.")
        else:
            st.plotly_chart(build_iv_chart(strike_df, spot, sym, exp_lbl),
                            use_container_width=True)

    # Auto-refresh
    if st.session_state.auto_refresh:
        time.sleep(1)
        st.rerun()


if __name__ == "__main__":
    main()
