#!/usr/bin/env python3
"""
Evision Infoserve — site + admin API server (zero external dependencies).

Serves the static marketing site AND a small JSON API on the same port, so the
public contact form can POST enquiries same-origin and the /admin/ panel can
read them back.

Storage : SQLite (evision.db, created next to this file)
Auth    : PBKDF2-HMAC-SHA256 password hashing + in-memory bearer tokens
Run     : python server.py   (defaults to http://localhost:8000)
"""

import json
import os
import re
import sqlite3
import hashlib
import secrets
import smtplib
import threading
import time
from datetime import datetime, timezone
from email.message import EmailMessage
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(ROOT, "evision.db")
PORT = int(os.environ.get("PORT", "8000"))
# Bind 0.0.0.0 for local dev; set HOST=127.0.0.1 in production (behind Nginx).
HOST = os.environ.get("HOST", "0.0.0.0")

# Default seed admin — CHANGE THE PASSWORD after first login (panel > Settings).
SEED_EMAIL = os.environ.get("ADMIN_EMAIL", "evisiononweb@gmail.com")
SEED_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Evision@2026")

PBKDF2_ROUNDS = 240_000
SESSION_TTL = 60 * 60 * 12  # 12 hours

# ── Optional email notifications ──────────────────────────────────────────
# Set these env vars to email the admin whenever a new enquiry arrives.
# Leave unset and the server still saves enquiries — it just logs instead.
#   set SMTP_HOST=smtp.gmail.com
#   set SMTP_PORT=587
#   set SMTP_USER=your@gmail.com
#   set SMTP_PASS=your-app-password          (Gmail: an "App Password", not your login)
#   set SMTP_FROM=your@gmail.com
#   set NOTIFY_TO=info@evisioninfoserve.com  (where alerts are delivered)
SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASS = os.environ.get("SMTP_PASS")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER or "")
NOTIFY_TO = os.environ.get("NOTIFY_TO", "info@evisioninfoserve.com")

# token -> {"email": str, "expires": float}
SESSIONS = {}


# ───────────────────────── helpers ─────────────────────────

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ROUNDS)
    return dk.hex(), salt


def verify_password(password, pw_hash, salt):
    calc, _ = hash_password(password, salt)
    return secrets.compare_digest(calc, pw_hash)


def init_db():
    conn = db()
    c = conn.cursor()
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            pw_hash TEXT NOT NULL,
            pw_salt TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS enquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, email TEXT, phone TEXT, company TEXT, website TEXT,
            service TEXT, budget TEXT, message TEXT,
            type TEXT DEFAULT 'quote',
            source TEXT,
            status TEXT DEFAULT 'new',
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, email TEXT, phone TEXT, company TEXT, website TEXT,
            service TEXT, plan TEXT, value TEXT,
            status TEXT DEFAULT 'active',
            notes TEXT DEFAULT '',
            from_enquiry INTEGER,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price INTEGER DEFAULT 0,          -- base price in rupees
            unit TEXT DEFAULT '/mo',          -- e.g. '/mo', 'one-time', '/project'
            starting INTEGER DEFAULT 1,       -- show "Starting at"
            discount_pct INTEGER DEFAULT 0,   -- per-service discount override (0 = none)
            description TEXT DEFAULT '',
            sort INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,               -- e.g. 'Diwali Sale'
            discount_pct INTEGER DEFAULT 0,
            note TEXT DEFAULT '',             -- short line shown in the banner
            active INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );
        """
    )
    conn.commit()
    # ── lightweight migrations: add columns to existing databases ──
    existing_cols = {r["name"] for r in c.execute("PRAGMA table_info(enquiries)").fetchall()}
    for col, ddl in (("consent", "consent INTEGER DEFAULT 0"),
                     ("marketing", "marketing INTEGER DEFAULT 0")):
        if col not in existing_cols:
            c.execute(f"ALTER TABLE enquiries ADD COLUMN {ddl}")
    conn.commit()
    # Seed services on first run (idempotent: INSERT OR IGNORE on unique slug).
    for i, (slug, name, cat, price, unit, starting, desc) in enumerate(SERVICES_SEED):
        c.execute(
            """INSERT OR IGNORE INTO services
               (slug,name,category,price,unit,starting,description,sort,active)
               VALUES (?,?,?,?,?,?,?,?,1)""",
            (slug, name, cat, price, unit, starting, desc, i),
        )
    conn.commit()
    # Seed the first admin if none exist.
    existing = c.execute("SELECT COUNT(*) AS n FROM admins").fetchone()["n"]
    if existing == 0:
        h, s = hash_password(SEED_PASSWORD)
        c.execute(
            "INSERT INTO admins (email, pw_hash, pw_salt, created_at) VALUES (?,?,?,?)",
            (SEED_EMAIL.lower(), h, s, now_iso()),
        )
        conn.commit()
        print(f"  -> Seeded admin account: {SEED_EMAIL}  (password: {SEED_PASSWORD})")
        print("    Please change this password after your first login.")
    conn.close()


def new_token(email):
    tok = secrets.token_urlsafe(32)
    SESSIONS[tok] = {"email": email, "expires": time.time() + SESSION_TTL}
    return tok


def session_email(token):
    s = SESSIONS.get(token)
    if not s:
        return None
    if s["expires"] < time.time():
        SESSIONS.pop(token, None)
        return None
    return s["email"]


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Services seeded on first run. Prices are PLACEHOLDERS — edit them in the admin
# panel (Pricing tab). (slug, name, category, price, unit, starting, description)
SERVICES_SEED = [
    # ── SEO ──
    ("seo", "SEO & AI Search", "SEO", 15000, "/mo", 1, "Full-funnel SEO engineered to rank on Google and get cited by AI engines."),
    ("ai-seo", "AI SEO", "SEO", 18000, "/mo", 1, "Optimisation for AI Overviews and answer engines (AEO/GEO)."),
    ("llm-optimization", "LLM Optimization", "SEO", 20000, "/mo", 1, "Get your brand surfaced and cited inside ChatGPT, Gemini & Perplexity."),
    ("agentic-ai-seo", "Agentic AI SEO", "SEO", 25000, "/mo", 1, "Automation-driven SEO with AI agents handling research and execution."),
    ("enterprise-seo", "Enterprise SEO", "SEO", 40000, "/mo", 1, "Scaled SEO programs for large, complex sites and multiple teams."),
    ("ecommerce-seo", "Ecommerce SEO", "SEO", 30000, "/mo", 1, "Category, product and collection-page SEO that drives revenue."),
    ("technical-seo", "Technical SEO", "SEO", 22000, "/mo", 1, "Crawl, indexation, Core Web Vitals and schema fixed at the root."),
    ("local-seo", "Local SEO", "SEO", 12000, "/mo", 1, "Google Business Profile, maps pack and local citation dominance."),
    ("multilingual-seo", "Multilingual SEO Services", "SEO", 28000, "/mo", 1, "Hreflang, localisation and SEO across multiple languages and regions."),
    ("link-building", "Link Building Services", "SEO", 15000, "/mo", 1, "White-hat authority links from relevant, high-quality publishers."),
    ("white-label-seo", "White Label SEO Services", "SEO", 20000, "/mo", 1, "SEO delivery under your agency's brand, reported your way."),
    ("seo-audit", "SEO Audit", "SEO", 9000, "one-time", 0, "A 12-point technical, content and AI-visibility audit with an action plan."),
    # ── Content Marketing ──
    ("content-marketing", "Content Marketing", "Content Marketing", 20000, "/mo", 1, "Topic clusters, blogs and video that build topical authority."),
    ("guest-posting", "Guest Posting", "Content Marketing", 12000, "/mo", 1, "Editorially placed guest articles on relevant, authoritative sites."),
    ("content-writing", "Content Writing Services", "Content Marketing", 15000, "/mo", 1, "SEO-led blogs, web copy and landing pages written to convert."),
    ("digital-pr", "Digital PR", "Content Marketing", 25000, "/mo", 1, "Newsworthy campaigns that earn coverage, links and brand mentions."),
    # ── Other services ──
    ("social-media", "Social Media (SMO)", "Other Services", 14000, "/mo", 1, "Organic social growth, community and content that converts."),
    ("ppc", "PPC & Paid Ads", "Other Services", 18000, "/mo", 1, "Google, Meta and LinkedIn ad campaigns engineered for ROI."),
    ("orm", "ORM & Reputation", "Other Services", 16000, "/mo", 1, "Review management and brand defence across the web."),
    ("ai-marketing", "AI Digital Marketing", "Other Services", 22000, "/mo", 1, "GEO, automation and analytics for the AI-search era."),
]
CATEGORY_ORDER = ["SEO", "Content Marketing", "Other Services"]


def compute_pricing(conn):
    """Return (offer_dict_or_None, [service_dicts]) with final prices computed."""
    offer_row = conn.execute(
        "SELECT name, discount_pct, note FROM offers WHERE active=1 ORDER BY id DESC LIMIT 1"
    ).fetchone()
    offer = dict(offer_row) if offer_row else None
    site_disc = offer["discount_pct"] if offer else 0
    rows = conn.execute(
        "SELECT * FROM services WHERE active=1 ORDER BY sort, id"
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        # Per-service discount overrides the site-wide offer; otherwise use site-wide.
        eff = d["discount_pct"] if d["discount_pct"] else site_disc
        eff = max(0, min(90, eff))
        d["effective_discount"] = eff
        d["final_price"] = round(d["price"] * (100 - eff) / 100) if eff else d["price"]
        out.append(d)
    return offer, out


def notify_new_enquiry(e):
    """Email the admin about a new enquiry. Runs in a background thread so the
    visitor's request is never blocked. Degrades gracefully if SMTP is unset."""
    label = "Free Audit" if e.get("type") == "audit" else "Quote"
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS):
        print(f"[enquiry] New {label}: {e.get('name')} <{e.get('email')}> "
              f"— email notify not configured (set SMTP_* env vars to enable).")
        return
    try:
        body = (
            f"New {label} request from the website:\n\n"
            f"Name    : {e.get('name')}\n"
            f"Email   : {e.get('email')}\n"
            f"Phone   : {e.get('phone')}\n"
            f"Company : {e.get('company')}\n"
            f"Website : {e.get('website')}\n"
            f"Service : {e.get('service')}\n"
            f"Budget  : {e.get('budget')}\n"
            f"Source  : {e.get('source')}\n"
            f"Consent (T&C)     : {'yes' if e.get('consent') else 'no'}\n"
            f"Marketing opt-in  : {'yes' if e.get('marketing') else 'no'}\n\n"
            f"Message:\n{e.get('message') or '(none)'}\n\n"
            f"— View in the admin panel: /admin/\n"
        )
        msg = EmailMessage()
        msg["Subject"] = f"[Evision] New {label} — {e.get('name')}"
        msg["From"] = SMTP_FROM
        msg["To"] = NOTIFY_TO
        if e.get("email"):
            msg["Reply-To"] = e["email"]
        msg.set_content(body)
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        print(f"[enquiry] Notification email sent to {NOTIFY_TO}")
    except Exception as ex:  # never let email problems break the API
        print(f"[enquiry] Email notification failed: {ex}")


# ───────────────────────── request handler ─────────────────────────

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def log_message(self, fmt, *args):
        # Quieter logging
        pass

    def end_headers(self):
        # Tell browsers not to cache static assets, so edits show up on reload.
        p = self.path.split("?")[0]
        if not p.startswith("/api/") and (p.endswith((".html", ".js", ".css")) or p.endswith("/")):
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    # ---- low-level json helpers ----
    def _json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8", "replace") or "{}")
        except json.JSONDecodeError:
            return {}

    def _auth(self):
        h = self.headers.get("Authorization", "")
        if h.startswith("Bearer "):
            return session_email(h[7:])
        return None

    def _require_auth(self):
        email = self._auth()
        if not email:
            self._json({"error": "Unauthorized"}, 401)
            return None
        return email

    # ---- dispatch ----
    def do_GET(self):
        if self.path.split("?")[0].startswith("/api/"):
            return self.api_get()
        # Pretty URL: /admin -> /admin/index.html handled by SimpleHTTPRequestHandler
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/"):
            return self.api_post()
        self.send_error(404)

    def do_PATCH(self):
        if self.path.startswith("/api/"):
            return self.api_patch()
        self.send_error(404)

    def do_DELETE(self):
        if self.path.startswith("/api/"):
            return self.api_delete()
        self.send_error(404)

    # ───────────── API: GET ─────────────
    def api_get(self):
        path = self.path.split("?")[0]
        # Public pricing feed (services + active festival offer, prices computed).
        if path == "/api/pricing":
            conn = db()
            offer, services = compute_pricing(conn)
            conn.close()
            return self._json({"offer": offer, "services": services})
        if path == "/api/admin/services":
            if not self._require_auth():
                return
            conn = db()
            rows = conn.execute("SELECT * FROM services ORDER BY sort, id").fetchall()
            conn.close()
            return self._json([dict(r) for r in rows])
        if path == "/api/admin/offers":
            if not self._require_auth():
                return
            conn = db()
            rows = conn.execute("SELECT * FROM offers ORDER BY id DESC").fetchall()
            conn.close()
            return self._json([dict(r) for r in rows])
        if path == "/api/admin/enquiries":
            if not self._require_auth():
                return
            conn = db()
            rows = conn.execute("SELECT * FROM enquiries ORDER BY id DESC").fetchall()
            conn.close()
            return self._json([dict(r) for r in rows])
        if path == "/api/admin/clients":
            if not self._require_auth():
                return
            conn = db()
            rows = conn.execute("SELECT * FROM clients ORDER BY id DESC").fetchall()
            conn.close()
            return self._json([dict(r) for r in rows])
        if path == "/api/admin/stats":
            if not self._require_auth():
                return
            conn = db()
            stats = {
                "enquiries": conn.execute("SELECT COUNT(*) n FROM enquiries").fetchone()["n"],
                "new": conn.execute("SELECT COUNT(*) n FROM enquiries WHERE status='new'").fetchone()["n"],
                "clients": conn.execute("SELECT COUNT(*) n FROM clients").fetchone()["n"],
                "active": conn.execute("SELECT COUNT(*) n FROM clients WHERE status='active'").fetchone()["n"],
            }
            conn.close()
            return self._json(stats)
        if path == "/api/admin/me":
            email = self._require_auth()
            if not email:
                return
            return self._json({"email": email})
        return self._json({"error": "Not found"}, 404)

    # ───────────── API: POST ─────────────
    def api_post(self):
        path = self.path
        data = self._body()

        # Public: visitor submits an enquiry from the contact form
        if path == "/api/enquiry":
            name = (data.get("name") or "").strip()
            email = (data.get("email") or "").strip()
            phone = (data.get("phone") or "").strip()
            if not name or not EMAIL_RE.match(email):
                return self._json({"error": "Name and a valid email are required."}, 400)
            record = {
                "name": name, "email": email, "phone": phone,
                "company": (data.get("company") or "").strip(),
                "website": (data.get("website") or "").strip(),
                "service": (data.get("service") or "").strip(),
                "budget": (data.get("budget") or "").strip(),
                "message": (data.get("message") or "").strip(),
                "type": (data.get("type") or "quote").strip(),
                "source": (data.get("source") or "").strip(),
                "consent": 1 if data.get("consent") else 0,
                "marketing": 1 if data.get("marketing") else 0,
            }
            conn = db()
            conn.execute(
                """INSERT INTO enquiries
                   (name,email,phone,company,website,service,budget,message,type,source,
                    consent,marketing,status,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?, 'new', ?)""",
                (
                    record["name"], record["email"], record["phone"], record["company"],
                    record["website"], record["service"], record["budget"], record["message"],
                    record["type"], record["source"], record["consent"], record["marketing"],
                    now_iso(),
                ),
            )
            conn.commit()
            conn.close()
            # Fire-and-forget admin notification (won't block the response).
            threading.Thread(target=notify_new_enquiry, args=(record,), daemon=True).start()
            return self._json({"ok": True}, 201)

        # Admin: login
        if path == "/api/admin/login":
            email = (data.get("email") or "").strip().lower()
            password = data.get("password") or ""
            conn = db()
            row = conn.execute("SELECT * FROM admins WHERE email=?", (email,)).fetchone()
            conn.close()
            if not row or not verify_password(password, row["pw_hash"], row["pw_salt"]):
                return self._json({"error": "Invalid email or password."}, 401)
            return self._json({"token": new_token(email), "email": email})

        # Admin: logout
        if path == "/api/admin/logout":
            h = self.headers.get("Authorization", "")
            if h.startswith("Bearer "):
                SESSIONS.pop(h[7:], None)
            return self._json({"ok": True})

        # Admin: change password
        if path == "/api/admin/change-password":
            email = self._require_auth()
            if not email:
                return
            current = data.get("current") or ""
            new = data.get("new") or ""
            if len(new) < 8:
                return self._json({"error": "New password must be at least 8 characters."}, 400)
            conn = db()
            row = conn.execute("SELECT * FROM admins WHERE email=?", (email,)).fetchone()
            if not row or not verify_password(current, row["pw_hash"], row["pw_salt"]):
                conn.close()
                return self._json({"error": "Current password is incorrect."}, 401)
            h, s = hash_password(new)
            conn.execute("UPDATE admins SET pw_hash=?, pw_salt=? WHERE email=?", (h, s, email))
            conn.commit()
            conn.close()
            return self._json({"ok": True})

        # Admin: add client
        if path == "/api/admin/clients":
            if not self._require_auth():
                return
            conn = db()
            cur = conn.execute(
                """INSERT INTO clients
                   (name,email,phone,company,website,service,plan,value,status,notes,from_enquiry,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    (data.get("name") or "").strip(),
                    (data.get("email") or "").strip(),
                    (data.get("phone") or "").strip(),
                    (data.get("company") or "").strip(),
                    (data.get("website") or "").strip(),
                    (data.get("service") or "").strip(),
                    (data.get("plan") or "").strip(),
                    (data.get("value") or "").strip(),
                    (data.get("status") or "active").strip(),
                    (data.get("notes") or "").strip(),
                    data.get("from_enquiry"),
                    now_iso(),
                ),
            )
            conn.commit()
            cid = cur.lastrowid
            conn.close()
            return self._json({"ok": True, "id": cid}, 201)

        # Admin: create a festival offer
        if path == "/api/admin/offers":
            if not self._require_auth():
                return
            name = (data.get("name") or "").strip()
            if not name:
                return self._json({"error": "Offer name is required."}, 400)
            active = 1 if data.get("active") else 0
            conn = db()
            # Only one site-wide offer should be active at a time.
            if active:
                conn.execute("UPDATE offers SET active=0")
            cur = conn.execute(
                "INSERT INTO offers (name,discount_pct,note,active,created_at) VALUES (?,?,?,?,?)",
                (name, int(data.get("discount_pct") or 0), (data.get("note") or "").strip(),
                 active, now_iso()),
            )
            conn.commit()
            oid = cur.lastrowid
            conn.close()
            return self._json({"ok": True, "id": oid}, 201)

        # Admin: convert an enquiry into a client
        m = re.match(r"^/api/admin/enquiries/(\d+)/convert$", path)
        if m:
            if not self._require_auth():
                return
            eid = int(m.group(1))
            conn = db()
            e = conn.execute("SELECT * FROM enquiries WHERE id=?", (eid,)).fetchone()
            if not e:
                conn.close()
                return self._json({"error": "Enquiry not found."}, 404)
            cur = conn.execute(
                """INSERT INTO clients
                   (name,email,phone,company,website,service,plan,value,status,notes,from_enquiry,created_at)
                   VALUES (?,?,?,?,?,?,?,?, 'active', ?, ?, ?)""",
                (
                    e["name"], e["email"], e["phone"], e["company"], e["website"],
                    e["service"], "", e["budget"], e["message"] or "", eid, now_iso(),
                ),
            )
            conn.execute("UPDATE enquiries SET status='converted' WHERE id=?", (eid,))
            conn.commit()
            cid = cur.lastrowid
            conn.close()
            return self._json({"ok": True, "id": cid}, 201)

        return self._json({"error": "Not found"}, 404)

    # ───────────── API: PATCH ─────────────
    def api_patch(self):
        email = self._require_auth()
        if not email:
            return
        data = self._body()

        m = re.match(r"^/api/admin/enquiries/(\d+)$", self.path)
        if m:
            eid = int(m.group(1))
            fields, vals = [], []
            for k in ("status", "notes"):
                if k in data:
                    fields.append(f"{k}=?")
                    vals.append(data[k])
            if not fields:
                return self._json({"error": "Nothing to update."}, 400)
            vals.append(eid)
            conn = db()
            conn.execute(f"UPDATE enquiries SET {','.join(fields)} WHERE id=?", vals)
            conn.commit()
            conn.close()
            return self._json({"ok": True})

        m = re.match(r"^/api/admin/clients/(\d+)$", self.path)
        if m:
            cid = int(m.group(1))
            allowed = ("name", "email", "phone", "company", "website",
                       "service", "plan", "value", "status", "notes")
            fields, vals = [], []
            for k in allowed:
                if k in data:
                    fields.append(f"{k}=?")
                    vals.append(data[k])
            if not fields:
                return self._json({"error": "Nothing to update."}, 400)
            vals.append(cid)
            conn = db()
            conn.execute(f"UPDATE clients SET {','.join(fields)} WHERE id=?", vals)
            conn.commit()
            conn.close()
            return self._json({"ok": True})

        m = re.match(r"^/api/admin/services/(\d+)$", self.path)
        if m:
            sid = int(m.group(1))
            allowed = ("name", "category", "price", "unit", "starting",
                       "discount_pct", "description", "sort", "active")
            ints = {"price", "starting", "discount_pct", "sort", "active"}
            fields, vals = [], []
            for k in allowed:
                if k in data:
                    fields.append(f"{k}=?")
                    vals.append(int(data[k]) if k in ints else data[k])
            if not fields:
                return self._json({"error": "Nothing to update."}, 400)
            vals.append(sid)
            conn = db()
            conn.execute(f"UPDATE services SET {','.join(fields)} WHERE id=?", vals)
            conn.commit()
            conn.close()
            return self._json({"ok": True})

        m = re.match(r"^/api/admin/offers/(\d+)$", self.path)
        if m:
            oid = int(m.group(1))
            conn = db()
            if "active" in data and data.get("active"):
                conn.execute("UPDATE offers SET active=0")  # only one active
            allowed = ("name", "discount_pct", "note", "active")
            ints = {"discount_pct", "active"}
            fields, vals = [], []
            for k in allowed:
                if k in data:
                    fields.append(f"{k}=?")
                    vals.append(int(data[k]) if k in ints else data[k])
            if not fields:
                conn.close()
                return self._json({"error": "Nothing to update."}, 400)
            vals.append(oid)
            conn.execute(f"UPDATE offers SET {','.join(fields)} WHERE id=?", vals)
            conn.commit()
            conn.close()
            return self._json({"ok": True})

        return self._json({"error": "Not found"}, 404)

    # ───────────── API: DELETE ─────────────
    def api_delete(self):
        if not self._require_auth():
            return
        m = re.match(r"^/api/admin/enquiries/(\d+)$", self.path)
        if m:
            conn = db()
            conn.execute("DELETE FROM enquiries WHERE id=?", (int(m.group(1)),))
            conn.commit()
            conn.close()
            return self._json({"ok": True})
        m = re.match(r"^/api/admin/clients/(\d+)$", self.path)
        if m:
            conn = db()
            conn.execute("DELETE FROM clients WHERE id=?", (int(m.group(1)),))
            conn.commit()
            conn.close()
            return self._json({"ok": True})
        m = re.match(r"^/api/admin/offers/(\d+)$", self.path)
        if m:
            conn = db()
            conn.execute("DELETE FROM offers WHERE id=?", (int(m.group(1)),))
            conn.commit()
            conn.close()
            return self._json({"ok": True})
        return self._json({"error": "Not found"}, 404)


def main():
    init_db()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Evision Infoserve server running:")
    print(f"  Bound  ->  {HOST}:{PORT}")
    print(f"  Site   ->  http://localhost:{PORT}/")
    print(f"  Admin  ->  http://localhost:{PORT}/admin/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
