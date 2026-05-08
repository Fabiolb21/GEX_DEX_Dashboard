# 🏗️ Arquitetura do Sistema - GEX Dashboard

## Visão Geral

O GEX Dashboard é uma aplicação Streamlit que se conecta à API Tastytrade para obter dados em tempo real de opções e calcular a Exposição Gamma (GEX).

## Fluxo de Dados

```
┌─────────────────┐
│   Streamlit     │
│      App        │
│    (app.py)     │
└────────┬────────┘
         │
         ├─────────────────────────────────┐
         │                                 │
         ▼                                 ▼
┌─────────────────┐              ┌──────────────────┐
│  Auth Module    │              │  GEX Calculator  │
│   (auth.py)     │              │(gex_calculator.py)│
└────────┬────────┘              └──────────────────┘
         │                                 ▲
         │                                 │
         ▼                                 │
┌─────────────────┐                       │
│  Tastytrade API │                       │
│  OAuth Tokens   │                       │
└────────┬────────┘                       │
         │                                 │
         ▼                                 │
┌─────────────────┐                       │
│   dxFeed        │                       │
│   WebSocket     │───────────────────────┘
│  (real-time)    │    Dados de Opções
└─────────────────┘   (Greeks, OI, Volume)
```

## Componentes

### 1. Streamlit App (app.py)
**Responsabilidade**: Interface do usuário e orquestração

**Funcionalidades**:
- Interface web interativa
- Configuração de parâmetros (símbolo, strikes, expiração)
- Visualizações (gráficos Plotly)
- Gerenciamento de estado da sessão
- Auto-refresh opcional

**Dependências**:
- `streamlit`: Framework web
- `plotly`: Visualizações interativas
- `pandas`: Manipulação de dados

### 2. Auth Module (utils/auth.py)
**Responsabilidade**: Autenticação e gerenciamento de tokens

**Funcionalidades**:
- Carregar credenciais (env vars ou Streamlit secrets)
- OAuth refresh token flow
- Cache de tokens com expiração
- Auto-refresh antes de expirar
- Obter streamer token para dxFeed

**Métodos principais**:
```python
load_credentials_from_env()  # Carrega credenciais
get_access_token()           # Obtém/renova access token
get_streamer_token()         # Obtém token dxFeed
ensure_streamer_token()      # Garante token válido
```

**Arquivos gerados**:
- `tasty_token.json`: Access token em cache
- `streamer_token.json`: Streamer token em cache

### 3. GEX Calculator (utils/gex_calculator.py)
**Responsabilidade**: Cálculo e agregação de Gamma Exposure

**Funcionalidades**:
- Parse de símbolos de opções
- Cálculo de GEX: `gamma × OI × 100 × spot_price`
- Agregação por strike
- Cálculo de Zero Gamma (Flip level)
- Thread-safe operations
- Séries temporais (histórico)

**Fórmulas**:
```
GEX = Gamma × Open Interest × 100 × Spot Price
Net GEX = Call GEX - Put GEX
Zero Gamma = Strike onde Net GEX cruza zero
```

**Classes**:
```python
class GEXCalculator:
    update_gamma()              # Atualiza dados de uma opção
    get_gex_by_strike()        # Retorna DataFrame por strike
    get_total_gex_metrics()    # Métricas agregadas
    get_zero_gamma_level()     # Calcula zero gamma
```

### 4. WebSocket Manager (utils/websocket_manager.py)
**Responsabilidade**: Conexão WebSocket com dxFeed (não usado na versão simplificada)

**Nota**: Na versão atual (app.py), o WebSocket é gerenciado diretamente no app para simplicidade. Este módulo está disponível para implementações mais avançadas.

## Fluxo de Autenticação

```
1. App inicia
   │
   ├─> Tenta carregar do cache (tasty_token.json)
   │   └─> Token válido? → Usa token
   │
   └─> Token expirado ou inexistente?
       │
       └─> Carrega credenciais (.env ou secrets)
           │
           └─> POST /oauth/token (refresh flow)
               │
               ├─> Salva access_token em cache
               │
               └─> GET /api-quote-tokens
                   │
                   └─> Salva streamer_token em cache
```

## Fluxo de Coleta de Dados

```
1. Usuário clica "Fetch Data"
   │
   ├─> Obtém token (ensure_streamer_token)
   │
   ├─> Conecta WebSocket dxFeed
   │   ├─> SETUP message
   │   ├─> AUTH message
   │   └─> CHANNEL_REQUEST
   │
   ├─> Busca preço do underlying
   │   └─> Subscribe: Quote + Trade
   │       └─> Retorna preço atual
   │
   ├─> Gera símbolos de opções
   │   └─> Baseado em: preço, strikes, expiration
   │
   ├─> Subscribe a dados de opções
   │   ├─> Greeks (gamma, delta, IV)
   │   ├─> Summary (open interest)
   │   └─> Trade (volume)
   │
   ├─> Coleta dados por X segundos
   │   └─> Acumula em dicionário
   │
   ├─> Fecha WebSocket
   │
   └─> Processa dados
       ├─> Cria GEXCalculator
       ├─> Calcula GEX por opção
       ├─> Agrega por strike
       └─> Exibe visualizações
```

## Cálculo de GEX

### Por Opção Individual
```python
GEX = gamma × open_interest × 100 × spot_price

Onde:
- gamma: sensibilidade do delta ao preço
- open_interest: contratos em aberto
- 100: multiplier (cada contrato = 100 ações)
- spot_price: preço atual do underlying
```

### Agregação por Strike
```python
Call GEX = Σ (gamma_call × OI_call × 100 × spot)
Put GEX = Σ (gamma_put × OI_put × 100 × spot)
Net GEX = Call GEX - Put GEX
```

### Zero Gamma Level
Encontra o strike onde Net GEX cruza zero através de interpolação linear:

```python
Se net_gex[strike_i] e net_gex[strike_i+1] têm sinais diferentes:
    zero_gamma = strike_i + (strike_i+1 - strike_i) × 
                 (-net_gex[i]) / (net_gex[i+1] - net_gex[i])
```

## Estrutura de Dados

### Option Data
```python
{
    ".SPXW251214C6000": {
        "gamma": 0.05,
        "delta": 0.52,
        "iv": 0.18,
        "oi": 1000,
        "volume": 250
    },
    ...
}
```

### Strike Aggregation
```python
{
    6000: {
        "call_gex": 150000000,
        "put_gex": 120000000,
        "call_oi": 5000,
        "put_oi": 4000,
        "call_volume": 1200,
        "put_volume": 900,
        "call_iv": 0.18,
        "put_iv": 0.20
    },
    ...
}
```

## Configuração de Deployment

### Local Development
```
.env file:
CLIENT_ID=...
CLIENT_SECRET=...
REFRESH_TOKEN=...
```

### Streamlit Cloud
```
st.secrets (TOML):
CLIENT_ID = "..."
CLIENT_SECRET = "..."
REFRESH_TOKEN = "..."
```

O módulo `auth.py` detecta automaticamente o ambiente e usa o método apropriado.

## Performance

### Cache de Tokens
- Access tokens: válidos por 15 minutos
- Streamer tokens: válidos por ~20 horas
- Auto-refresh: 60s antes de expirar (access) / 5min antes (streamer)

### Coleta de Dados
- Strike range típico: 50 opções × 4 tipos = 200 subscriptions
- Tempo de coleta: 15-20 segundos (recomendado)
- Frequência: sob demanda ou auto-refresh

### Memória
- Session state mantém: calculator, option_data, preço
- Histórico limitado: últimos 720 snapshots (1 hora @ 5s)

## Segurança

### Credenciais
- Nunca commitadas no Git (.gitignore)
- Armazenadas em: .env (local) ou st.secrets (cloud)
- Tokens em cache não contêm credenciais base

### API Rate Limits
- Não explicitamente limitado pelo app
- Tastytrade tem rate limits próprios
- Auto-refresh: usar com moderação

## Extensibilidade

### Adicionar Novos Underlyings
```python
PRESET_SYMBOLS = {
    "NEW": {
        "option_prefix": "NEW",
        "default_price": 100,
        "increment": 1
    }
}
```

### Adicionar Métricas
Estender `GEXCalculator`:
```python
def get_custom_metric(self):
    with self.lock:
        # Calcular nova métrica
        return result
```

### Novos Gráficos
Adicionar em `app.py`:
```python
fig = go.Figure()
# Adicionar traces
st.plotly_chart(fig)
```

## Limitações Conhecidas

1. **Dados históricos**: Não disponível via dxFeed (apenas tempo real)
2. **Múltiplas expirações**: App foca em uma expiração por vez
3. **Websocket timeout**: Reconecta automaticamente, mas pode perder dados
4. **Streamlit Cloud**: Apps dormem após inatividade (tier gratuito)

## Próximos Passos / Melhorias

- [ ] Suporte a múltiplas expirações simultâneas
- [ ] Exportação de dados (CSV/Excel)
- [ ] Alertas customizáveis
- [ ] Análise histórica (se dados disponíveis)
- [ ] Dark mode theme
- [ ] Mobile optimization
- [ ] Comparação entre dias
- [ ] Machine learning predictions

---

**Versão**: 1.0  
**Última atualização**: Fevereiro 2026
