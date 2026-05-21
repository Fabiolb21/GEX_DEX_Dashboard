"""
Gamma Exposure (GEX) Calculator
Calculates and aggregates gamma exposure metrics for options chains.

Convencao de dealer (market maker hedging):
  - Dealers sao tipicamente SHORT opcoes (vendidos para o publico)
  - Call GEX = +gamma x OI x 100 x spot  (dealer short call -> short gamma)
  - Put GEX  = -gamma x OI x 100 x spot  (dealer short put  -> long gamma)
  - Net GEX  = Call GEX - Put GEX

  Quando Net GEX > 0: dealers long gamma -> vendem rally, compram queda (estabiliza)
  Quando Net GEX < 0: dealers short gamma -> amplificam movimentos

  Zero Gamma (Gamma Flip): strike onde Net GEX cruza zero, mais proximo do spot.
"""
import re
import time
import threading
from collections import deque, defaultdict
import pandas as pd


def parse_option_symbol(symbol):
    """
    Parse option symbol: .PREFIX + YYMMDD + C/P + STRIKE
    Ex: .SPXW251214C6000, .NDXP251214P20000, .SPY251219C590
    Returns dict ou None.
    """
    match = re.match(r"\.([A-Z]+)(\d{6})([CP])(\d+(?:\.\d+)?)", symbol)
    if match:
        return {
            "prefix":     match.group(1),
            "expiration": match.group(2),
            "type":       match.group(3),
            "strike":     float(match.group(4)),
        }
    return None


class GEXCalculator:
    """
    Calcula Gamma Exposure com a convencao correta do dealer.

    Formulas:
      call_gex(strike) = +gamma x OI x 100 x spot
      put_gex(strike)  = +gamma x OI x 100 x spot  (armazenado positivo)
      net_gex(strike)  =  call_gex - put_gex
         -> positivo: dealers long gamma (estabilizador)
         -> negativo: dealers short gamma (amplificador)

    Zero Gamma = cruzamento de zero do net_gex mais proximo do spot.
    """

    def __init__(self, max_history_seconds=3600, spot_price=6000):
        self.lock                = threading.Lock()
        self.spot_price          = float(spot_price)
        self.options             = {}
        self.time_series         = deque(maxlen=720)
        self.max_history_seconds = max_history_seconds
        self.last_snapshot_time  = 0

    def update_spot_price(self, price):
        with self.lock:
            self.spot_price = float(price)

    def update_gamma(self, symbol, gamma, open_interest):
        """Registra gamma e OI de uma opcao."""
        parsed = parse_option_symbol(symbol)
        if not parsed:
            return
        try:
            gamma         = float(gamma)
            open_interest = float(open_interest)
        except (ValueError, TypeError):
            return
        import math
        if math.isnan(gamma) or math.isnan(open_interest):
            return
        with self.lock:
            self.options[symbol] = {
                "gamma":  gamma,
                "oi":     open_interest,
                "type":   parsed["type"],
                "strike": parsed["strike"],
            }

    # ------------------------------------------------------------------
    # Helpers internos (chamados dentro do lock)
    # ------------------------------------------------------------------

    def _build_rows(self):
        """Agrega GEX por strike. Retorna dict {strike: {call_gex, put_gex}}."""
        rows = defaultdict(lambda: {"call_gex": 0.0, "put_gex": 0.0})
        for opt in self.options.values():
            gex = opt["gamma"] * opt["oi"] * 100 * self.spot_price
            if opt["type"] == "C":
                rows[opt["strike"]]["call_gex"] += gex
            else:
                rows[opt["strike"]]["put_gex"]  += gex
        return rows

    def _find_zero_gamma(self, rows, spot=None):
        """
        Interpolacao linear do cruzamento de zero do Net GEX
        mais proximo do spot. Retorna float ou None.
        """
        if len(rows) < 2:
            return None

        strikes  = sorted(rows.keys())
        net_gexs = [rows[s]["call_gex"] - rows[s]["put_gex"] for s in strikes]

        crossings = []
        for i in range(len(strikes) - 1):
            n1, n2 = net_gexs[i], net_gexs[i + 1]
            if n1 * n2 < 0:
                s1, s2 = strikes[i], strikes[i + 1]
                zero   = s1 + (s2 - s1) * (-n1) / (n2 - n1)
                crossings.append(zero)
            elif n1 == 0.0:
                crossings.append(float(strikes[i]))

        if not crossings:
            return None

        ref = float(spot) if spot is not None else self.spot_price
        return min(crossings, key=lambda z: abs(z - ref))

    # ------------------------------------------------------------------
    # API publica
    # ------------------------------------------------------------------

    def get_gex_by_strike(self):
        """DataFrame [strike, call_gex, put_gex, net_gex] ordenado por strike."""
        with self.lock:
            rows = self._build_rows()
            if not rows:
                return pd.DataFrame(columns=["strike", "call_gex", "put_gex", "net_gex"])
            data = [
                {
                    "strike":   s,
                    "call_gex": v["call_gex"],
                    "put_gex":  v["put_gex"],
                    "net_gex":  v["call_gex"] - v["put_gex"],
                }
                for s, v in rows.items()
            ]
            return pd.DataFrame(data).sort_values("strike").reset_index(drop=True)

    def get_zero_gamma_level(self):
        """Strike onde Net GEX cruza zero, mais proximo do spot."""
        with self.lock:
            return self._find_zero_gamma(self._build_rows())

    def get_total_gex_metrics(self):
        """Metricas agregadas: totais, max strike, zero gamma."""
        with self.lock:
            if not self.options:
                return {
                    "total_call_gex": 0.0, "total_put_gex": 0.0,
                    "net_gex": 0.0,        "max_gex_strike": None,
                    "max_gex_value": 0.0,  "zero_gamma": None,
                    "num_options": 0,
                }
            rows       = self._build_rows()
            total_call = sum(v["call_gex"] for v in rows.values())
            total_put  = sum(v["put_gex"]  for v in rows.values())
            max_strike = max(rows, key=lambda s: abs(rows[s]["call_gex"] - rows[s]["put_gex"]))
            max_value  = rows[max_strike]["call_gex"] - rows[max_strike]["put_gex"]
            return {
                "total_call_gex": total_call,
                "total_put_gex":  total_put,
                "net_gex":        total_call - total_put,
                "max_gex_strike": max_strike,
                "max_gex_value":  max_value,
                "zero_gamma":     self._find_zero_gamma(rows),
                "num_options":    len(self.options),
            }

    def add_time_series_snapshot(self):
        current_time = time.time()
        if current_time - self.last_snapshot_time < 5:
            return False
        with self.lock:
            m = self.get_total_gex_metrics()
            self.time_series.append({"timestamp": current_time, "total_gex": m["net_gex"]})
            self.last_snapshot_time = current_time
            cutoff = current_time - self.max_history_seconds
            while self.time_series and self.time_series[0]["timestamp"] < cutoff:
                self.time_series.popleft()
        return True

    def get_time_series(self):
        with self.lock:
            if not self.time_series:
                return pd.DataFrame(columns=["timestamp", "total_gex", "datetime"])
            df = pd.DataFrame(list(self.time_series))
            df["datetime"] = pd.to_datetime(df["timestamp"], unit="s")
            return df

    def get_summary_string(self):
        m  = self.get_total_gex_metrics()
        zg = f"${m['zero_gamma']:,.2f}" if m["zero_gamma"] else "N/A"
        return (
            f"GEX Summary:\n"
            f"  Call GEX  : ${m['total_call_gex']:,.0f}\n"
            f"  Put GEX   : ${m['total_put_gex']:,.0f}\n"
            f"  Net GEX   : ${m['net_gex']:,.0f}\n"
            f"  Zero Gamma: {zg}\n"
            f"  Max Strike: {m['max_gex_strike']}\n"
            f"  Options   : {m['num_options']}"
        )


if __name__ == "__main__":
    calc = GEXCalculator(spot_price=6000)

    # Simula cadeia simples para validar Zero Gamma
    # Strike 5900: call_gex < put_gex -> net < 0
    # Strike 6000: call_gex > put_gex -> net > 0
    # Zero Gamma deve estar entre 5900 e 6000, proximo do spot
    calc.update_gamma(".SPXW251219C5900", gamma=0.002, open_interest=20000)
    calc.update_gamma(".SPXW251219P5900", gamma=0.008, open_interest=20000)
    calc.update_gamma(".SPXW251219C6000", gamma=0.010, open_interest=15000)
    calc.update_gamma(".SPXW251219P6000", gamma=0.004, open_interest=15000)

    m = calc.get_total_gex_metrics()
    print(f"Net GEX   : ${m['net_gex']:,.0f}")
    print(f"Zero Gamma: {m['zero_gamma']}")
    df = calc.get_gex_by_strike()
    print(df.to_string(index=False))
