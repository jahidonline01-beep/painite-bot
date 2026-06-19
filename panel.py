import os
import re
import time
import random
import logging
import requests
import database as db
from utils import detect_country_from_phone
from config import (
    IVASMS_EMAIL,
    IVASMS_PASSWORD,
    IVASMS_LOGIN_URL,
    IVASMS_SMS_URL,
    IVASMS_BASE_URL,
    STEX_API_URL,
    STEX_API_KEY,
)

try:
    import cloudscraper
    from bs4 import BeautifulSoup
    _HAS_SCRAPE = True
except Exception:
    _HAS_SCRAPE = False

IVASMS_PROXY = os.environ.get("IVASMS_PROXY", "").strip()


def get_panel_config() -> dict:
    """Panel config comes from the DB (editable from the admin app),
    falling back to env/config defaults. `mode` is either:
      - "api"    → stexsms token API (mauthapi header)
      - "scrape" → legacy ivasms HTML scrape
    """
    s = db.get_all_settings() if db.DATABASE_URL else {}
    return {
        "mode": s.get("panel_mode", "api"),
        "api_url": (s.get("panel_api_url") or STEX_API_URL).rstrip("/"),
        "api_key": s.get("panel_api_key", STEX_API_KEY),
        "site_url": (s.get("panel_site_url") or IVASMS_BASE_URL).rstrip("/"),
        "login_url": s.get("panel_login_url", IVASMS_LOGIN_URL),
        "sms_url": s.get("panel_sms_url", IVASMS_SMS_URL),
        "email": s.get("panel_email", IVASMS_EMAIL),
        "password": s.get("panel_password", IVASMS_PASSWORD),
    }


def range_to_rid(rng) -> str:
    """liveaccess returns ranges like '22501XXX'. getnum needs the digits
    WITHOUT the trailing X placeholders, e.g. '22501'."""
    return re.sub(r"[xX]+$", "", str(rng or "")).strip()


class Panel:
    def __init__(self):
        self._session = requests.Session()
        # scrape state (legacy)
        self.scraper = None
        self.logged_in = False
        self.last_login_time = 0

    # ── stexsms token API ───────────────────────────────────────────────────
    def _api(self, cfg: dict, path: str, method: str = "GET", body: dict = None) -> dict:
        base = cfg.get("api_url", "").strip().rstrip("/")
        key = cfg.get("api_key", "").strip()
        if not base:
            return {"ok": False, "error": "No API URL configured"}
        if not key:
            return {"ok": False, "error": "No API key configured"}
        url = f"{base}/{path.lstrip('/')}"
        headers = {"mauthapi": key, "Accept": "application/json"}
        try:
            if method == "POST":
                headers["Content-Type"] = "application/json"
                r = self._session.post(url, json=body or {}, headers=headers, timeout=30)
            else:
                r = self._session.get(url, headers=headers, timeout=30)
            try:
                data = r.json()
            except Exception:
                return {"ok": False, "error": f"Non-JSON response (HTTP {r.status_code})", "http": r.status_code}
            meta = data.get("meta", {}) if isinstance(data, dict) else {}
            code = meta.get("code")
            return {
                "ok": code == 200,
                "code": code,
                "status": meta.get("status"),
                "data": data.get("data") if isinstance(data, dict) else None,
                "message": data.get("message", "") if isinstance(data, dict) else "",
                "http": r.status_code,
            }
        except Exception as e:
            logging.error(f"Panel API error ({path}): {e}")
            return {"ok": False, "error": str(e)}

    def live_access(self, cfg: dict = None) -> list:
        cfg = cfg or get_panel_config()
        res = self._api(cfg, "liveaccess", "GET")
        if not res.get("ok"):
            logging.error(f"liveaccess failed: {res.get('error') or res.get('status')}")
            return []
        data = res.get("data") or {}
        return data.get("services", []) if isinstance(data, dict) else []

    def get_countries(self, cfg: dict = None) -> list:
        """Group the panel's active ranges by country (detected from the range
        prefix). Returns a list sorted by most-recently-active first."""
        cfg = cfg or get_panel_config()
        services = self.live_access(cfg)
        groups = {}
        for svc in services:
            last_at = svc.get("last_at", 0) or 0
            for rng in svc.get("ranges", []):
                rid = range_to_rid(rng)
                if not rid:
                    continue
                country, flag = detect_country_from_phone(rid)
                if country == "Unknown":
                    key = "+" + rid[:3]
                    label = "Country " + key
                else:
                    key, label = country, country
                g = groups.setdefault(key, {"country": label, "flag": flag, "ranges": [], "last_at": 0})
                if rid not in g["ranges"]:
                    g["ranges"].append(rid)
                if last_at > g["last_at"]:
                    g["last_at"] = last_at
        return sorted(groups.values(), key=lambda x: x["last_at"], reverse=True)

    def latest_rid(self, cfg: dict = None) -> str:
        """Pick a range id from the most-recently-active service (the 'last
        range'). Used by the Random button."""
        cfg = cfg or get_panel_config()
        services = self.live_access(cfg)
        best, best_at = None, -1
        for svc in services:
            last_at = svc.get("last_at", 0) or 0
            ranges = [range_to_rid(r) for r in svc.get("ranges", []) if range_to_rid(r)]
            if ranges and last_at > best_at:
                best_at, best = last_at, ranges
        return random.choice(best) if best else None

    def get_number(self, rid, cfg: dict = None) -> dict:
        """Allocate one number from a range. Returns a dict with success flag."""
        cfg = cfg or get_panel_config()
        res = self._api(cfg, "getnum", "POST", {"rid": str(rid)})
        if res.get("ok") and isinstance(res.get("data"), dict):
            return {"success": True, **res["data"]}
        if res.get("code") == 2946 or res.get("status") == "not_found":
            return {"success": False, "error": "out_of_stock"}
        return {"success": False, "error": res.get("error") or res.get("message") or "request failed"}

    def success_otp(self, cfg: dict = None) -> list:
        cfg = cfg or get_panel_config()
        res = self._api(cfg, "success-otp", "GET")
        if not res.get("ok"):
            return []
        data = res.get("data") or {}
        return data.get("otps", []) if isinstance(data, dict) else []

    # ── Unified SMS feed (used by the watcher and OTP Check) ─────────────────
    def fetch_sms(self) -> list:
        cfg = get_panel_config()
        if cfg["mode"] == "api":
            results = []
            for o in self.success_otp(cfg):
                phone = str(o.get("number", ""))
                message = str(o.get("message", ""))
                if not phone or not message:
                    continue
                country, _ = detect_country_from_phone(phone)
                results.append({
                    "phone": phone,
                    "message": message,
                    "service": "",
                    "country": country if country != "Unknown" else "",
                    "otp_id": str(o.get("otp_id") or f"{phone}|{message}"),
                    "time": o.get("time", 0),
                })
            return results
        return self._fetch_scrape(cfg)

    def test_connection(self) -> dict:
        cfg = get_panel_config()
        if cfg["mode"] == "api":
            res = self._api(cfg, "liveaccess", "GET")
            if res.get("ok"):
                data = res.get("data") or {}
                svcs = data.get("services", []) if isinstance(data, dict) else []
                ranges = sum(len(s.get("ranges", [])) for s in svcs)
                return {"ok": True, "mode": "api", "services": len(svcs), "ranges": ranges}
            return {"ok": False, "mode": "api",
                    "error": res.get("error") or res.get("message") or f"code {res.get('code')}"}
        ok = self.login(cfg)
        return {"ok": ok, "mode": "scrape"}

    # ── Legacy ivasms scrape mode ────────────────────────────────────────────
    def _init_scraper(self):
        if not _HAS_SCRAPE:
            return
        self.scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False},
            delay=10,
        )
        if IVASMS_PROXY:
            self.scraper.proxies = {"http": IVASMS_PROXY, "https": IVASMS_PROXY}
            logging.info("panel: using proxy from IVASMS_PROXY")

    def login(self, cfg: dict = None) -> bool:
        if not _HAS_SCRAPE:
            logging.error("scrape mode unavailable (cloudscraper/bs4 not installed)")
            return False
        cfg = cfg or get_panel_config()
        try:
            self._init_scraper()
            site_url = cfg["site_url"]
            login_url = cfg["login_url"]
            try:
                self.scraper.get(site_url, timeout=30)
            except Exception as e:
                logging.warning(f"panel warmup failed: {e}")

            login_page = self.scraper.get(login_url, timeout=30)
            if login_page.status_code == 403:
                logging.error("Panel login 403 — Cloudflare blocking this IP. Use API mode or a proxy.")

            soup = BeautifulSoup(login_page.text, "html.parser")
            csrf_input = soup.find("input", {"name": "_token"})
            csrf_token = csrf_input.get("value", "") if csrf_input else ""

            payload = {"_token": csrf_token, "email": cfg["email"], "password": cfg["password"]}
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": site_url,
                "Referer": login_url,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Upgrade-Insecure-Requests": "1",
            }
            resp = self.scraper.post(login_url, data=payload, headers=headers, timeout=30, allow_redirects=True)
            if resp.status_code in (200, 302) and "login" not in resp.url.lower():
                self.logged_in = True
                self.last_login_time = time.time()
                logging.info("Panel login successful")
                return True
            logging.error(f"Panel login failed. Status: {resp.status_code}. URL: {resp.url}")
            return False
        except Exception as e:
            logging.error(f"Panel login exception: {e}")
            return False

    def _ensure_logged_in(self, cfg: dict) -> bool:
        if not self.logged_in or (time.time() - self.last_login_time) > 3600:
            return self.login(cfg)
        return True

    def _fetch_scrape(self, cfg: dict) -> list:
        if not self._ensure_logged_in(cfg):
            return []
        try:
            resp = self.scraper.get(cfg["sms_url"], timeout=30)
            if "login" in resp.url.lower():
                self.logged_in = False
                if not self.login(cfg):
                    return []
                resp = self.scraper.get(cfg["sms_url"], timeout=30)
            try:
                return self._parse_json_sms(resp.json())
            except Exception:
                pass
            return self._parse_html_sms(resp.text)
        except Exception as e:
            logging.error(f"Panel fetch_scrape error: {e}")
            return []

    def _parse_json_sms(self, data) -> list:
        results, items = [], []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("data", data.get("sms", data.get("messages", data.get("results", []))))
        if not isinstance(items, list):
            return results
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                phone = str(item.get("number", item.get("phone", item.get("to", item.get("msisdn", "")))))
                message = str(item.get("message", item.get("sms", item.get("body", item.get("text", item.get("content", ""))))))
                service = str(item.get("service", item.get("sender", item.get("from", item.get("app", "")))))
                country = str(item.get("country", item.get("country_name", "")))
                if phone and message:
                    results.append({"phone": phone, "message": message, "service": service,
                                    "country": country, "otp_id": f"{phone}|{message}", "time": 0})
            except Exception:
                continue
        return results

    def _parse_html_sms(self, html: str) -> list:
        results = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            for row in soup.find_all("tr"):
                cols = row.find_all("td")
                if len(cols) >= 3:
                    phone = cols[0].get_text(strip=True)
                    message = cols[-1].get_text(strip=True)
                    service = cols[1].get_text(strip=True) if len(cols) > 2 else ""
                    if phone and message and re.search(r"\d{5,}", phone):
                        results.append({"phone": phone, "message": message, "service": service,
                                        "country": "", "otp_id": f"{phone}|{message}", "time": 0})
        except Exception as e:
            logging.error(f"HTML parse error: {e}")
        return results


panel_instance = Panel()
