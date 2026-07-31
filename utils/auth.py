"""
Authentication utilities for Tastytrade API
Handles OAuth token exchange and dxFeed streamer token retrieval
"""
import os
import json
import time
import requests
from dotenv import load_dotenv

# Token file paths
TOKEN_FILE         = "tasty_token.json"
STREAMER_TOKEN_FILE = "streamer_token.json"

# Load environment variables
load_dotenv()

# --- CONFIGURACAO DE AMBIENTE ---
# Produção: api.tastytrade.com  (suas credenciais normais do app)
# Sandbox : api.cert.tastyworks.com  (requer credenciais separadas de sandbox)
IS_SANDBOX = False                          # <-- PRODUCAO
BASE_URL   = (
    "https://api.cert.tastyworks.com"
    if IS_SANDBOX else
    "https://api.tastytrade.com"            # endpoint correto de producao
)


def load_credentials_from_env():
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "CLIENT_ID" in st.secrets:
            return {
                "client_id":     st.secrets["CLIENT_ID"],
                "client_secret": st.secrets["CLIENT_SECRET"],
                "refresh_token": st.secrets["REFRESH_TOKEN"],
            }
    except Exception:
        pass

    return {
        "client_id":     os.getenv("CLIENT_ID"),
        "client_secret": os.getenv("CLIENT_SECRET"),
        "refresh_token": os.getenv("REFRESH_TOKEN"),
    }


def get_access_token(force_refresh=False):
    # Tenta usar token em cache
    if not force_refresh and os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r") as f:
                data = json.load(f)
                if data.get("expires_at", 0) > time.time() + 60:
                    return data["access_token"]
        except Exception:
            pass

    creds = load_credentials_from_env()

    if not creds["client_id"] or not creds["refresh_token"]:
        raise Exception(
            "Credenciais ausentes. Verifique CLIENT_ID, CLIENT_SECRET e "
            "REFRESH_TOKEN no arquivo .env ou nos secrets do Streamlit."
        )

    headers = {
        "Accept":       "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent":   "GEX-App/1.0",
    }
    payload = {
        "grant_type":    "refresh_token",
        "refresh_token": creds["refresh_token"],
        "client_id":     creds["client_id"],
        "client_secret": creds["client_secret"],
    }

    url = f"{BASE_URL}/oauth/token"
    try:
        resp = requests.post(url, data=payload, headers=headers, timeout=20)

        # Diagnostico detalhado em caso de erro
        if resp.status_code != 200:
            raise Exception(
                f"HTTP {resp.status_code} em {url}\n"
                f"Resposta: {resp.text[:400]}"
            )

        token_data = resp.json()
        token_data["expires_at"] = time.time() + token_data.get("expires_in", 900)

        with open(TOKEN_FILE, "w") as f:
            json.dump(token_data, f, indent=2)

        return token_data["access_token"]

    except requests.exceptions.RequestException as e:
        raise Exception(f"Erro de rede ao obter access token: {e}")


def get_streamer_token(access_token=None, force_refresh=False):
    # Tenta usar token em cache
    if not force_refresh and os.path.exists(STREAMER_TOKEN_FILE):
        try:
            with open(STREAMER_TOKEN_FILE, "r") as f:
                data = json.load(f)
                if data.get("expires_at", 0) > time.time() + 300:
                    return data["token"]
        except Exception:
            pass

    if not access_token:
        access_token = get_access_token()

    # Streamer token usa api.tastyworks.com independente do ambiente
    streamer_url = "https://api.tastyworks.com/api-quote-tokens"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "User-Agent":    "GEX-App/1.0",
    }

    try:
        resp = requests.get(streamer_url, headers=headers, timeout=20)

        if resp.status_code != 200:
            raise Exception(
                f"HTTP {resp.status_code} ao obter streamer token\n"
                f"Resposta: {resp.text[:400]}"
            )

        res        = resp.json()["data"]
        token_data = {
            "token":      res["token"],
            "expires_at": time.time() + (20 * 3600),
        }

        with open(STREAMER_TOKEN_FILE, "w") as f:
            json.dump(token_data, f, indent=2)

        return token_data["token"]

    except requests.exceptions.RequestException as e:
        raise Exception(f"Erro de rede ao obter streamer token: {e}")


def ensure_streamer_token():
    return get_streamer_token()
