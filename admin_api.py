from fastapi import FastAPI, Header, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import database as db
from config import ADMIN_API_TOKEN

app = FastAPI(title="Painite Bot Admin API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def verify_token(x_admin_token: str = Header(...)):
    if x_admin_token != ADMIN_API_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

class BroadcastIn(BaseModel):
    message: str

class BotStatusIn(BaseModel):
    active: bool

class PanelSettingsIn(BaseModel):
    mode: Optional[str] = None
    site_url: Optional[str] = None
    login_url: Optional[str] = None
    sms_url: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    api_url: Optional[str] = None
    api_key: Optional[str] = None

_broadcast_callback = None

def set_broadcast_callback(fn):
    global _broadcast_callback
    _broadcast_callback = fn

@app.get("/admin/stats")
def get_stats(x_admin_token: str = Header(...)):
    verify_token(x_admin_token)
    return db.get_stats()


@app.get("/admin/users")
def list_users(x_admin_token: str = Header(...)):
    verify_token(x_admin_token)
    return db.get_all_users()

@app.post("/admin/broadcast")
async def broadcast(body: BroadcastIn, x_admin_token: str = Header(...)):
    verify_token(x_admin_token)
    if not _broadcast_callback:
        raise HTTPException(status_code=503, detail="Bot not ready")
    users = db.get_all_users()
    import asyncio
    result = await _broadcast_callback(body.message, [u["user_id"] for u in users])
    return result

@app.get("/admin/sms-log")
def sms_log(x_admin_token: str = Header(...)):
    verify_token(x_admin_token)
    return db.get_sms_log(100)

@app.get("/admin/bot-status")
def bot_status(x_admin_token: str = Header(...)):
    verify_token(x_admin_token)
    return {"active": db.is_bot_active()}

@app.post("/admin/bot-status")
def set_bot_status(body: BotStatusIn, x_admin_token: str = Header(...)):
    verify_token(x_admin_token)
    db.set_setting("bot_active", "1" if body.active else "0")
    return {"active": body.active}

@app.get("/admin/settings")
def get_settings(x_admin_token: str = Header(...)):
    verify_token(x_admin_token)
    from panel import get_panel_config
    cfg = get_panel_config()
    return {
        "mode": cfg["mode"],
        "site_url": cfg["site_url"],
        "login_url": cfg["login_url"],
        "sms_url": cfg["sms_url"],
        "email": cfg["email"],
        "password": cfg["password"],
        "api_url": cfg["api_url"],
        "api_key": cfg["api_key"],
    }

@app.post("/admin/settings")
def save_settings(body: PanelSettingsIn, x_admin_token: str = Header(...)):
    verify_token(x_admin_token)
    mapping = {
        "panel_mode": body.mode,
        "panel_site_url": body.site_url,
        "panel_login_url": body.login_url,
        "panel_sms_url": body.sms_url,
        "panel_email": body.email,
        "panel_password": body.password,
        "panel_api_url": body.api_url,
        "panel_api_key": body.api_key,
    }
    for key, val in mapping.items():
        if val is not None:
            db.set_setting(key, val)
    return {"success": True}

@app.post("/admin/panel/test")
def test_panel(x_admin_token: str = Header(...)):
    verify_token(x_admin_token)
    from panel import panel_instance
    return panel_instance.test_connection()

@app.get("/admin/panel/ranges")
def panel_ranges(x_admin_token: str = Header(...)):
    verify_token(x_admin_token)
    from panel import panel_instance
    try:
        return {"countries": panel_instance.get_countries()}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

@app.get("/admin/panel/otps")
def panel_otps(x_admin_token: str = Header(...)):
    verify_token(x_admin_token)
    from panel import panel_instance
    try:
        return {"otps": panel_instance.success_otp()}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

@app.get("/health")
def health():
    return {"status": "ok"}
