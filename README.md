# 🤖 Painite OTP Bot

A Telegram OTP bot that fetches SMS from [ivasms.com](https://www.ivasms.com) and delivers OTPs to a Telegram group.

## 📁 Project Structure

```
painite-bot/
├── bot/                    # Python Telegram Bot + Admin REST API
│   ├── main.py             # Main bot entry point
│   ├── panel.py            # ivasms.com panel client (Cloudflare bypass)
│   ├── database.py         # PostgreSQL operations
│   ├── admin_api.py        # FastAPI admin REST API
│   ├── config.py           # Configuration (reads from env vars)
│   ├── utils.py            # Helpers (OTP extract, country detect, etc.)
│   └── requirements.txt    # Python dependencies
├── admin-app/              # Expo React Native Admin App (APK)
│   ├── app/
│   │   ├── login.tsx       # Login screen
│   │   └── (tabs)/
│   │       ├── index.tsx   # Dashboard
│   │       ├── numbers.tsx # Add/Delete numbers
│   │       ├── users.tsx   # Users & Broadcast
│   │       └── smslog.tsx  # SMS/OTP log
│   ├── app.json
│   └── package.json
├── .github/
│   └── workflows/
│       ├── build-apk.yml   # Auto-build Android APK
│       └── deploy-railway.yml  # Auto-deploy to Railway
├── railway.json            # Railway deployment config
├── nixpacks.toml           # Railway build config
└── Procfile                # Start command
```

## 🚀 Deployment on Railway (FREE)

### Step 1: Push to GitHub
1. Create a new GitHub repo (public or private)
2. Push all these files to the repo

### Step 2: Create Railway Project
1. Go to [railway.app](https://railway.app) → Sign in with GitHub
2. Click **"New Project"** → **"Deploy from GitHub repo"**
3. Select your repo
4. Railway will auto-detect the Python app

### Step 3: Add PostgreSQL Database
1. In your Railway project → Click **"+ New"** → **"Database"** → **"PostgreSQL"**
2. Railway will automatically set `DATABASE_URL` env var

### Step 4: Set Environment Variables
In Railway project → **Variables** tab, add these:

| Variable | Value |
|----------|-------|
| `TELEGRAM_BOT_TOKEN` | `8522208519:AAHwD_dI5pUY6lI8HYDmRKoaXStBuDVIapQ` |
| `GROUP_ID` | `-1001367182443` |
| `CHANNEL_ID` | `-1001688406759` |
| `ADMIN_ID` | `1319659809` |
| `ADMIN_USERNAME` | `JAHID_1` |
| `IVASMS_EMAIL` | `m.jahidhassan.k1@gmail.com` |
| `IVASMS_PASSWORD` | `your_ivasms_password` |
| `ADMIN_API_TOKEN` | `painite_admin_secret_2024` |
| `PORT` | `8000` |

### Step 5: Deploy
Click **"Deploy"** — Railway will build and start the bot automatically!

Your bot URL will be: `https://your-app.railway.app`

## 📱 Admin App Setup

### Build APK via GitHub Actions
1. In your GitHub repo → **Settings** → **Secrets** → Add:
   - `API_URL`: Your Railway bot URL (e.g., `https://your-app.railway.app`)
   - `ADMIN_TOKEN`: `painite_admin_secret_2024`
2. Push any change to `admin-app/` folder
3. GitHub Actions will auto-build the APK
4. Download from **Actions** tab → latest workflow → **Artifacts**

### Login to Admin App
- **API URL**: Your Railway URL
- **Admin Token**: `painite_admin_secret_2024` (or your custom ADMIN_API_TOKEN)

## 🤖 Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Start the bot |
| `/add +8801XXX` | Add phone number (admin only) |
| `/delete +8801XXX` | Delete number (admin only) |
| `/stats` | Show statistics (admin only) |
| `/update message` | Broadcast to all users (admin only) |

## 🔑 Bot Features
- 📱 **Paid Number** — Contact admin for paid number
- 📱 **Get Number (Random)** — Get a random available number
- 🌍 **Get Country** — Choose number by country
- 🔐 **OTP Check** — Check OTP for a specific number

## 📊 Admin API Endpoints

Base URL: `https://your-railway-url`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/admin/stats` | Dashboard stats |
| GET | `/admin/numbers` | List all numbers |
| POST | `/admin/numbers` | Add a number |
| DELETE | `/admin/numbers/{phone}` | Delete a number |
| GET | `/admin/users` | List all users |
| POST | `/admin/broadcast` | Broadcast message |
| GET | `/admin/sms-log` | SMS/OTP log |
| GET | `/health` | Health check |

All requests need header: `x-admin-token: your_token`

## ⚠️ Security Notes
- Change `ADMIN_API_TOKEN` to a strong random string
- Change your ivasms.com password
- Never share credentials publicly
