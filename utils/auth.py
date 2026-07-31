"""
Authentication utilities for Tastytrade API
"""
import os
import json
import time
import requests
from dotenv import load_dotenv

TOKEN_FILE          = "tasty_token.json"
STREAMER_TOKEN_FILE = "streamer_token.json"

load_dotenv()

IS_SANDBOX = False

# URLs candidatas em ordem de tentativa
OAUTH_URLS = [
    "https://api.tastytrade.com/oauth/token",
    "https://api.tastyworks.com/oauth/token",
]
STREAMER_URLS = [
    "https://api.tastyworks.com/api-quote-tokens",
    "https://api.tastytrade.com/api-quote-tokens",
]


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
    # Cache
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
            "REFRESH_TOKEN no .env ou nos secrets do Streamlit."
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

    last_error = None
    for url in OAUTH_URLS:
        try:
            resp = requests.post(url, data=payload, headers=headers, timeout=20)
            if resp.status_code == 200:
                token_data = resp.json()
                token_data["expires_at"] = time.time() + token_data.get("expires_in", 900)
                with open(TOKEN_FILE, "w") as f:
                    json.dump(token_data, f, indent=2)
                return token_data["access_token"]
            else:
                last_error = f"HTTP {resp.status_code} em {url}: {resp.text[:300]}"
        except requests.exceptions.ConnectionError as e:
            last_error = f"Sem conexao com {url}: {e}"
            continue
        except requests.exceptions.RequestException as e:
            last_error = f"Erro em {url}: {e}"
            continue

    raise Exception(
        f"Nao foi possivel obter access token. Ultimo erro: {last_error}\n\n"
        "Verifique sua conexao com a internet e se as credenciais estao corretas."
    )


def get_streamer_token(access_token=None, force_refresh=False):
    # Cache
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

    headers = {
        "Authorization": f"Bearer {access_token}",
        "User-Agent":    "GEX-App/1.0",
    }

    last_error = None
    for url in STREAMER_URLS:
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.status_code == 200:
                res        = resp.json()["data"]
                token_data = {
                    "token":         res["token"],
                    "expires_at":    time.time() + (20 * 3600),
                    # Salva URLs dinamicas retornadas pela API
                    "websocket-url": res.get("websocket-url", ""),
                    "dxlink-url":    res.get("dxlink-url", ""),
                }
                with open(STREAMER_TOKEN_FILE, "w") as f:
                    json.dump(token_data, f, indent=2)
                return token_data["token"]
            else:
                last_error = f"HTTP {resp.status_code} em {url}: {resp.text[:300]}"
        except requests.exceptions.ConnectionError as e:
            last_error = f"Sem conexao com {url}: {e}"
            continue
        except requests.exceptions.RequestException as e:
            last_error = f"Erro em {url}: {e}"
            continue

    raise Exception(
        f"Nao foi possivel obter streamer token. Ultimo erro: {last_error}"
    )


def ensure_streamer_token():
    return get_streamer_token()
