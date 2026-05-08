# 🚀 INÍCIO RÁPIDO - GEX Dashboard

## 📦 Arquivos do Projeto

Você recebeu os seguintes arquivos:

```
gex-dashboard/
├── app.py                      # Aplicativo principal Streamlit
├── requirements.txt            # Dependências Python
├── README.md                   # Documentação completa
├── DEPLOYMENT.md               # Guia de deployment
├── LICENSE                     # Licença MIT
├── .env.example               # Template de variáveis de ambiente
├── .gitignore                 # Arquivos ignorados pelo Git
├── utils/                     # Módulos auxiliares
│   ├── __init__.py
│   ├── auth.py               # Autenticação Tastytrade
│   ├── gex_calculator.py     # Cálculo de GEX
│   └── websocket_manager.py  # Gerenciador WebSocket
└── .streamlit/
    ├── config.toml           # Configuração UI
    └── secrets.toml.example  # Template de secrets
```

## ⚡ 3 Passos para Deploy no Streamlit Cloud

### 1️⃣ Criar Repositório no GitHub

```bash
# Extrair arquivos e navegar para a pasta
cd gex-dashboard

# Inicializar Git
git init
git add .
git commit -m "Initial commit"
git branch -M main

# Conectar ao GitHub (crie o repo primeiro em github.com)
git remote add origin https://github.com/SEU_USUARIO/gex-dashboard.git
git push -u origin main
```

### 2️⃣ Deploy no Streamlit Cloud

1. Acesse: https://share.streamlit.io
2. Faça login com GitHub
3. Clique em "New app"
4. Selecione seu repositório
5. Branch: `main`
6. Main file: `app.py`

### 3️⃣ Adicionar Credentials

Em "Advanced settings" → "Secrets", adicione:

```toml
CLIENT_ID = "seu_client_id_aqui"
CLIENT_SECRET = "seu_client_secret_aqui"
REFRESH_TOKEN = "seu_refresh_token_aqui"
```

**Clique em "Deploy"** e pronto! 🎉

## 🖥️ Testar Localmente (Opcional)

```bash
# Instalar dependências
pip install -r requirements.txt

# Criar arquivo .env com suas credenciais
cp .env.example .env
# Edite .env com suas credenciais reais

# Executar
streamlit run app.py
```

Abra: http://localhost:8501

## 🔑 Obter Credenciais Tastytrade

1. Acesse: https://developer.tastytrade.com/
2. Faça login com sua conta Tastytrade
3. Crie uma aplicação OAuth
4. Copie:
   - Client ID
   - Client Secret
   - Gere um Refresh Token

## 📚 Documentação

- **README.md**: Documentação completa do projeto
- **DEPLOYMENT.md**: Guia detalhado de deployment
- Streamlit Docs: https://docs.streamlit.io/

## ❓ Precisa de Ajuda?

1. Leia o README.md para instruções detalhadas
2. Verifique o DEPLOYMENT.md para troubleshooting
3. Consulte os logs no Streamlit Cloud

## 🎯 Recursos do Dashboard

✅ Tracking de Gamma Exposure em tempo real  
✅ Suporte a múltiplos ativos (SPX, NDX, SPY, QQQ, IWM, DIA)  
✅ Detecção de Zero Gamma (Flip)  
✅ Análise de Volume & Open Interest  
✅ Volatilidade Implícita Skew  
✅ Auto-refresh  
✅ Suporte a 0DTE  

## ⚠️ Importante

- Nunca commite arquivos `.env` ou `secrets.toml`
- Use sempre o `.gitignore` fornecido
- Este software é apenas para fins educacionais
- Trading de opções envolve riscos significativos

---

**Pronto para começar?** Siga os 3 passos acima! 🚀

Boa sorte com seu dashboard! 📊💹
