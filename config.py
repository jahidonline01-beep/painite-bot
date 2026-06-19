import os

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8522208519:AAHwD_dI5pUY6lI8HYDmRKoaXStBuDVIapQ")
GROUP_ID = int(os.environ.get("GROUP_ID", "-1001367182443"))
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "-1001688406759"))
ADMIN_ID = int(os.environ.get("ADMIN_ID", "1319659809"))
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "JAHID_1")
UPDATE_CHANNEL_LINK = os.environ.get("UPDATE_CHANNEL_LINK", "https://t.me/painite_1")
GROUP_LINK = os.environ.get("GROUP_LINK", "https://t.me/painite_club")

# ─── stexsms token API (primary panel) ───────────────────────────────────────
# Base path is the per-account API root, e.g.
#   https://api.2oo9.cloud/<ACCOUNT>/<SLUG>/@public/api
# Auth: send the API key in the `mauthapi` header (set it from the admin app).
STEX_API_URL = os.environ.get(
    "STEX_API_URL",
    "https://api.2oo9.cloud/MXS47FLFX0U/tness/@public/api",
)
STEX_API_KEY = os.environ.get("STEX_API_KEY", "")

# ─── Legacy ivasms scrape panel (fallback / panel-switch option) ──────────────
IVASMS_EMAIL = os.environ.get("IVASMS_EMAIL", "")
IVASMS_PASSWORD = os.environ.get("IVASMS_PASSWORD", "")
IVASMS_BASE_URL = "https://www.ivasms.com"
IVASMS_LOGIN_URL = f"{IVASMS_BASE_URL}/portal/login"
IVASMS_SMS_URL = f"{IVASMS_BASE_URL}/portal/live/my_sms"
IVASMS_SMS_API = f"{IVASMS_BASE_URL}/portal/live/get_sms"

DATABASE_URL = os.environ.get("DATABASE_URL", "")
ADMIN_API_TOKEN = os.environ.get("ADMIN_API_TOKEN", "painite_admin_secret_2024")
PORT = int(os.environ.get("PORT", "8000"))
