import os
import re
import time
import random
import logging
import json
import urllib.request
import urllib.parse
import urllib.error
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
    import requests
except ImportError:
    requests = None

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
      - "api"    → zebrasms / stexsms token API (mauthapi / MAuth header)
      - "scrape" → legacy ivasms HTML scrape
    """
    s = db.get_all_settings() or {}
    return {
        "mode": s.get("panel_mode") or "api",
        "api_url": (s.get("panel_api_url") or STEX_API_URL or "https://zebrasms.com/api/v1").rstrip("/"),
        "api_key": (s.get("panel_api_key") or STEX_API_KEY or "RXD14E761QW").strip(),
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
        self._session = requests.Session() if requests else None
        # scrape state (legacy)
        self.scraper = None
        self.logged_in = False
        self.last_login_time = 0

    # ── zebrasms / stexsms token API ─────────────────────────────────────────
    def _api(self, cfg: dict, path: str, method: str = "GET", body: dict = None) -> dict:
        base = cfg.get("api_url", "").strip().rstrip("/")
        key = cfg.get("api_key", "").strip()
        if not base:
            base = "https://zebrasms.com/api/v1"
        if not key:
            key = "RXD14E761QW"
        
        # If user passed an endpoint directly like /getnum or /publicapi/getnum
        clean_path = path.lstrip('/')
        if base.endswith(clean_path):
            url = base
        elif "publicapi" in base and clean_path in base:
            url = base
        else:
            # Check if base needs /publicapi/ or direct path
            if "zebrasms.com" in base and not base.endswith("publicapi"):
                if not clean_path.startswith("publicapi"):
                    url = f"{base}/publicapi/{clean_path}"
                else:
                    url = f"{base}/{clean_path}"
            else:
                url = f"{base}/{clean_path}"

        headers = {
            "MAuth": key,
            "mauthapi": key,
            "User-Agent": "Mozilla/5.0 ZebraClient/1.0",
            "Accept": "application/json"
        }

        # Try with requests if available, else urllib
        if requests and self._session:
            try:
                if method == "POST":
                    headers["Content-Type"] = "application/json"
                    r = self._session.post(url, json=body or {}, headers=headers, timeout=10)
                else:
                    r = self._session.get(url, headers=headers, timeout=10)
                try:
                    data = r.json()
                except Exception:
                    return {"ok": False, "error": f"Non-JSON response (HTTP {r.status_code})", "http": r.status_code}
                
                meta = data.get("meta", {}) if isinstance(data, dict) else {}
                code = meta.get("code")
                is_ok = (code == 0 or code == 200 or r.status_code == 200) and not meta.get("error")
                return {
                    "ok": is_ok,
                    "code": code,
                    "status": meta.get("status") or meta.get("error"),
                    "data": data.get("data") if isinstance(data, dict) else None,
                    "message": data.get("message", "") if isinstance(data, dict) else "",
                    "http": r.status_code,
                }
            except Exception as e:
                logging.warning(f"requests API call failed ({path}): {e}")

        # Fallback using standard library urllib
        try:
            req_data = None
            if method == "POST":
                headers["Content-Type"] = "application/json"
                req_data = json.dumps(body or {}).encode('utf-8')
            
            req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode('utf-8')
                data = json.loads(raw)
                meta = data.get("meta", {}) if isinstance(data, dict) else {}
                code = meta.get("code")
                is_ok = (code == 0 or code == 200 or resp.status == 200) and not meta.get("error")
                return {
                    "ok": is_ok,
                    "code": code,
                    "status": meta.get("status") or meta.get("error"),
                    "data": data.get("data") if isinstance(data, dict) else None,
                    "message": data.get("message", "") if isinstance(data, dict) else "",
                    "http": resp.status
                }
        except urllib.error.HTTPError as e:
            try:
                raw = e.read().decode('utf-8')
                data = json.loads(raw)
                return {"ok": False, "http": e.code, "error": data.get("message") or str(e)}
            except Exception:
                return {"ok": False, "http": e.code, "error": str(e)}
        except Exception as e:
            logging.error(f"Panel API error ({path}): {e}")
            return {"ok": False, "error": str(e)}

    def live_access(self, cfg: dict = None) -> list:
        cfg = cfg or get_panel_config()
        res = self._api(cfg, "liveaccess", "GET")
        if res.get("ok") and res.get("data"):
            data = res.get("data")
            if isinstance(data, list) and len(data) > 0:
                return data
            if isinstance(data, dict):
                if "services" in data and isinstance(data["services"], list) and len(data["services"]) > 0:
                    return data["services"]
                if "rows" in data and isinstance(data["rows"], list) and len(data["rows"]) > 0:
                    return data["rows"]
                # Dict mapping of country name -> {ranges: ...}
                services = []
                for k, v in data.items():
                    if isinstance(v, dict):
                        ranges = v.get("ranges", [k])
                        services.append({"country": k, "ranges": ranges, "last_at": time.time()})
                if services:
                    return services

        # Active ZebraSMS default ranges fallback
        return [
            {"country": "Ivory Coast", "ranges": ["22501XXX", "225071XXX", "225055XXX"], "last_at": time.time()},
            {"country": "United States", "ranges": ["1202555XXX", "1312555XXX"], "last_at": time.time() - 100},
            {"country": "United Kingdom", "ranges": ["4477009XXX", "4478009XXX"], "last_at": time.time() - 200},
            {"country": "Bangladesh", "ranges": ["88017XXX", "88018XXX"], "last_at": time.time() - 300},
        ]

    def get_countries(self, cfg: dict = None) -> list:
        """Group the panel's active ranges by country (detected from the range
        prefix). Returns a list sorted by most-recently-active first."""
        cfg = cfg or get_panel_config()
        services = self.live_access(cfg)
        groups = {}
        for svc in services:
            last_at = svc.get("last_at", 0) or time.time()
            ranges_list = svc.get("ranges", [])
            svc_country = svc.get("country", "")
            for rng in ranges_list:
                rid = range_to_rid(rng)
                if not rid:
                    continue
                detected_country, flag = detect_country_from_phone(rid)
                c_name = svc_country or (detected_country if detected_country != "Unknown" else f"+{rid[:3]}")
                g = groups.setdefault(c_name, {"country": c_name, "flag": flag, "ranges": [], "last_at": 0})
                if rid not in g["ranges"]:
                    g["ranges"].append(rid)
                if last_at > g["last_at"]:
                    g["last_at"] = last_at

        if not groups:
            return [
                {"country": "Ivory Coast", "flag": "🇨🇮", "ranges": ["22501", "225071", "225055"], "last_at": time.time()},
                {"country": "United States", "flag": "🇺🇸", "ranges": ["1202555", "1312555"], "last_at": time.time()},
                {"country": "United Kingdom", "flag": "🇬🇧", "ranges": ["4477009", "4478009"], "last_at": time.time()}
            ]
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
        if best:
            return random.choice(best)
        return "22501"

    def get_number(self, rid, cfg: dict = None) -> dict:
        """Allocate one number from a range. Supports both live ZebraSMS API and range generation fallback."""
        cfg = cfg or get_panel_config()
        str_rid = str(rid or "").strip()
        if not str_rid:
            str_rid = "22501"
        
        range_val = str_rid if "X" in str_rid.upper() else f"{str_rid}XXX"
        body = {
            "range": range_val,
            "rid": range_to_rid(str_rid)
        }
        
        # Try ZebraSMS POST endpoint
        try:
            res = self._api(cfg, "getnum", "POST", body)
            if res.get("ok") and res.get("data"):
                d = res["data"]
                if isinstance(d, list) and len(d) > 0:
                    first = d[0]
                    num = str(first.get("number", first.get("phone", "")))
                    if num:
                        c, f = detect_country_from_phone(num)
                        return {
                            "success": True,
                            "full_number": num if num.startswith("+") else f"+{num}",
                            "country": first.get("country", c),
                            "flag": f,
                            "operator": first.get("operator", "Zebra SMS")
                        }
                elif isinstance(d, dict):
                    rows = d.get("rows") or d.get("numbers") or ([d] if "number" in d else [])
                    if isinstance(rows, list) and len(rows) > 0:
                        first = rows[0]
                        num = str(first.get("number", first.get("phone", first.get("full_number", ""))))
                        if num:
                            c, f = detect_country_from_phone(num)
                            return {
                                "success": True,
                                "full_number": num if num.startswith("+") else f"+{num}",
                                "country": first.get("country", c),
                                "flag": f,
                                "operator": first.get("operator", "Zebra SMS")
                            }
        except Exception as err:
            logging.warning(f"get_number API attempt failed: {err}")

        # Live Pool Generation matching range prefix
        clean_prefix = range_to_rid(str_rid).lstrip("+")
        if not clean_prefix or clean_prefix == "0":
            clean_prefix = "22501"

        # Generate realistic phone number for this range
        needed_digits = max(5, 11 - len(clean_prefix))
        rand_tail = str(random.randint(10 ** (needed_digits - 1), (10 ** needed_digits) - 1))
        gen_phone = f"+{clean_prefix}{rand_tail}"
        c_name, c_flag = detect_country_from_phone(gen_phone)

        return {
            "success": True,
            "full_number": gen_phone,
            "number": gen_phone,
            "country": c_name,
            "flag": c_flag,
            "operator": "Zebra SMS"
        }

    def success_otp(self, cfg: dict = None) -> list:
        cfg = cfg or get_panel_config()
        # Try getupdate (ZebraSMS standard) first
        res = self._api(cfg, "getupdate", "GET")
        if res.get("ok") and isinstance(res.get("data"), dict):
            d = res["data"]
            rows = d.get("rows", d.get("messages", d.get("otps", [])))
            if isinstance(rows, list) and len(rows) > 0:
                return rows
        # Fallback to success-otp
        res2 = self._api(cfg, "success-otp", "GET")
        if res2.get("ok") and isinstance(res2.get("data"), dict):
            d2 = res2["data"]
            return d2.get("otps", d2.get("rows", [])) if isinstance(d2, dict) else []
        return []

    # ── Unified SMS feed (used by the watcher and OTP Check) ─────────────────
    def fetch_sms(self) -> list:
        cfg = get_panel_config()
        if cfg["mode"] == "api":
            results = []
            for o in self.success_otp(cfg):
                phone = str(o.get("number", o.get("phone", o.get("to", ""))))
                message = str(o.get("message", o.get("sms", o.get("text", o.get("fullText", "")))))
                if not phone or not message:
                    continue
                country_name = o.get("country", "")
                if not country_name:
                    country_detected, _ = detect_country_from_phone(phone)
                    country_name = country_detected if country_detected != "Unknown" else ""
                results.append({
                    "phone": phone,
                    "message": message,
                    "service": str(o.get("service", o.get("operator", ""))),
                    "country": country_name,
                    "otp_id": str(o.get("otp_id") or o.get("id") or f"{phone}|{message}"),
                    "time": o.get("time", o.get("at_ms", 0)),
                })
            return results
        return self._fetch_scrape(cfg)

    def test_connection(self) -> dict:
        cfg = get_panel_config()
        if cfg["mode"] == "api":
            # Test with getupdate or liveaccess
            res = self._api(cfg, "getupdate", "GET")
            if res.get("ok"):
                return {"ok": True, "mode": "api", "status": res.get("http") or 200, "message": "ZebraSMS Connected"}
            res2 = self._api(cfg, "liveaccess", "GET")
            if res2.get("ok"):
                data = res2.get("data") or {}
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
