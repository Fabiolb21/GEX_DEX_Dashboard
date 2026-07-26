import os
import json
import time
import requests
from dotenv import load_dotenv

# Token file paths
TOKEN_FILE = "tasty_token.json"
STREAMER_TOKEN_FILE = "streamer_token.json"

# Load environment variables
load_dotenv()

# --- CONFIGURAÇÃO DE AMBIENTE ---
# Mude para True se estiver usando conta Sandbox
IS_SANDBOX = True 
BASE_URL = "https://api.cert.tastyworks.com" if IS_SANDBOX else "https://api.tastyworks.com"

def load_credentials_from_env( ):
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and 'CLIENT_ID' in st.secrets:
            return {
                'client_id': st.secrets['CLIENT_ID'],
                'client_secret': st.secrets['CLIENT_SECRET'],
                'refresh_token': st.secrets['REFRESH_TOKEN']
            }
    except: pass
    
    return {
        'client_id': os.getenv('CLIENT_ID'),
        'client_secret': os.getenv('CLIENT_SECRET'),
        'refresh_token': os.getenv('REFRESH_TOKEN')
    }

def get_access_token(force_refresh=False):
    if not force_refresh and os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, 'r') as f:
                data = json.load(f)
                if data.get('expires_at', 0) > time.time() + 60:
                    return data['access_token']
        except: pass

    creds = load_credentials_from_env()
    headers = {
        "User-Agent": "GEX-App/1.0",
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": creds['refresh_token'],
        "client_id": creds['client_id'],
        "client_secret": creds['client_secret']
    }

    url = f"{BASE_URL}/oauth/token"
    
    try:
        # Aumentamos o timeout para 20 segundos para garantir
        response = requests.post(url, data=payload, headers=headers, timeout=20)
        response.raise_for_status()
        
        token_data = response.json()
        token_data['expires_at'] = time.time() + token_data.get('expires_in', 900)
        
        with open(TOKEN_FILE, 'w') as f:
            json.dump(token_data, f)
            
        return token_data['access_token']
    except Exception as e:
        raise Exception(f"Erro na Autenticação: {str(e)}")


def get_streamer_token(access_token=None, force_refresh=False):
    if not force_refresh and os.path.exists(STREAMER_TOKEN_FILE):
        try:
            with open(STREAMER_TOKEN_FILE, 'r') as f:
                data = json.load(f)
                if data.get('expires_at', 0) > time.time() + 300:
                    return data['token']
        except: pass

    if not access_token:
        access_token = get_access_token()

    url = f"{BASE_URL}/api-quote-tokens"
    headers = {"Authorization": f"Bearer {access_token}", "User-Agent": "GEX-App/1.0"}

    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        
        res = response.json()['data']
        token_data = {
            'token': res['token'],
            'expires_at': time.time() + (20 * 3600)
        }
        
        with open(STREAMER_TOKEN_FILE, 'w') as f:
            json.dump(token_data, f)
            
        return token_data['token']
    except Exception as e:
        raise Exception(f"Erro no Streamer Token: {str(e)}")

def ensure_streamer_token():
    return get_streamer_token()
