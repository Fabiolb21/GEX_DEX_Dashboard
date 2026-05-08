# 🚀 Quick Deployment Guide to Streamlit Cloud

## Prerequisites

✅ GitHub account  
✅ Tastytrade API credentials (Client ID, Client Secret, Refresh Token)  
✅ Your code pushed to a GitHub repository

## Step-by-Step Deployment

### 1. Push Your Code to GitHub

```bash
# Initialize git repository (if not already done)
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit - GEX Dashboard"

# Create main branch
git branch -M main

# Add remote (replace with your repository URL)
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git

# Push to GitHub
git push -u origin main
```

### 2. Go to Streamlit Cloud

Visit: [share.streamlit.io](https://share.streamlit.io)

### 3. Sign In

- Click "Sign in with GitHub"
- Authorize Streamlit Cloud to access your repositories

### 4. Create New App

1. Click "New app" button
2. Select your repository from the dropdown
3. Select branch: `main`
4. Set main file path: `app.py`

### 5. Configure Secrets

1. Click "Advanced settings"
2. In the "Secrets" section, paste:

```toml
CLIENT_ID = "your_actual_client_id"
CLIENT_SECRET = "your_actual_client_secret"
REFRESH_TOKEN = "your_actual_refresh_token"
```

**Important**: Replace the placeholder values with your actual Tastytrade API credentials!

### 6. Deploy!

Click "Deploy" and wait 2-3 minutes for your app to build and launch.

Your app will be available at:
```
https://YOUR-APP-NAME.streamlit.app
```

## 🔐 Getting Tastytrade API Credentials

1. Go to [Tastytrade Developer Portal](https://developer.tastytrade.com/)
2. Sign in with your Tastytrade account
3. Create a new OAuth application
4. Copy your:
   - Client ID
   - Client Secret
   - Generate a Refresh Token

## 🔄 Updating Your App

Any time you push changes to your GitHub repository's main branch, Streamlit Cloud will automatically redeploy your app.

```bash
# Make your changes
git add .
git commit -m "Update: description of changes"
git push origin main
```

Your app will automatically update in 1-2 minutes!

## ⚙️ Managing Your App

From the Streamlit Cloud dashboard, you can:
- ✏️ Edit secrets
- 🔄 Reboot the app
- 📊 View logs
- 📈 Monitor usage
- ⚙️ Change settings
- 🗑️ Delete the app

## 🐛 Troubleshooting

### App Won't Start

**Check logs** in Streamlit Cloud dashboard:
1. Go to your app
2. Click "Manage app" (bottom right)
3. Click "Logs"

Common issues:
- ❌ Missing secrets → Add them in Advanced settings
- ❌ Wrong file path → Should be `app.py`
- ❌ Missing dependencies → Check `requirements.txt`

### "Missing required credentials" Error

Make sure you:
1. Added secrets in Streamlit Cloud (not just locally)
2. Used the correct format (TOML, with quotes)
3. Replaced placeholder values with real credentials

### App Is Slow

This is normal! Free Streamlit Cloud apps:
- May sleep after inactivity
- Share resources with other apps
- Take 10-30 seconds to wake up

## 💰 Pricing

**Free Tier Includes:**
- ✅ 1 GB RAM per app
- ✅ Unlimited public apps
- ✅ Community support

**Paid Plans** (if you need more):
- More resources
- Private apps
- Priority support

## 📞 Support

- 📚 [Streamlit Docs](https://docs.streamlit.io/)
- 💬 [Community Forum](https://discuss.streamlit.io/)
- 🐛 [GitHub Issues](https://github.com/streamlit/streamlit/issues)

## 🎉 You're Done!

Your GEX Dashboard is now live and accessible from anywhere! Share the URL with colleagues or use it for your trading research.

**Happy Trading! 📊💹**
