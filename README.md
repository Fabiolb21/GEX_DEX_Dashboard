# 📊 SPX Gamma Exposure (GEX) Dashboard

Real-time options gamma exposure tracking dashboard built with Streamlit and Tastytrade API.

![Dashboard Preview](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white)

## 🌟 Features

- **Real-time Gamma Exposure Tracking**: Monitor GEX across multiple strike prices
- **Multi-Asset Support**: SPX, NDX, SPY, QQQ, IWM, DIA
- **Zero Gamma (Flip) Detection**: Identify critical price levels where dealer positioning flips
- **Volume & Open Interest Analysis**: Track market activity by strike
- **Implied Volatility Skew**: Visualize IV across strikes
- **Auto-refresh**: Optional continuous data updates
- **0DTE Support**: Track same-day expiration options

## 🚀 Quick Start

### Prerequisites

- Python 3.10 or higher
- Tastytrade account with API access
- Tastytrade API credentials (Client ID, Client Secret, Refresh Token)

### Local Installation

1. **Clone the repository**
```bash
git clone <your-repo-url>
cd gex-dashboard
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure your credentials**

Create a `.env` file in the root directory:
```bash
CLIENT_ID=your_client_id_here
CLIENT_SECRET=your_client_secret_here
REFRESH_TOKEN=your_refresh_token_here
```

Or for Streamlit Cloud, use the secrets management (see deployment section).

4. **Run the app**
```bash
streamlit run app.py
```

The dashboard will open in your browser at `http://localhost:8501`

## 🌐 Deploy to Streamlit Cloud

### Step 1: Prepare Your Repository

1. Push your code to GitHub:
```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin <your-github-repo-url>
git push -u origin main
```

2. Make sure these files are in your repository:
   - `app.py` (main application)
   - `requirements.txt` (dependencies)
   - `utils/` folder with:
     - `__init__.py`
     - `auth.py`
     - `gex_calculator.py`
     - `websocket_manager.py`
   - `.streamlit/config.toml` (optional: UI configuration)

### Step 2: Deploy on Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)

2. Sign in with your GitHub account

3. Click "New app"

4. Fill in the deployment details:
   - **Repository**: Select your GitHub repository
   - **Branch**: `main`
   - **Main file path**: `app.py`

5. Click "Advanced settings" and add your secrets:

```toml
# Add these in the Secrets section
CLIENT_ID = "your_client_id_here"
CLIENT_SECRET = "your_client_secret_here"
REFRESH_TOKEN = "your_refresh_token_here"
```

6. Click "Deploy!"

Your app will be live at: `https://your-app-name.streamlit.app`

### Step 3: Update Auth Module for Streamlit Cloud

The `auth.py` module automatically detects if it's running on Streamlit Cloud and uses `st.secrets` instead of `.env` file.

## 📖 How It Works

### Authentication Flow

1. The app uses OAuth refresh token flow to obtain access tokens from Tastytrade
2. Access tokens are cached with expiration tracking
3. Streamer tokens are obtained for dxFeed WebSocket connection
4. All tokens refresh automatically before expiration

### Data Collection

1. Connects to Tastytrade's dxFeed WebSocket
2. Subscribes to Greeks, Summary (OI), and Trade (Volume) data
3. Collects data for configurable strike range around current price
4. Calculates gamma exposure: `GEX = gamma × open_interest × 100 × spot_price`

### Zero Gamma Calculation

The "Zero Gamma" or "Gamma Flip" level is calculated by finding where Net GEX crosses zero:
- **Above Zero Gamma**: Dealers are long gamma (buying dips, selling rallies)
- **Below Zero Gamma**: Dealers are short gamma (selling dips, buying rallies)

This level acts as a critical pivot point for market dynamics.

## 🎯 Usage Tips

### Symbol Selection
- **SPX/NDX**: Use for index analysis (larger increments)
- **SPY/QQQ**: Use for ETF analysis (smaller increments, higher liquidity)
- **IWM/DIA**: Small cap and Dow tracking

### Strike Range
- **Narrow (15-20 strikes)**: Faster data collection, focused analysis
- **Wide (40-50 strikes)**: Complete picture, longer collection time

### Data Fetch Duration
- **5-10 seconds**: Quick snapshot (may miss some data)
- **15-20 seconds**: Balanced (recommended)
- **25-30 seconds**: Complete data collection

### Auto-Refresh
- Enable for continuous monitoring
- Useful during trading hours
- Disable to conserve API calls

## 📊 Understanding the Charts

### GEX by Strike
- **Green bars**: Call gamma exposure (positive pressure)
- **Red bars**: Put gamma exposure (negative pressure)
- **Orange line**: Current underlying price
- **Purple line**: Zero Gamma level

### Volume & OI
- Shows market activity and positioning
- High OI at a strike = strong support/resistance
- Volume spikes = active trading interest

### IV Skew
- Shows implied volatility across strikes
- Typical shape: higher IV for OTM puts (volatility skew)
- Flatter skew = lower fear premium

## 🔧 Configuration Files

### `.env` (Local Development)
```bash
CLIENT_ID=your_client_id
CLIENT_SECRET=your_client_secret
REFRESH_TOKEN=your_refresh_token
```

### `.streamlit/secrets.toml` (Streamlit Cloud)
```toml
CLIENT_ID = "your_client_id"
CLIENT_SECRET = "your_client_secret"
REFRESH_TOKEN = "your_refresh_token"
```

### `.streamlit/config.toml` (UI Customization)
```toml
[theme]
primaryColor = "#00C851"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"

[server]
headless = true
port = 8501
maxUploadSize = 200
```

## 🐛 Troubleshooting

### "Could not fetch price"
- Market may be closed (use last closing price)
- Network connectivity issues
- API credentials invalid

### "No GEX data available"
- Check if options exist for selected expiration
- Ensure strike range includes traded strikes
- Increase fetch duration

### "Connection timeout"
- Verify internet connection
- Check if Tastytrade API is accessible
- Try reducing strike range

### Token Errors
- Verify API credentials are correct
- Ensure refresh token hasn't expired
- Check Tastytrade API status

## 📚 API Documentation

- [Tastytrade API Docs](https://developer.tastytrade.com/)
- [dxFeed WebSocket Protocol](https://kb.dxfeed.com/)
- [Streamlit Docs](https://docs.streamlit.io/)

## 🔒 Security Notes

- **Never commit `.env` or `secrets.toml` files**
- Add them to `.gitignore`
- Rotate API credentials regularly
- Use Streamlit Cloud secrets management for deployment

## 📦 Project Structure

```
gex-dashboard/
│
├── app.py                  # Main Streamlit application
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── .env.example           # Environment variables template
│
├── utils/                 # Utility modules
│   ├── __init__.py
│   ├── auth.py           # Authentication & token management
│   ├── gex_calculator.py # GEX calculation engine
│   └── websocket_manager.py # WebSocket connection handler
│
└── .streamlit/           # Streamlit configuration
    ├── config.toml       # UI configuration
    └── secrets.toml.example # Secrets template
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## ⚠️ Disclaimer

This software is for educational purposes only. Do not use it for actual trading decisions without proper risk management. Options trading carries significant risk and may not be suitable for all investors.

## 🙏 Acknowledgments

- Tastytrade for providing the API
- dxFeed for real-time market data
- Streamlit for the amazing framework

## 📞 Support

For issues and questions:
- Open an issue on GitHub
- Check existing documentation
- Review Tastytrade API documentation

---

**Built with ❤️ using Streamlit and Tastytrade API**
