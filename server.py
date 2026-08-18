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

import base64
import html
import json
import os
import re
import sqlite3
import hashlib
import secrets
import smtplib
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import voice_booking as voice

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

# ── Optional instant alerts on your phone ─────────────────────────────────
# Email is too slow to call a lead back while they are still on the site, so a
# new enquiry can also push straight to a phone. Every channel is off until its
# env vars are set, and each one fails silently — an alert problem must never
# cost us the lead. See the README for the 2-minute setup of each.
#
#   Telegram (free, instant)   TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID
#   ntfy     (free, loud)      NTFY_TOPIC  [+ NTFY_SERVER, NTFY_PRIORITY]
#   Phone call (paid, rings)   TWILIO_SID + TWILIO_TOKEN + TWILIO_FROM + ALERT_PHONE
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC")
NTFY_PRIORITY = os.environ.get("NTFY_PRIORITY", "urgent")
TWILIO_SID = os.environ.get("TWILIO_SID")
TWILIO_TOKEN = os.environ.get("TWILIO_TOKEN")
TWILIO_FROM = os.environ.get("TWILIO_FROM")
ALERT_PHONE = os.environ.get("ALERT_PHONE", "+919311221517")   # who gets called
# Lead types that are NOT worth a phone alert (they still email + land in /admin/).
ALERT_SKIP_TYPES = {t.strip() for t in
                    (os.environ.get("ALERT_SKIP_TYPES", "newsletter")).split(",") if t.strip()}

# token -> {"email": str, "expires": float}
SESSIONS = {}


# ───────────────────────── helpers ─────────────────────────

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log(msg):
    """print() that can't take a request down. A Windows console is cp1252, so
    a spammer's Cyrillic name or a stray arrow would otherwise raise
    UnicodeEncodeError mid-response; under systemd (UTF-8) this is just print."""
    try:
        print(msg)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "ascii"
        print(msg.encode(enc, "replace").decode(enc, "replace"))


def slugify(text, fallback="post"):
    """URL-safe slug: lowercase, alnum + single hyphens."""
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:80] or fallback


def unique_slug(conn, base, exclude_id=None):
    """Ensure the slug is unique in the posts table (append -2, -3, … on clash)."""
    base = slugify(base)
    slug, n = base, 1
    while True:
        row = conn.execute("SELECT id FROM posts WHERE slug=?", (slug,)).fetchone()
        if not row or row["id"] == exclude_id:
            return slug
        n += 1
        slug = f"{base}-{n}"


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
            name TEXT DEFAULT '',
            role TEXT DEFAULT 'author',    -- 'admin' (can publish) | 'author' (drafts only)
            bio TEXT DEFAULT '',           -- author bio shown under their posts
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS enquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, email TEXT, phone TEXT, company TEXT, website TEXT,
            service TEXT, budget TEXT, message TEXT,
            type TEXT DEFAULT 'quote',
            source TEXT,
            status TEXT DEFAULT 'new',   -- 'new' | 'contacted' | 'converted' | 'closed' | 'spam'
            notes TEXT DEFAULT '',
            ip TEXT DEFAULT '',          -- sender IP (spam filtering / rate limits)
            ua TEXT DEFAULT '',          -- sender user-agent
            spam_score INTEGER DEFAULT 0,
            spam_reason TEXT DEFAULT '',
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
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT UNIQUE,   -- ElevenLabs call id; makes booking idempotent
            enquiry_id INTEGER,            -- the row this call created in enquiries
            name TEXT, email TEXT, phone TEXT, company TEXT,
            project_type TEXT, budget_band TEXT, notes TEXT DEFAULT '',
            start_at TEXT NOT NULL,        -- ISO 8601 with +05:30 offset
            duration_min INTEGER DEFAULT 30,
            event_id TEXT DEFAULT '',      -- Google Calendar event id
            meet_link TEXT DEFAULT '',
            lead_source TEXT DEFAULT '',
            status TEXT DEFAULT 'booked',  -- 'booked' | 'cancelled'
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
        CREATE TABLE IF NOT EXISTS testimonials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            role TEXT DEFAULT '',             -- e.g. 'Founder, NimbusKart'
            quote TEXT NOT NULL,
            photo TEXT DEFAULT '',            -- image URL/path (/uploads/.. or /assets/..)
            rating INTEGER DEFAULT 5,
            sort INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            client TEXT DEFAULT '',
            category TEXT DEFAULT '',
            image TEXT DEFAULT '',            -- cover image URL/path
            summary TEXT DEFAULT '',
            metric TEXT DEFAULT '',           -- headline result, e.g. '+212% organic'
            url TEXT DEFAULT '',              -- optional case-study / live link
            sort INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            excerpt TEXT DEFAULT '',          -- short summary for cards & meta fallback
            cover TEXT DEFAULT '',            -- hero/cover image URL/path
            body TEXT DEFAULT '',             -- article HTML (authored in the admin editor)
            tag TEXT DEFAULT '',              -- category label, e.g. 'AI Search'
            author TEXT DEFAULT '',
            author_role TEXT DEFAULT '',
            author_bio TEXT DEFAULT '',       -- short bio shown under the author on the post
            author_email TEXT DEFAULT '',     -- owning account (for author panel + ownership)
            read_min INTEGER DEFAULT 5,       -- estimated read time (minutes)
            meta_title TEXT DEFAULT '',       -- <title> override (falls back to title)
            meta_desc TEXT DEFAULT '',        -- meta description (falls back to excerpt)
            og_title TEXT DEFAULT '',         -- Open Graph title (falls back to meta_title/title)
            og_desc TEXT DEFAULT '',          -- Open Graph description (falls back to meta_desc/excerpt)
            og_image TEXT DEFAULT '',         -- Open Graph image (falls back to cover)
            status TEXT DEFAULT 'draft',      -- 'draft' | 'published'
            sort INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT DEFAULT '',
            published_at TEXT DEFAULT ''
        );
        """
    )
    conn.commit()
    # ── lightweight migrations: add columns to existing databases ──
    existing_cols = {r["name"] for r in c.execute("PRAGMA table_info(enquiries)").fetchall()}
    for col, ddl in (("consent", "consent INTEGER DEFAULT 0"),
                     ("marketing", "marketing INTEGER DEFAULT 0"),
                     # spam filtering: who sent it and why it was scored the way it was
                     ("ip", "ip TEXT DEFAULT ''"),
                     ("ua", "ua TEXT DEFAULT ''"),
                     ("spam_score", "spam_score INTEGER DEFAULT 0"),
                     ("spam_reason", "spam_reason TEXT DEFAULT ''")):
        if col not in existing_cols:
            c.execute(f"ALTER TABLE enquiries ADD COLUMN {ddl}")
    conn.commit()
    # Add author-role columns to older admins tables (roles + display name).
    admin_cols = {r["name"] for r in c.execute("PRAGMA table_info(admins)").fetchall()}
    for col, ddl in (("name", "name TEXT DEFAULT ''"),
                     ("role", "role TEXT DEFAULT 'author'"),
                     ("bio", "bio TEXT DEFAULT ''")):
        if col not in admin_cols:
            c.execute(f"ALTER TABLE admins ADD COLUMN {ddl}")
    # Track which account owns each post (author panel + publish gating) and the
    # author's short bio shown under the post.
    post_cols = {r["name"] for r in c.execute("PRAGMA table_info(posts)").fetchall()}
    if "author_email" not in post_cols:
        c.execute("ALTER TABLE posts ADD COLUMN author_email TEXT DEFAULT ''")
    if "author_bio" not in post_cols:
        c.execute("ALTER TABLE posts ADD COLUMN author_bio TEXT DEFAULT ''")
    conn.commit()
    # The main account is always an admin (can publish). Older DBs default new
    # role columns to 'author', so promote the main account back to admin, and
    # guarantee at least one admin exists.
    c.execute("UPDATE admins SET role='admin' WHERE email=?", (SEED_EMAIL.lower(),))
    c.execute("UPDATE admins SET name='Admin' WHERE email=? AND (name IS NULL OR name='')",
              (SEED_EMAIL.lower(),))
    if c.execute("SELECT COUNT(*) AS n FROM admins WHERE role='admin'").fetchone()["n"] == 0:
        first = c.execute("SELECT id FROM admins ORDER BY id LIMIT 1").fetchone()
        if first:
            c.execute("UPDATE admins SET role='admin' WHERE id=?", (first["id"],))
    conn.commit()
    # One-time data fix: rename the SEO service to match the rest of the site
    # (nav, services page). Only touches the row if it still has the original
    # seed label, so any custom name set in the admin panel is preserved.
    c.execute("UPDATE services SET name='SEO Services' WHERE slug='seo' AND name='SEO & AI Search'")
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
            "INSERT INTO admins (email, pw_hash, pw_salt, name, role, created_at) VALUES (?,?,?,?,?,?)",
            (SEED_EMAIL.lower(), h, s, "Admin", "admin", now_iso()),
        )
        conn.commit()
        print(f"  -> Seeded admin account: {SEED_EMAIL}  (password: {SEED_PASSWORD})")
        print("    Please change this password after your first login.")
    # Seed testimonials on first run (only if the table is empty).
    if c.execute("SELECT COUNT(*) AS n FROM testimonials").fetchone()["n"] == 0:
        for i, (name, role, quote, photo, rating) in enumerate(TESTIMONIALS_SEED):
            c.execute(
                """INSERT INTO testimonials (name,role,quote,photo,rating,sort,active,created_at)
                   VALUES (?,?,?,?,?,?,1,?)""",
                (name, role, quote, photo, rating, i, now_iso()),
            )
        conn.commit()
    # Seed portfolio on first run (only if the table is empty).
    if c.execute("SELECT COUNT(*) AS n FROM portfolio").fetchone()["n"] == 0:
        for i, (title, client, cat, image, summary, metric, url) in enumerate(PORTFOLIO_SEED):
            c.execute(
                """INSERT INTO portfolio (title,client,category,image,summary,metric,url,sort,active,created_at)
                   VALUES (?,?,?,?,?,?,?,?,1,?)""",
                (title, client, cat, image, summary, metric, url, i, now_iso()),
            )
        conn.commit()
    # Seed the first blog post on first run (only if the table is empty).
    if c.execute("SELECT COUNT(*) AS n FROM posts").fetchone()["n"] == 0:
        p = POST_SEED
        c.execute(
            """INSERT INTO posts
               (slug,title,excerpt,cover,body,tag,author,author_role,read_min,
                meta_title,meta_desc,og_title,og_desc,og_image,status,sort,
                created_at,updated_at,published_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,'published',0,?,?,?)""",
            (p["slug"], p["title"], p["excerpt"], p["cover"], p["body"], p["tag"],
             p["author"], p["author_role"], p["read_min"], p["meta_title"], p["meta_desc"],
             p["og_title"], p["og_desc"], p["og_image"], now_iso(), now_iso(), now_iso()),
        )
        conn.commit()
    # Seed the lead-magnet posts idempotently (INSERT OR IGNORE on the unique
    # slug). Runs every startup so they survive DB resets and are always live,
    # yet stay fully editable in the admin CMS. sort=10+ keeps them after the
    # first featured post but they publish immediately.
    for i, p in enumerate(LEAD_MAGNET_POSTS):
        c.execute(
            """INSERT OR IGNORE INTO posts
               (slug,title,excerpt,cover,body,tag,author,author_role,read_min,
                meta_title,meta_desc,og_title,og_desc,og_image,status,sort,
                created_at,updated_at,published_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,'published',?,?,?,?)""",
            (p["slug"], p["title"], p["excerpt"], p.get("cover", ""), p["body"], p["tag"],
             p["author"], p["author_role"], p["read_min"], p["meta_title"], p["meta_desc"],
             p["og_title"], p["og_desc"], p.get("og_image", ""), 10 + i,
             now_iso(), now_iso(), now_iso()),
        )
    conn.commit()
    # The consent label is baked into each post's stored body, so the INSERT OR
    # IGNORE above can't refresh it on posts that already exist. Patch just that
    # snippet in place — idempotent (only rows still carrying the old wording
    # match) and surgical, so admin edits elsewhere in the body survive.
    c.execute("UPDATE posts SET body = REPLACE(body, ?, ?) WHERE instr(body, ?) > 0",
              (LM_CONSENT_OLD, LM_CONSENT, LM_CONSENT_OLD))
    conn.commit()
    # Seed extra portfolio items (web design/dev + student projects) idempotently
    # — only inserts an item if no row with the same title exists, so it's safe
    # to run repeatedly and won't duplicate or clobber admin-managed items.
    for i, (title, client, cat, image, summary, metric, url) in enumerate(PORTFOLIO_EXTRA):
        exists = c.execute("SELECT 1 FROM portfolio WHERE title=? LIMIT 1", (title,)).fetchone()
        if not exists:
            c.execute(
                """INSERT INTO portfolio (title,client,category,image,summary,metric,url,sort,active,created_at)
                   VALUES (?,?,?,?,?,?,?,?,1,?)""",
                (title, client, cat, image, summary, metric, url, -100 + i, now_iso()),
            )
    conn.commit()
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


def account_by_email(email):
    """Full admins row (dict) for an email, or None. Used for role checks."""
    if not email:
        return None
    conn = db()
    row = conn.execute("SELECT * FROM admins WHERE email=?", (email,)).fetchone()
    conn.close()
    return dict(row) if row else None


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# ─────────────────── spam filtering for the public enquiry form ────────────
# Bots scrape the contact form and post junk leads: invented names, throwaway
# mailboxes, guest-post / backlink outreach, the same phone number reused under
# five different identities. Nothing is silently deleted — every submission is
# SCORED, and anything at or above SPAM_THRESHOLD is saved with status='spam'
# so it stays out of the inbox, out of the "new" badge and out of the
# notification email, while remaining reviewable (and restorable) in /admin/.
#
# Tunable via env vars; the defaults are deliberately conservative so a real
# lead needs to trip several rules at once before it is quarantined.
SPAM_THRESHOLD = int(os.environ.get("SPAM_THRESHOLD", "60"))
SPAM_RETENTION_DAYS = int(os.environ.get("SPAM_RETENTION_DAYS", "30"))
# Hard cap per IP. Set well above anything a real visitor does (mobile networks
# put many users behind one IP, so this is a flood stop, not a spam filter).
RATE_LIMIT_HOUR = int(os.environ.get("ENQUIRY_RATE_HOUR", "12"))
RATE_LIMIT_DAY = int(os.environ.get("ENQUIRY_RATE_DAY", "40"))

# Throwaway mailbox providers + domains that have only ever sent us outreach
# spam. Extend without touching code: SPAM_DOMAINS="foo.com,bar.net"
SPAM_DOMAINS = {
    # domains seen in real spam on this site
    "jmailservice.com", "guestpostmate.com", "sendproud.com",
    # common disposable / burner providers
    "mailinator.com", "guerrillamail.com", "sharklasers.com", "yopmail.com",
    "10minutemail.com", "tempmail.com", "temp-mail.org", "trashmail.com",
    "getnada.com", "maildrop.cc", "dispostable.com", "fakeinbox.com",
    "throwawaymail.com", "emailondeck.com", "moakt.com", "mailnesia.com",
    "spam4.me", "tempr.email", "mytemp.email", "inboxkitten.com",
    "mail-temp.com", "byom.de", "grr.la", "einrot.com", "cuvox.de",
}
SPAM_DOMAINS |= {d.strip().lower() for d in
                 (os.environ.get("SPAM_DOMAINS") or "").split(",") if d.strip()}

# Phrases that show up in link-building / guest-post outreach and classic junk,
# but effectively never in a genuine "I need SEO for my business" enquiry.
SPAM_PHRASES = [
    "guest post", "guest posting site", "sponsored post", "paid post",
    "link insertion", "link exchange", "dofollow", "do-follow", "backlink",
    "high da", "da pa", "da 50", "buy links", "sell links", "link building service",
    "seo reseller", "outreach service", "casino", "betting", "gambling", "escort",
    "bitcoin", "crypto investment", "forex", "payday loan", "viagra", "porn",
    "unsubscribe", "bulk email", "mass mailing", "cheap traffic", "buy followers",
    "make money online", "work from home opportunity", "click here now",
]

# Automated clients that are never a real visitor's browser.
BOT_UA_RE = re.compile(
    r"python-requests|python-urllib|curl/|wget|scrapy|okhttp|go-http-client|"
    r"libwww-perl|java/|axios/|httpclient|node-fetch|postman", re.I)

# Scripts a Greater-Noida marketing site never receives genuine enquiries in.
FOREIGN_SCRIPT_RE = re.compile(r"[Ѐ-ӿ一-鿿぀-ヿ؀-ۿ]")
URL_RE = re.compile(r"(https?://|www\.)", re.I)


def _iso_ago(**kw):
    """ISO timestamp N hours/days ago, comparable against created_at strings."""
    from datetime import timedelta
    return (datetime.now(timezone.utc) - timedelta(**kw)).isoformat(timespec="seconds")


def digits_only(s):
    return re.sub(r"\D", "", s or "")


def score_enquiry(rec, conn, ip="", ua="", origin="", referer="", elapsed_ms=None,
                  honeypot=""):
    """Weighted spam score for one submission.

    Returns (score, [reasons]). No single soft signal can quarantine a lead —
    a genuine enquiry has to trip several rules before it crosses the
    threshold. Hard signals (honeypot, blocked domain, bot user-agent) score
    100 on their own because a human browser cannot produce them.
    """
    score, why = 0, []

    def hit(points, reason):
        nonlocal score
        score += points
        why.append(reason)

    text = " ".join(filter(None, [rec.get("message"), rec.get("company"),
                                  rec.get("name"), rec.get("website")])).lower()
    email = (rec.get("email") or "").lower()
    domain = email.split("@")[-1] if "@" in email else ""

    # ── hard signals ──
    if honeypot.strip():
        hit(100, "honeypot field filled")
    if domain and domain in SPAM_DOMAINS:
        hit(100, f"blocked email domain ({domain})")
    if ua and BOT_UA_RE.search(ua):
        hit(100, "automated user-agent")
    elif not ua:
        hit(50, "no user-agent")

    # ── request-shape signals ──
    # A real browser submitting our own form always sends Origin or Referer
    # from this site; a script POSTing straight at /api/enquiry usually sends
    # neither.
    host = (SITE_URL.split("//")[-1] or "").lower()
    src = (origin or referer or "").lower()
    if not src:
        hit(45, "no Origin/Referer header")
    elif host and host not in src and "localhost" not in src and "127.0.0.1" not in src:
        hit(60, "submitted from another site")
    if elapsed_ms is not None and elapsed_ms < 3000:
        hit(60, f"form completed in {elapsed_ms / 1000:.1f}s")

    # ── content signals ──
    for p in SPAM_PHRASES:
        if p in text:
            hit(50, f"spam phrase: '{p}'")
            break
    links = len(re.findall(URL_RE, rec.get("message") or ""))
    if links:
        hit(40 if links == 1 else 60, f"{links} link(s) in the message")
    if FOREIGN_SCRIPT_RE.search(text):
        hit(30, "non-Latin script in the text")
    if len(rec.get("name") or "") > 60:
        hit(30, "absurdly long name")
    # Generated identities habitually put the person's own name in Company.
    name_l = (rec.get("name") or "").strip().lower()
    if name_l and name_l == (rec.get("company") or "").strip().lower():
        hit(35, "company name is identical to the person's name")
    # contact.html is the only source of type='quote' and it requires a message,
    # so a quote with none was not sent through the real form.
    if rec.get("type") == "quote" and not (rec.get("message") or "").strip():
        hit(35, "quote request with an empty message")

    # ── history signals (needs the DB) ──
    # These target the bot pattern specifically — many invented identities
    # behind one connection — rather than volume alone, because a genuinely
    # keen visitor may well grab three lead magnets and then request a quote.
    phone = digits_only(rec.get("phone"))
    try:
        if phone and len(phone) >= 8:
            others = conn.execute(
                "SELECT COUNT(DISTINCT lower(email)) n FROM enquiries "
                "WHERE replace(replace(replace(phone,' ',''),'-',''),'+','') LIKE ? "
                "  AND created_at > ? AND lower(email) <> ? AND email <> ''",
                (f"%{phone[-10:]}", _iso_ago(days=30), email),
            ).fetchone()["n"]
            if others >= 1:
                hit(45, f"phone already used by {others} other sender(s)")

        if ip:
            recent = conn.execute(
                "SELECT lower(email) e, status, message, created_at FROM enquiries "
                "WHERE ip=? AND created_at > ?", (ip, _iso_ago(hours=24)),
            ).fetchall()
            hour_ago = _iso_ago(hours=1)
            last_hour = [r for r in recent if r["created_at"] > hour_ago]
            # Same person, more forms = fine. Several different senders from one
            # connection in an hour = a script cycling through fake identities.
            identities = {r["e"] for r in last_hour if r["e"]} - {email}
            if len(identities) >= 2:
                hit(60, f"{len(identities) + 1} different senders from this IP within an hour")
            elif len(last_hour) >= 6:
                hit(40, f"{len(last_hour)} submissions from this IP within an hour")
            if any(r["status"] == "spam" for r in recent):
                hit(50, "this IP already sent spam in the last 24h")
            # Byte-identical resubmission (bots replay the same payload).
            msg = (rec.get("message") or "").strip()
            if email and any(r["e"] == email and (r["message"] or "").strip() == msg
                             for r in recent):
                hit(30, "identical submission already received today")
    except sqlite3.Error:
        pass  # scoring must never break the form

    return score, why


def enquiry_rate_limited(conn, ip):
    """True when this IP has flooded the form — the request is refused outright
    (nothing stored), which keeps a bot loop from filling the database."""
    if not ip:
        return False
    try:
        hour = conn.execute(
            "SELECT COUNT(*) n FROM enquiries WHERE ip=? AND created_at > ?",
            (ip, _iso_ago(hours=1))).fetchone()["n"]
        day = conn.execute(
            "SELECT COUNT(*) n FROM enquiries WHERE ip=? AND created_at > ?",
            (ip, _iso_ago(days=1))).fetchone()["n"]
    except sqlite3.Error:
        return False
    return hour >= RATE_LIMIT_HOUR or day >= RATE_LIMIT_DAY


def purge_old_spam(conn):
    """Drop quarantined spam older than the retention window, so the table does
    not grow forever. Real enquiries are never touched."""
    try:
        conn.execute("DELETE FROM enquiries WHERE status='spam' AND created_at < ?",
                     (_iso_ago(days=SPAM_RETENTION_DAYS),))
        conn.commit()
    except sqlite3.Error:
        pass


# ── Clean / hierarchical URLs ──────────────────────────────────────────────
# Map each file to its pretty URL. The server serves the file at the clean URL
# and 301-redirects the old .html URL to it.
_SEO_CHILDREN = ["ai-seo", "llm-optimization", "agentic-ai-seo", "enterprise-seo",
                 "ecommerce-seo", "technical-seo", "local-seo", "multilingual-seo",
                 "link-building", "white-label-seo", "seo-audit", "industry-seo"]
_CONTENT_CHILDREN = ["content-writing", "guest-posting", "digital-pr"]
FILE_TO_CLEAN = {
    "index.html": "/",
    "web-design.html": "/services/web-design",
    "web-development.html": "/services/web-development",
    "seo.html": "/services/seo",
    "content-marketing.html": "/services/content-marketing",
    "social-media.html": "/services/social-media",
    "ppc.html": "/services/ppc",
    "orm.html": "/services/orm",
    "ai-marketing.html": "/services/ai-digital-marketing",
    "affiliate-marketing.html": "/services/affiliate-marketing",
    "youtube-marketing.html": "/services/youtube-marketing",
    "email-marketing.html": "/services/email-marketing",
    "mobile-app-marketing.html": "/services/mobile-app-marketing",
    "pricing.html": "/pricing", "about.html": "/about", "blog.html": "/blog",
    "website-scorecard.html": "/website-health-check",
    "contact.html": "/contact", "portfolio.html": "/portfolio", "clients.html": "/clients",
    "career.html": "/career", "testimonials.html": "/testimonials",
    "privacy-policy.html": "/privacy-policy", "refund-policy.html": "/refund-policy",
    "terms.html": "/terms", "service.html": "/service",
    "services.html": "/services",
}
for _c in _SEO_CHILDREN:
    FILE_TO_CLEAN[_c + ".html"] = "/services/seo/" + _c
for _c in _CONTENT_CHILDREN:
    FILE_TO_CLEAN[_c + ".html"] = "/services/content-marketing/" + _c
CLEAN_TO_FILE = {v: k for k, v in FILE_TO_CLEAN.items()}

# Services seeded on first run. Prices are PLACEHOLDERS — edit them in the admin
# panel (Pricing tab). (slug, name, category, price, unit, starting, description)
SERVICES_SEED = [
    # ── SEO ──
    ("seo", "SEO Services", "SEO", 15000, "/mo", 1, "Full-funnel SEO engineered to rank on Google and get cited by AI engines."),
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
    ("industry-seo", "Industry-Based SEO", "SEO", 22000, "/mo", 1, "Customised SEO for healthcare, education, travel, ecommerce, finance and more."),
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
    ("affiliate-marketing", "Affiliate Marketing", "Other Services", 15000, "/mo", 1, "Performance-based programs that drive qualified traffic, leads and sales."),
    ("youtube-marketing", "YouTube Video Marketing", "Other Services", 16000, "/mo", 1, "Channel management, YouTube SEO and video strategy that grow leads."),
    ("email-marketing", "Email Marketing", "Other Services", 12000, "/mo", 1, "Targeted campaigns, automation and lead nurturing with measurable ROI."),
    ("mobile-app-marketing", "Mobile App Marketing", "Other Services", 18000, "/mo", 1, "ASO, app CRO and growth campaigns that drive downloads and retention."),
]
CATEGORY_ORDER = ["SEO", "Content Marketing", "Other Services"]

# Client testimonials seeded on first run. Edit/add/remove from the admin panel
# (Testimonials tab). (name, role, quote, photo, rating)
TESTIMONIALS_SEED = [
    ("Rahul Mehta", "Founder, NimbusKart",
     "We went from page 3 to the featured snippet — and started showing up inside ChatGPT answers for our category. Leads doubled in a quarter.",
     "/assets/clients/rahul-mehta.jpg", 5),
    ("Sneha Kapoor", "Head of Growth, FinlyApp",
     "The most structured agency we've worked with. Their schema and answer-block approach is genuinely built for how people search now.",
     "/assets/clients/sneha-kapoor.jpg", 5),
    ("Ankit Sharma", "Founder, SaaS startup",
     "Organic became our biggest channel within two quarters. Clear reporting, no jargon, and real results we could take to the board.",
     "/assets/clients/ankit-sharma.jpg", 5),
    ("Priya Nair", "Director, D2C brand",
     "They fixed technical issues three agencies before them had missed. Category traffic and revenue are both up double digits.",
     "/assets/clients/priya-nair.jpg", 5),
    ("Dr. Arjun Rao", "Owner, multi-clinic group",
     "We're #1 in the local map pack now and the phone hasn't stopped ringing. Brilliant local SEO and a team that actually responds.",
     "/assets/clients/arjun-rao.jpg", 5),
    ("Meera Iyer", "Marketing Head, EdTech",
     "The only team that truly understands AI search. Within months we were being cited in ChatGPT and Perplexity for our niche.",
     "/assets/clients/meera-iyer.jpg", 5),
]

# Portfolio / case studies seeded on first run. Manage from the admin panel
# (Portfolio tab). (title, client, category, image, summary, metric, url)
PORTFOLIO_SEED = [
    ("SaaS organic growth engine", "B2B SaaS", "SEO", "/assets/portfolio/saas.jpg",
     "Technical fixes plus topic clusters doubled non-brand organic traffic in seven months.", "+212% organic", ""),
    ("Ecommerce category SEO", "D2C Ecommerce", "Ecommerce SEO", "/assets/portfolio/ecommerce.jpg",
     "Category-page optimisation grew revenue from organic search 64% year on year.", "+64% revenue", ""),
    ("Local services map-pack #1", "Multi-location services", "Local SEO", "/assets/portfolio/local.jpg",
     "From page two to the top of the local pack across nine service areas.", "#1 map pack", ""),
    ("Cited by AI engines", "B2B technology", "AI SEO / GEO", "/assets/portfolio/ai.jpg",
     "Became a cited source in ChatGPT and Perplexity for core category queries.", "AI-cited", ""),
    ("D2C digital PR campaign", "Consumer brand", "Digital PR", "/assets/portfolio/pr.jpg",
     "A data-led study earned 40+ pieces of coverage and high-authority links.", "40+ links", ""),
    ("Lead-gen paid restructure", "Lead generation", "PPC & Paid Ads", "/assets/portfolio/ppc.jpg",
     "Restructured paid campaigns to cut cost-per-lead while scaling volume.", "−38% CPL", ""),
]

# Web design / development + student-project work. Seeded idempotently (by
# title) so the portfolio leads with build work, not just SEO case studies.
# image='' → the portfolio page renders a styled browser-mockup placeholder.
PORTFOLIO_EXTRA = [
    # ── Live client websites (real screenshots in /assets/portfolio) ──
    ("Astro Annie — Astrology & Tarot", "Astro Annie · Astrologer", "Web Design · Astrology",
     "/assets/portfolio/astro-annie.jpg",
     "A design-led astrology & tarot website with an animated three-card reading experience and online booking.",
     "Animated UI", "https://astroanjilina.com/"),
    ("Aurum & Co. — Real Estate", "Aurum & Co. · Noida", "Web Development · Real Estate",
     "/assets/portfolio/aurum-co.jpg",
     "A premium real-estate consulting site with verified property listings, live activity stats and consultation booking.",
     "Listings portal", "https://ivory-llama-587747.hostingersite.com/"),
    ("Sri Siddhivinayak Enterprises", "Sri Siddhivinayak · Dhanbad", "Web Development · IT Services",
     "/assets/portfolio/sri-siddhivinayak.jpg",
     "A conversion-focused website for an IT, CCTV & AMC company — services, products and a live service dashboard.",
     "Live dashboard", "https://papayawhip-echidna-100598.hostingersite.com/"),
    ("Modern D2C brand website", "D2C skincare", "Web Design", "",
     "A premium, conversion-focused storefront designed and built from scratch — fast, mobile-first and SEO-ready.", "98/100 speed", ""),
    ("Real-estate listing platform", "Property developer", "Web Development", "",
     "A custom property portal with search, filters, map view and enquiry capture, built to scale.", "3.2s → 0.9s", ""),
    ("Restaurant online ordering", "Multi-outlet F&B", "E-commerce", "",
     "Online ordering with menu management and WhatsApp checkout across multiple outlets.", "+140% orders", ""),
    ("Corporate website revamp", "B2B services", "Web Design", "",
     "A dated corporate site redesigned for speed, mobile and lead generation — without losing rankings.", "+68% leads", ""),
    ("SaaS marketing site + CMS", "B2B SaaS", "Web Development", "",
     "A headless marketing site with a self-serve CMS so the team ships pages without a developer.", "Next.js", ""),
    ("College fest event portal", "Final-year student", "Student Project", "",
     "An event registration and pass-generation system built with the student, documented and deployed live for the viva.", "Live demo", ""),
    ("Job & internship portal", "Final-year student", "Student Project", "",
     "A full-stack MERN job portal with resume upload and an admin dashboard — report and viva ready.", "MERN stack", ""),
    ("Doctor appointment system", "Final-year student", "Student Project", "",
     "A Django appointment-booking project with role-based access, reports and clean documentation.", "Django", ""),
]

# First blog post — seeded once so the Blog is never empty. Fully editable in admin.
POST_SEED = {
    "slug": "geo-vs-seo-ai-search-2026",
    "title": "GEO vs SEO: How AI Search Is Changing the Way Brands Get Found in 2026",
    "tag": "AI Search",
    "author": "Priya Sharma",
    "author_role": "Head of SEO Strategy · Evision Infoserve",
    "read_min": 11,
    "excerpt": "A practical guide to Generative Engine Optimization (GEO) and how it differs "
               "from traditional SEO — and what to do so your brand gets cited by ChatGPT, "
               "Gemini and Perplexity.",
    "cover": "",
    "meta_title": "GEO vs SEO: How AI Search Is Changing How Brands Get Found in 2026 | Evision Infoserve",
    "meta_desc": "A practical guide to Generative Engine Optimization (GEO) and how it differs from "
                 "traditional SEO — and what to do so your brand gets cited by ChatGPT, Gemini and Perplexity.",
    "og_title": "GEO vs SEO: How AI Search Is Changing How Brands Get Found in 2026",
    "og_desc": "SEO gets you ranked; GEO gets you cited inside AI answers. Here's the 2026 visibility playbook.",
    "og_image": "",
    "body": """<h2 id="shift">The search box is no longer the destination</h2>
<p>For two decades, the job was simple: rank in the top results and earn the click. But the interface of search has changed. Google AI Overviews, ChatGPT, Gemini and Perplexity increasingly answer the question <em>on the spot</em> — and the user never visits a website at all.</p>
<p>That doesn't make discoverability less important. It makes <strong>where</strong> you're discovered different. The new question isn't only "do I rank?" — it's "<strong>am I the source the AI trusts and names?</strong>"</p>
<h2 id="difference">SEO vs GEO: what's actually different</h2>
<p>It helps to think of them as two layers of the same strategy rather than competitors. <strong>SEO</strong> optimises for ranked links and clicks. <strong>GEO</strong> optimises for inclusion and citation inside generative answers.</p>
<h3>Where they overlap</h3>
<p>The good news: most of the work compounds. Fast, crawlable, well-structured pages with strong topical authority help you both rank on Google and get pulled into an AI summary.</p>
<ul>
<li>Clean heading hierarchy — one H1, ordered H2–H6.</li>
<li>Structured data (JSON-LD) so machines understand entities.</li>
<li>Genuine expertise and citations — Google's E-E-A-T and an AI's trust signals are close cousins.</li>
</ul>
<h3>Where they diverge</h3>
<p>GEO rewards <strong>contextual completeness</strong> over keyword density. AI engines lift self-contained passages, so each section should make sense on its own. Original data, clear definitions and comparison tables are disproportionately valuable — they're exactly what a model reaches for.</p>
<blockquote>"Optimise for the question, not just the keyword. The brands that define the answer become the answer."</blockquote>
<h2 id="playbook">A practical GEO playbook</h2>
<p>Here's the approach we ship on every Evision Infoserve build — a repeatable system, not a one-off trick.</p>
<h3>1. Lead with the answer</h3>
<p>Put a 40–60 word direct answer near the top of every page. This single move wins featured snippets, voice answers and AI answer boxes at once.</p>
<h3>2. Build topical authority in clusters</h3>
<p>Pillar pages supported by interlinked articles signal depth. AI engines favour sources that demonstrably own a topic, not pages that mention it once.</p>
<h3>3. Make your entities consistent</h3>
<p>Keep your brand name, services and location identical across your site, Google Business Profile and directories. Consistency is how a model becomes confident enough to name you.</p>
<h3>4. Open the door for AI crawlers</h3>
<p>An llms.txt file plus access for GPTBot, ClaudeBot and PerplexityBot tells the engines where your best, most citable content lives.</p>""",
}


# ── Lead-magnet blog posts ─────────────────────────────────────────────────
# Five gated-content articles. Each embeds an inline lead-capture form
# (.lm-form, wired up in assets/site.js) that posts to /api/enquiry with
# type='lead-magnet', so downloads land in the admin panel as enquiries.
# Seeded idempotently by slug on every startup, so they survive DB resets and
# stay editable in the admin CMS.

# The consent label rendered inside every lead-magnet card. Kept as constants so
# init_db() can refresh the copy baked into already-seeded posts (see below).
LM_CONSENT_OLD = (
    '<label class="lm-consent"><input type="checkbox" name="consent"> '
    'Email me this resource &amp; the occasional tip. I agree to the '
    '<a href="/privacy-policy.html">privacy policy</a>.</label>'
)
LM_CONSENT = (
    '<label class="lm-consent"><input type="checkbox" name="consent"> '
    '<span>I authorize <b>Evision Infoserve</b> to send me this resource and related '
    'notifications via <b>SMS, RCS, Call, Email &amp; WhatsApp</b> &mdash; including on a '
    'number registered with DND/NCPR &mdash; and I accept the '
    '<a href="/terms.html" target="_blank" rel="noopener">Terms &amp; Conditions</a> and '
    '<a href="/privacy-policy.html" target="_blank" rel="noopener">Privacy Policy</a>.</span></label>'
)


def _lm(magnet, headline, sub, benes, cta, slug):
    """Return the HTML for an inline lead-magnet capture card."""
    lis = "".join(
        f'<li><i data-lucide="check-circle-2" class="ic"></i><span>{b}</span></li>' for b in benes)
    return (
        '<div class="lead-magnet"><div class="lm-inner">'
        '<div class="lm-copy">'
        '<span class="lm-badge"><i data-lucide="download"></i> Free download</span>'
        f'<h3>{headline}</h3><p>{sub}</p>'
        f'<ul class="lm-benes">{lis}</ul>'
        '</div>'
        f'<form class="lm-form" data-magnet="{html.escape(magnet, quote=True)}" data-source="{slug}">'
        '<input type="text" name="name" placeholder="Full name *" autocomplete="name">'
        '<input type="email" name="email" placeholder="Email *" autocomplete="email">'
        '<input type="tel" name="phone" placeholder="Phone / WhatsApp *" autocomplete="tel">'
        + LM_CONSENT +
        '<div class="lm-msg"></div>'
        f'<button type="submit" class="btn btn-primary btn-block">{cta} '
        '<i data-lucide="arrow-right" class="ic"></i></button>'
        '</form></div></div>'
    )


LEAD_MAGNET_POSTS = [
    {
        "slug": "web-development-project-ideas-for-students-2026",
        "title": "50 Web Development Project Ideas for Final-Year Students (2026)",
        "tag": "Student Projects",
        "author": "Evision Infoserve",
        "author_role": "Web Development Studio · Greater Noida",
        "read_min": 9,
        "excerpt": "A curated list of final-year web development project ideas across beginner, "
                   "intermediate and advanced levels — with the right tech stack for each and a free downloadable idea pack.",
        "cover": "",
        "meta_title": "50 Web Development Project Ideas for Final-Year Students (2026) | Evision Infoserve",
        "meta_desc": "Final-year web development project ideas for students — beginner to advanced, with tech "
                     "stacks, features and a free downloadable idea pack. We also help students build their projects.",
        "og_title": "50 Web Development Project Ideas for Final-Year Students (2026)",
        "og_desc": "Beginner to advanced final-year web dev project ideas — with tech stacks and a free idea pack.",
        "body": (
            '<p>Choosing the right final-year project decides how much you learn — and how good your resume looks. '
            'The best student web development projects solve a real problem, use a modern stack, and are small enough to actually finish. '
            'This guide gives you 50 ideas grouped by difficulty, the tech to build each one, and a free downloadable pack with the full list, feature checklists and a report structure.</p>'
            '<h2 id="how-to-choose">How to pick a project that scores well</h2>'
            '<p>Examiners reward a working demo, clean code and a clear problem statement. Pick something you can host live, explain in a viva, and extend if you have time. Avoid ideas that are either trivial (a static portfolio) or impossibly large (a full social network).</p>'
            '<ul>'
            '<li><strong>Solves a real problem</strong> — something you or your college actually needs.</li>'
            '<li><strong>Has a database</strong> — CRUD, auth and real data beat static pages.</li>'
            '<li><strong>Is demoable</strong> — deploy it so the panel can click through a live URL.</li>'
            '</ul>'
            '<h2 id="beginner">Beginner projects (HTML, CSS, JS + a simple backend)</h2>'
            '<ul>'
            '<li>College event registration &amp; pass generator</li>'
            '<li>Personal finance / expense tracker</li>'
            '<li>Notes &amp; to-do app with login</li>'
            '<li>Recipe finder using a public API</li>'
            '<li>Weather + air-quality dashboard</li>'
            '<li>Quiz app with a scoreboard</li>'
            '</ul>'
            '<h2 id="intermediate">Intermediate projects (React/Node or Django)</h2>'
            '<ul>'
            '<li>Job / internship portal with resume upload</li>'
            '<li>E-commerce store with cart and payment sandbox</li>'
            '<li>Blogging platform with an admin CMS</li>'
            '<li>Hostel / library management system</li>'
            '<li>Doctor appointment booking system</li>'
            '<li>Real-time chat app with sockets</li>'
            '</ul>'
            '<h2 id="advanced">Advanced projects (full-stack + something extra)</h2>'
            '<ul>'
            '<li>AI resume analyzer / ATS score checker</li>'
            '<li>Learning management system (LMS) with video</li>'
            '<li>Multi-vendor marketplace with dashboards</li>'
            '<li>Crowdfunding / donation platform</li>'
            '<li>SaaS analytics dashboard with charts</li>'
            '<li>AI chatbot for a college website</li>'
            '</ul>'
            + _lm(
                "50 Web Dev Project Ideas Pack (PDF)",
                "Get all 50 project ideas — free",
                "A ready-to-use PDF with the full list, recommended tech stack for each, feature checklists and a project-report structure your panel will love.",
                ["All 50 ideas, sorted by difficulty",
                 "Tech stack + feature list for each",
                 "Report + viva-preparation structure"],
                "Send me the idea pack",
                "web-development-project-ideas-for-students-2026",
            ) +
            '<h2 id="we-help">Need help building yours?</h2>'
            '<p>We help students turn any of these ideas into a finished, deployed project — with clean code you can understand and defend, proper documentation and a live demo link. Whether you want full development, guidance, or just a code review before submission, we can help. Grab the idea pack above and our team will reach out to see if you need a hand.</p>'
        ),
    },
    {
        "slug": "final-year-project-checklist-report-viva-ready",
        "title": "The Final-Year Project Checklist: Report & Viva Ready",
        "tag": "Student Projects",
        "author": "Evision Infoserve",
        "author_role": "Web Development Studio · Greater Noida",
        "read_min": 8,
        "excerpt": "Everything your final-year web project needs before submission — from problem statement to "
                   "deployment, documentation and viva prep. Download the full printable checklist.",
        "cover": "",
        "meta_title": "Final-Year Project Checklist (Report + Viva Ready) | Evision Infoserve",
        "meta_desc": "A complete checklist for final-year web development projects — SRS, database design, "
                     "deployment, report and viva prep. Free printable download. We also build student projects.",
        "og_title": "The Final-Year Project Checklist: Report & Viva Ready",
        "og_desc": "From problem statement to viva prep — the complete student project checklist, free.",
        "body": (
            '<p>Most marks are lost not on the code, but on the things around it — a vague problem statement, a thin report, a demo that breaks on the day. '
            'This checklist walks through every stage of a final-year web development project so nothing slips. Download the printable version and tick your way to submission.</p>'
            '<h2 id="planning">1. Planning &amp; documentation</h2>'
            '<ul>'
            '<li>Clear problem statement and objective (one paragraph)</li>'
            '<li>Scope: what is and is not included</li>'
            '<li>Software Requirements Specification (SRS)</li>'
            '<li>Technology stack justification</li>'
            '</ul>'
            '<h2 id="design">2. Design</h2>'
            '<ul>'
            '<li>ER diagram / database schema</li>'
            '<li>Use-case and data-flow diagrams (DFD)</li>'
            '<li>Wireframes for the key screens</li>'
            '</ul>'
            '<h2 id="build">3. Build &amp; test</h2>'
            '<ul>'
            '<li>Authentication and role-based access</li>'
            '<li>CRUD for every core entity</li>'
            '<li>Input validation and error handling</li>'
            '<li>Responsive on mobile and desktop</li>'
            '<li>A basic test pass on every feature</li>'
            '</ul>'
            '<h2 id="deploy">4. Deploy &amp; demo</h2>'
            '<ul>'
            '<li>Live hosted URL (so the panel can click it)</li>'
            '<li>Seed data so the demo looks real</li>'
            '<li>A backup plan if the internet fails (local + video)</li>'
            '</ul>'
            + _lm(
                "Final-Year Project Checklist (PDF)",
                "Download the printable checklist",
                "The complete, stage-by-stage checklist — planning, SRS, database design, build, deployment, report and viva questions — in one printable PDF.",
                ["Every stage from idea to viva",
                 "Report chapter-by-chapter outline",
                 "20 common viva questions to prepare"],
                "Send me the checklist",
                "final-year-project-checklist-report-viva-ready",
            ) +
            '<h2 id="report">5. Report &amp; viva</h2>'
            '<p>Your report should mirror your build: introduction, literature/existing-system review, requirements, design, implementation, testing, screenshots, conclusion and future scope. For the viva, be ready to explain <em>why</em> you chose your stack, how your database is structured, and one thing you would improve with more time.</p>'
            '<p><strong>Stuck or short on time?</strong> We help students finish, polish and deploy their web projects — with documentation and a demo that holds up in front of the panel. Download the checklist and we\'ll check in to see if you need support.</p>'
        ),
    },
    {
        "slug": "website-launch-checklist-40-point",
        "title": "Website Launch Checklist: 40 Things to Check Before You Go Live",
        "tag": "Web Development",
        "author": "Evision Infoserve",
        "author_role": "Web Design & Development · Greater Noida",
        "read_min": 7,
        "excerpt": "Don't launch a website with broken links, missing schema or a slow mobile score. "
                   "This 40-point pre-launch checklist covers performance, SEO, security and content. Free download.",
        "cover": "",
        "meta_title": "Website Launch Checklist: 40 Things to Check Before Go-Live | Evision Infoserve",
        "meta_desc": "A 40-point website launch checklist — performance, SEO, security, analytics and content — "
                     "so your site goes live clean and ready to rank. Free downloadable PDF.",
        "og_title": "Website Launch Checklist: 40 Things to Check Before You Go Live",
        "og_desc": "Performance, SEO, security and content — the 40-point pre-launch checklist, free.",
        "body": (
            '<p>Launch day is the worst time to discover a broken contact form or a 40/100 mobile score. A pre-launch checklist turns a stressful go-live into a calm one. '
            'Here are the essentials we run on every Evision Infoserve build before it ships — grab the full 40-point version below.</p>'
            '<h2 id="performance">Performance &amp; Core Web Vitals</h2>'
            '<ul>'
            '<li>Images compressed and lazy-loaded</li>'
            '<li>Largest Contentful Paint under 2.5s on mobile</li>'
            '<li>No layout shift (CLS) on load</li>'
            '<li>Caching and a CDN enabled</li>'
            '</ul>'
            '<h2 id="seo">SEO &amp; structured data</h2>'
            '<ul>'
            '<li>Unique title and meta description on every page</li>'
            '<li>One H1 per page, ordered headings</li>'
            '<li>JSON-LD schema (Organization, WebSite, Breadcrumb)</li>'
            '<li>XML sitemap and robots.txt live</li>'
            '<li>Descriptive, keyword-aware image alt text</li>'
            '</ul>'
            '<h2 id="security">Security &amp; reliability</h2>'
            '<ul>'
            '<li>SSL certificate and HTTPS redirect</li>'
            '<li>Forms protected against spam</li>'
            '<li>Automated backups configured</li>'
            '<li>404 page and broken-link check</li>'
            '</ul>'
            + _lm(
                "40-Point Website Launch Checklist (PDF)",
                "Get the full 40-point checklist",
                "The complete pre-launch checklist — performance, SEO, security, analytics, accessibility and content — so nothing gets missed on go-live day.",
                ["Performance, SEO, security &amp; content",
                 "Printable — tick as you go",
                 "The exact list our team uses"],
                "Send me the checklist",
                "website-launch-checklist-40-point",
            ) +
            '<h2 id="analytics">Analytics &amp; tracking</h2>'
            '<p>Before you announce the launch, confirm analytics and search tools are recording data: Google Analytics 4, Google Search Console (with the sitemap submitted), conversion tracking on your forms, and a quick test enquiry to make sure leads actually reach your inbox.</p>'
            '<p>Launching a new site soon? We design, build and launch fast, SEO-ready websites — and run this exact checklist before every go-live. <a href="/web-development.html">See our web development service</a> or download the checklist above.</p>'
        ),
    },
    {
        "slug": "website-brief-requirements-template",
        "title": "How to Write a Website Brief (Free Requirements Template)",
        "tag": "Web Design",
        "author": "Evision Infoserve",
        "author_role": "Web Design & Development · Greater Noida",
        "read_min": 6,
        "excerpt": "A clear website brief gets you a better site, faster, at a fixed price. Here's exactly what to "
                   "include — plus a free fill-in-the-blanks requirements template.",
        "cover": "",
        "meta_title": "How to Write a Website Brief — Free Requirements Template | Evision Infoserve",
        "meta_desc": "Learn how to write a website brief that gets accurate quotes and a better result — with a "
                     "free downloadable website requirements template for your next project.",
        "og_title": "How to Write a Website Brief (Free Requirements Template)",
        "og_desc": "Get accurate quotes and a better website — here's the brief to write, with a free template.",
        "body": (
            '<p>The difference between a website project that goes smoothly and one that drags on is usually the brief. A clear brief gets you accurate quotes, a fixed timeline, and a result that actually matches what you pictured. Here\'s what to include — and a template you can fill in tonight.</p>'
            '<h2 id="goals">1. Business goals &amp; audience</h2>'
            '<p>Start with <em>why</em>. What should the website achieve — leads, sales, bookings, credibility? Who is it for, and what do you want them to do? One or two sentences here shapes every design decision that follows.</p>'
            '<h2 id="pages">2. Pages &amp; features</h2>'
            '<ul>'
            '<li>Sitemap: every page you need</li>'
            '<li>Must-have features (forms, booking, payments, blog, multi-language)</li>'
            '<li>Any integrations (CRM, WhatsApp, payment gateway)</li>'
            '</ul>'
            '<h2 id="look">3. Look &amp; feel</h2>'
            '<ul>'
            '<li>Two or three websites you like, and why</li>'
            '<li>Your logo, colours and fonts (or a note that you need branding)</li>'
            '<li>Photos and content — ready, or do you need help?</li>'
            '</ul>'
            + _lm(
                "Website Requirements Template",
                "Get the fill-in-the-blanks template",
                "A simple website brief template — goals, sitemap, features, content and budget — so you get accurate quotes and a website that matches your vision.",
                ["Fill it in in 15 minutes",
                 "Get accurate, comparable quotes",
                 "Works for any web designer or agency"],
                "Send me the template",
                "website-brief-requirements-template",
            ) +
            '<h2 id="budget">4. Budget &amp; timeline</h2>'
            '<p>Sharing a budget range isn\'t giving away your hand — it lets a studio recommend the right scope instead of guessing. Note any hard deadline (an event, a campaign) so the timeline is realistic from day one.</p>'
            '<p>Ready to brief your project? Fill in the template above and <a href="/contact.html" data-audit-open>send it to us</a> for a fixed quote within 24 hours — website design and development, SEO-ready from day one.</p>'
        ),
    },
    {
        "slug": "seo-starter-kit-rank-new-website-90-days",
        "title": "The SEO Starter Kit: Rank Your New Website in 90 Days",
        "tag": "SEO",
        "author": "Evision Infoserve",
        "author_role": "SEO & Search Growth · Greater Noida",
        "read_min": 10,
        "excerpt": "A brand-new website won't rank on its own. This 90-day SEO starter plan covers the technical "
                   "foundations, content and links that get you found — with a free downloadable roadmap.",
        "cover": "",
        "meta_title": "SEO Starter Kit: Rank Your New Website in 90 Days | Evision Infoserve",
        "meta_desc": "A 90-day SEO plan for new websites — technical setup, keyword and content foundations, and "
                     "links. Free downloadable roadmap. We also run SEO for businesses across India.",
        "og_title": "The SEO Starter Kit: Rank Your New Website in 90 Days",
        "og_desc": "Technical setup, content and links — the 90-day plan to get a new website found. Free roadmap.",
        "body": (
            '<p>Launching a website is the start, not the finish. Google needs time and signals before it trusts a new domain. This 90-day starter plan is the exact sequence we use to move a fresh site from invisible to found — download the roadmap and follow along.</p>'
            '<h2 id="days-1-30">Days 1–30: Technical foundations</h2>'
            '<ul>'
            '<li>Verify Google Search Console and submit your sitemap</li>'
            '<li>Fix crawl and indexation issues</li>'
            '<li>Nail Core Web Vitals (speed, stability)</li>'
            '<li>Add JSON-LD schema and a clean heading structure</li>'
            '<li>Set up a Google Business Profile for local reach</li>'
            '</ul>'
            '<h2 id="days-31-60">Days 31–60: Keywords &amp; content</h2>'
            '<ul>'
            '<li>Map keywords to pages (intent, not just volume)</li>'
            '<li>Write answer-first content for each core page</li>'
            '<li>Publish two to four helpful articles in a topic cluster</li>'
            '<li>Interlink pages so authority flows</li>'
            '</ul>'
            '<h2 id="days-61-90">Days 61–90: Authority &amp; AI visibility</h2>'
            '<ul>'
            '<li>Earn a handful of relevant, quality backlinks</li>'
            '<li>Get listed in trusted local and industry directories</li>'
            '<li>Add an llms.txt file so AI engines find your best content</li>'
            '<li>Track rankings, traffic and AI citations</li>'
            '</ul>'
            + _lm(
                "90-Day SEO Roadmap (PDF)",
                "Get the 90-day SEO roadmap",
                "A week-by-week plan to get a new website ranking — technical setup, keyword mapping, content and links — in one printable roadmap.",
                ["Week-by-week actions for 90 days",
                 "Beginner-friendly, no jargon",
                 "Works alongside any website"],
                "Send me the roadmap",
                "seo-starter-kit-rank-new-website-90-days",
            ) +
            '<h2 id="keep-going">After 90 days</h2>'
            '<p>SEO compounds. Keep publishing, keep earning links, and keep improving the pages that are close to page one. Most sites see meaningful movement in three to six months of consistent work.</p>'
            '<p>Want it handled for you? We run SEO — technical, content, local and AI search — for businesses across India. <a href="/seo.html">See our SEO service</a> or grab the roadmap above to start yourself.</p>'
        ),
    },
]

# ── Image uploads (admin) ──────────────────────────────────────────────────
UPLOAD_DIR = os.path.join(ROOT, "uploads")
_EXT_BY_MIME = {"image/jpeg": "jpg", "image/jpg": "jpg", "image/png": "png",
                "image/webp": "webp", "image/gif": "gif", "image/avif": "avif"}
_DATAURL_RE = re.compile(r"^data:([\w/+.-]+);base64,(.*)$", re.S)
MAX_UPLOAD_BYTES = 6 * 1024 * 1024  # 6 MB


def save_upload(data_url, suggested_name=""):
    """Decode a base64 data URL, save it under /uploads/, return its public path.
    Raises ValueError on bad input. Used by the admin image picker."""
    m = _DATAURL_RE.match(data_url or "")
    if not m:
        raise ValueError("Invalid image data.")
    mime = m.group(1).lower()
    ext = _EXT_BY_MIME.get(mime)
    if not ext:
        raise ValueError("Unsupported image type. Use JPG, PNG, WEBP, GIF or AVIF.")
    try:
        raw = base64.b64decode(m.group(2), validate=True)
    except Exception:
        raise ValueError("Could not decode the image.")
    if not raw:
        raise ValueError("Empty image.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ValueError("Image is too large (max 6 MB).")
    # Build a safe, unique filename: <slug>-<token>.<ext>
    stem = re.sub(r"[^a-z0-9]+", "-", os.path.splitext(suggested_name or "")[0].lower()).strip("-") or "image"
    stem = stem[:40]
    fname = f"{stem}-{secrets.token_hex(4)}.{ext}"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    with open(os.path.join(UPLOAD_DIR, fname), "wb") as fh:
        fh.write(raw)
    return "/uploads/" + fname


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


# ───────────────────── new-lead alerts (email + phone) ─────────────────────

LEAD_LABELS = {"audit": "Free Audit", "get-started": "Get Started",
               "lead-magnet": "Lead Magnet", "scorecard": "Scorecard",
               "quote-calculator": "Quote Calculator", "newsletter": "Newsletter",
               "voice-call": "Voice Call"}


def lead_label(e):
    return LEAD_LABELS.get(e.get("type"), "Quote")


def wa_number(phone):
    """A lead's phone as a wa.me / tel target: digits, Indian country code added
    when they typed a bare 10-digit mobile."""
    d = re.sub(r"\D", "", phone or "")
    if len(d) == 10:
        d = "91" + d
    return d


def lead_lines(e):
    """The alert body, shared by every channel. Short enough to read on a lock
    screen: who, what they want, and how to reach them."""
    bits = [f"{lead_label(e)} — {e.get('name') or 'Someone'}"]
    if e.get("phone"):
        bits.append(f"Phone: {e['phone']}")
    if e.get("email"):
        bits.append(f"Email: {e['email']}")
    detail = " · ".join(filter(None, [e.get("company"), e.get("service"), e.get("budget")]))
    if detail:
        bits.append(detail)
    if e.get("message"):
        msg = " ".join((e["message"] or "").split())
        bits.append("“" + (msg[:220] + "…" if len(msg) > 220 else msg) + "”")
    if e.get("source"):
        bits.append(f"From: {e['source']}")
    return bits


def _http(url, data=None, headers=None, timeout=10):
    """Minimal POST/GET helper (stdlib only). Returns the response body text."""
    import urllib.request
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def send_telegram_alert(e):
    """Push the lead to Telegram — free, arrives in about a second, and the
    phone number is tap-to-call inside the app."""
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return False
    import urllib.parse
    # Telegram's HTML mode understands &amp; &lt; &gt; and nothing else, so
    # html.escape()'s &#x27; for apostrophes would show up as literal text.
    def esc(s):
        return (str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    lines = ["🔥 <b>New lead — " + esc(e.get("name") or "Someone") + "</b>",
             "<i>" + esc(lead_label(e)) + "</i>", ""]
    for ln in lead_lines(e)[1:]:
        lines.append(esc(ln))
    wa = wa_number(e.get("phone"))
    if wa:
        greet = urllib.parse.quote(
            f"Hi {(e.get('name') or '').split(' ')[0]}, this is Evision Infoserve — "
            f"thanks for your enquiry. When is a good time to talk?")
        lines += ["", f'<a href="https://wa.me/{wa}?text={greet}">💬 WhatsApp them</a> · '
                      f'<a href="{SITE_URL}/admin/">📋 Admin panel</a>']
    body = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID, "text": "\n".join(lines),
        "parse_mode": "HTML", "disable_web_page_preview": "true",
    }).encode()
    _http(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", body,
          {"Content-Type": "application/x-www-form-urlencoded"})
    return True


def send_ntfy_alert(e):
    """Push via ntfy — free, and at 'urgent' priority it rings/vibrates through
    a silenced phone, which is the closest thing to a call without paying."""
    if not NTFY_TOPIC:
        return False
    # Publish as JSON rather than via headers: ntfy headers must be ASCII, which
    # would mangle a name in Devanagari (or even an em dash).
    prio = {"min": 1, "low": 2, "default": 3, "high": 4, "urgent": 5, "max": 5}
    payload = {
        "topic": NTFY_TOPIC,
        "title": f"New {lead_label(e)} lead — {e.get('name') or 'Someone'}",
        "message": "\n".join(lead_lines(e)[1:]),
        "priority": prio.get(NTFY_PRIORITY.lower(), 5),
        "tags": ["fire", "telephone_receiver"],
        "click": f"{SITE_URL}/admin/",
    }
    wa = wa_number(e.get("phone"))
    if wa:
        payload["actions"] = [{"action": "view", "label": "WhatsApp",
                               "url": f"https://wa.me/{wa}"}]
    _http(NTFY_SERVER, json.dumps(payload).encode("utf-8"),
          {"Content-Type": "application/json"})
    return True


def place_twilio_call(e):
    """Actually ring your phone and read the lead out loud (paid, ~₹2/call).
    Use it for the enquiry types you want to drop everything for."""
    if not (TWILIO_SID and TWILIO_TOKEN and TWILIO_FROM and ALERT_PHONE):
        return False
    import urllib.parse
    say = (f"New lead on your website. {e.get('name') or 'Someone'} is interested in "
           f"{e.get('service') or 'your services'}. Check WhatsApp or the admin panel.")
    say = html.escape(say)
    twiml = f"<Response><Say voice='alice' language='en-IN'>{say}</Say>" \
            f"<Pause length='1'/><Say voice='alice' language='en-IN'>{say}</Say></Response>"
    body = urllib.parse.urlencode({"To": ALERT_PHONE, "From": TWILIO_FROM, "Twiml": twiml}).encode()
    auth = base64.b64encode(f"{TWILIO_SID}:{TWILIO_TOKEN}".encode()).decode()
    _http(f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Calls.json", body,
          {"Content-Type": "application/x-www-form-urlencoded",
           "Authorization": "Basic " + auth}, timeout=15)
    return True


def alert_new_enquiry(e):
    """Fan a new (non-spam) lead out to every configured channel. Runs in a
    background thread; one channel failing never stops the others."""
    sent = []
    phone_channels = e.get("type") not in ALERT_SKIP_TYPES
    jobs = [("email", notify_new_enquiry)]
    if phone_channels:
        jobs += [("telegram", send_telegram_alert), ("ntfy", send_ntfy_alert),
                 ("call", place_twilio_call)]
    for name, fn in jobs:
        try:
            if fn(e):
                sent.append(name)
        except Exception as ex:
            log(f"[alert] {name} failed: {ex}")
    log(f"[alert] New {lead_label(e)} from {e.get('name')} "
        f"({e.get('phone') or e.get('email')}) -> {', '.join(sent) or 'no channel configured'}")


def notify_new_enquiry(e):
    """Email the admin about a new enquiry. Degrades gracefully if SMTP is unset."""
    label = lead_label(e)
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS):
        return False
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
        f"Contact consent   : {'yes - SMS/RCS/Call/Email/WhatsApp + T&C' if e.get('consent') else 'NO - do not call/SMS'}\n"
        f"Marketing opt-in  : {'yes' if e.get('marketing') else 'no'}\n\n"
        f"Message:\n{e.get('message') or '(none)'}\n\n"
        f"— View in the admin panel: {SITE_URL}/admin/\n"
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
    return True   # failures are caught and logged by alert_new_enquiry()


# ───────────────────────── blog post rendering ─────────────────────────

SITE_URL = os.environ.get("SITE_URL", "https://evisioninfoserve.com").rstrip("/")


def _fmt_date(iso):
    """'2026-05-28T...' → 'May 28, 2026'. Returns '' on bad input."""
    try:
        return datetime.fromisoformat(iso).strftime("%b %d, %Y")
    except Exception:
        return ""


def render_post_page(post):
    """Build a full, SEO-ready HTML page for a single blog post from a DB row
    (dict). Title, meta description and Open Graph tags all come from the post so
    they're editable in the admin panel; the body HTML is authored there too."""
    e = html.escape
    title = post["title"]
    meta_title = post.get("meta_title") or f"{title} | Evision Infoserve"
    meta_desc = post.get("meta_desc") or post.get("excerpt") or ""
    og_title = post.get("og_title") or post.get("meta_title") or title
    og_desc = post.get("og_desc") or meta_desc
    og_image = post.get("og_image") or post.get("cover") or ""
    url = f"{SITE_URL}/blog/{post['slug']}"
    if og_image and og_image.startswith("/"):
        og_image = SITE_URL + og_image

    # Byline pieces
    byline = []
    if post.get("author"):
        initials = "".join(w[0] for w in post["author"].split()[:2]).upper() or "E"
        byline.append(f'<span class="au"><span class="art-av">{e(initials)}</span><b>{e(post["author"])}</b></span>')
    if post.get("author_role"):
        byline.append(f'<span class="dot"></span><span>{e(post["author_role"])}</span>')
    if post.get("read_min"):
        byline.append(f'<span class="dot"></span><span>{int(post["read_min"])} min read</span>')
    date_str = _fmt_date(post.get("published_at") or post.get("created_at") or "")
    if date_str:
        byline.append(f'<span class="dot"></span><span>{e(date_str)}</span>')
    byline_html = "".join(byline)

    # Feature image / placeholder
    if post.get("cover"):
        feat = f'<div class="art-feat has-img"><img src="{e(post["cover"])}" alt="{e(title)}"></div>'
    else:
        feat = (f'<div class="art-feat"><div class="ph"><div class="big">{e(title)}</div>'
                f'<div class="sm">// evisioninfoserve.com/blog</div></div></div>')

    tag_html = f'<span class="tag tag-blue">{e(post["tag"])}</span>' if post.get("tag") else ""

    # Author box
    author_box = ""
    if post.get("author"):
        initials = "".join(w[0] for w in post["author"].split()[:2]).upper() or "E"
        role = post.get("author_role") or "Evision Infoserve"
        bio_html = ('<p class="abio">' + e(post["author_bio"]) + '</p>') if post.get("author_bio") else ""
        author_box = (
            '<div class="author-box"><div class="av">' + e(initials) + '</div><div>'
            '<div class="an">' + e(post["author"]) + '</div>'
            '<div class="ar">' + e(role) + '</div>'
            + bio_html +
            '</div></div>'
        )

    og_img_tags = ""
    if og_image:
        og_img_tags = (f'<meta property="og:image" content="{e(og_image)}">'
                       f'<meta name="twitter:image" content="{e(og_image)}">')

    # JSON-LD Article schema (helps Google + AI engines)
    ld = {
        "@context": "https://schema.org", "@type": "Article",
        "headline": title, "description": meta_desc,
        "author": {"@type": "Person", "name": post.get("author") or "Evision Infoserve"},
        "publisher": {"@type": "Organization", "name": "Evision Infoserve"},
        "mainEntityOfPage": url, "url": url,
    }
    if og_image:
        ld["image"] = og_image
    if post.get("published_at"):
        ld["datePublished"] = post["published_at"]
    if post.get("updated_at"):
        ld["dateModified"] = post["updated_at"]

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="icon" type="image/svg+xml" href="/assets/favicon.svg?v=2">
<title>{e(meta_title)}</title>
<meta name="description" content="{e(meta_desc)}">
<link rel="canonical" href="{e(url)}">
<meta property="og:type" content="article">
<meta property="og:title" content="{e(og_title)}">
<meta property="og:description" content="{e(og_desc)}">
<meta property="og:url" content="{e(url)}">
<meta property="og:site_name" content="Evision Infoserve">
{og_img_tags}
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(og_title)}">
<meta name="twitter:description" content="{e(og_desc)}">
<script type="application/ld+json">{json.dumps(ld)}</script>
<link rel="stylesheet" href="/assets/tokens.css?v=5">
<link rel="stylesheet" href="/assets/site.css?v=6">
<link rel="stylesheet" href="/assets/chrome.css?v=5">
<link rel="stylesheet" href="/assets/blog.css?v=3">
<script src="https://unpkg.com/lucide@latest/dist/umd/lucide.min.js"></script>
</head>
<body data-page="blog">

<section class="art-hero" data-screen-label="Article hero">
  <div class="container">
    <div class="art-head">
      {tag_html}
      <h1>{e(title)}</h1>
      <div class="art-byline">{byline_html}</div>
    </div>
    {feat}
  </div>
</section>

<section class="section" style="padding-top:44px">
  <div class="container">
    <div class="art-body">
      <article class="prose">
        {post["body"]}
        {author_box}
      </article>
      <p style="margin-top:36px"><a href="/blog" class="btn btn-ghost-light btn-sm">← Back to all articles</a></p>
    </div>
  </div>
</section>

<section class="cta-band">
  <div class="container cta-inner">
    <div><h2 class="h-lg" style="color:#fff;max-width:22ch">Need a website, SEO, or a hand with your project?</h2><p class="lead" style="margin-top:12px;color:var(--fg-muted-dark)">Tell us what you're building — we'll send a free quote and a plan within 24 hours.</p></div>
    <a href="/contact.html" data-audit-open class="btn btn-primary btn-lg">Get a free quote</a>
  </div>
</section>

<script src="/assets/site.js?v=7"></script>
<script src="/assets/chrome.js?v=7"></script>
</body>
</html>"""


# ───────────────────────── sitemap & robots ─────────────────────────

# Pages that exist but should stay out of the sitemap:
#   /service – generic template page (noindexed). /pricing is now a real,
#   indexable selling page and is included.
SITEMAP_EXCLUDE = {"/service"}

# ── SEO / AEO: brand facts used across meta tags, JSON-LD and llms.txt ──
BRAND_NAME = "Evision Infoserve"
BRAND_PHONE = "+91 93112 21517"
BRAND_TEL = "+919311221517"
BRAND_EMAIL = "info@evisioninfoserve.com"
BRAND_STREET = "Gaur City Mall, Greater Noida West"
BRAND_LOCALITY = "Greater Noida"
BRAND_REGION = "Uttar Pradesh"
BRAND_POSTAL = "201009"
BRAND_GEO = (28.6045, 77.4270)   # Greater Noida West (approx)
BRAND_SAMEAS = [
    "https://www.linkedin.com/company/evisioninfoserve/",
    "https://www.instagram.com/evisioninfoserve/",
    "https://www.youtube.com/@evisioninfoserve",
    "https://www.facebook.com/EvisionInfoservepvtltd/",
]
OG_IMAGE = "/assets/og-default.png"

# Human-readable labels for clean-URL segments (breadcrumbs + AEO).
_SEG_LABEL = {
    "services": "Services", "web-design": "Website Design", "web-development": "Web Development",
    "seo": "SEO Services", "content-marketing": "Content Marketing", "social-media": "Social Media",
    "ppc": "PPC & Paid Ads", "orm": "ORM & Reputation", "ai-digital-marketing": "AI Digital Marketing",
    "affiliate-marketing": "Affiliate Marketing", "youtube-marketing": "YouTube Marketing",
    "email-marketing": "Email Marketing", "mobile-app-marketing": "Mobile App Marketing",
    "ai-seo": "AI SEO / LLMO", "llm-optimization": "LLM Optimization", "agentic-ai-seo": "Agentic AI SEO",
    "enterprise-seo": "Enterprise SEO", "ecommerce-seo": "Ecommerce SEO", "technical-seo": "Technical SEO",
    "local-seo": "Local SEO", "multilingual-seo": "Multilingual SEO", "link-building": "Link Building",
    "white-label-seo": "White-Label SEO", "seo-audit": "SEO Audit", "industry-seo": "Industry SEO",
    "content-writing": "Content Writing", "guest-posting": "Guest Posting", "digital-pr": "Digital PR",
    "pricing": "Packages & Pricing", "about": "About Us", "blog": "Blog", "contact": "Contact",
    "website-health-check": "Website Health Check",
    "portfolio": "Portfolio", "clients": "Our Clients", "career": "Careers", "testimonials": "Testimonials",
    "privacy-policy": "Privacy Policy", "refund-policy": "Refund Policy", "terms": "Terms",
}

# Homepage FAQ (mirrors the on-page FAQ) → FAQPage schema for AEO / rich results.
HOME_FAQ = [
    ("Do you handle both website design and SEO?",
     "Yes — that's our core advantage. We design and develop your website and run SEO under one roof, so the site is built to rank from day one instead of being retrofitted later. You can also take either service on its own."),
    ("How long does a new website take?",
     "A standard business website typically takes 3–5 weeks from kickoff to launch; e-commerce and custom web apps take longer. We share a clear timeline and milestones after the discovery call."),
    ("What platforms do you build on?",
     "We build on WordPress, headless stacks, Shopify/WooCommerce for stores, and fully custom code when it's the right fit. We recommend the platform based on your goals, budget and who will maintain it."),
    ("How quickly will I see SEO results?",
     "Technical wins and a faster site show up immediately; meaningful ranking and traffic gains typically build over 3–6 months of consistent SEO and content. We report progress every month."),
    ("Can you redesign or improve my existing website?",
     "Absolutely. We audit your current site, keep what works, and redesign for speed, conversions and search — without losing your existing rankings during the migration."),
    ("Do you offer combined website + SEO packages?",
     "Yes. Our bundled plans include the website build plus ongoing SEO in one predictable monthly plan. See the packages section or ask for a tailored quote."),
]


def build_llms():
    """llms.txt — a concise, AI-crawler-friendly map of the site's best content.
    Helps GPTBot, ClaudeBot, PerplexityBot & Google-Extended understand and cite us."""
    L = [
        f"# {BRAND_NAME}",
        "",
        f"> {BRAND_NAME} is a website design, development and SEO studio in {BRAND_LOCALITY}, "
        "India. We design and build fast, beautiful websites, then engineer them to rank on "
        "Google and get cited by AI search (AEO, GEO, LLMO). Websites start from ₹9,999.",
        "",
        f"- Location: {BRAND_STREET}, {BRAND_LOCALITY}, {BRAND_REGION} {BRAND_POSTAL}, India",
        f"- Phone / WhatsApp: {BRAND_PHONE}",
        f"- Email: {BRAND_EMAIL}",
        "",
        "## Core services",
        f"- [Website Design]({SITE_URL}/services/web-design): custom, responsive, conversion-focused UI/UX and brand design.",
        f"- [Web Development]({SITE_URL}/services/web-development): WordPress, Shopify, React/Next.js, e-commerce and web apps.",
        f"- [SEO Services]({SITE_URL}/services/seo): technical, on-page, local and content SEO to rank on Google.",
        f"- [AI SEO / LLMO]({SITE_URL}/services/seo/ai-seo): get surfaced and cited inside ChatGPT, Gemini and Perplexity.",
        f"- [Content Marketing]({SITE_URL}/services/content-marketing): topic clusters and answer-first content.",
        f"- [PPC & Paid Ads]({SITE_URL}/services/ppc): Google, Meta and LinkedIn campaigns tuned for ROI.",
        "",
        "## Packages",
        f"- [Pricing & packages]({SITE_URL}/pricing): Launch (from ₹9,999 one-time), Grow (website + SEO, monthly), Scale (custom). Free instant estimate calculator.",
        "",
        "## Resources",
        f"- [Blog & free guides]({SITE_URL}/blog): practical web design, development and SEO guides, plus final-year web development project help for students.",
        f"- [Portfolio]({SITE_URL}/portfolio): websites, web apps and SEO case studies.",
        f"- [Contact]({SITE_URL}/contact): get a free quote and audit within 24 hours.",
        "",
    ]
    return "\n".join(L)


def build_sitemap():
    """Generate sitemap.xml from the public clean-URL map + every published blog
    post, so new posts appear automatically. URLs use SITE_URL (the canonical
    domain)."""
    e = html.escape
    conn = db()
    posts = conn.execute(
        "SELECT slug, published_at, updated_at, created_at FROM posts WHERE status='published'"
    ).fetchall()
    conn.close()

    entries = []  # (loc, lastmod, priority)
    for fname, clean in FILE_TO_CLEAN.items():
        if clean in SITEMAP_EXCLUDE:
            continue
        loc = SITE_URL + ("/" if clean == "/" else clean)
        try:
            lastmod = datetime.fromtimestamp(
                os.path.getmtime(os.path.join(ROOT, fname)), timezone.utc).strftime("%Y-%m-%d")
        except OSError:
            lastmod = ""
        pr = "1.0" if clean == "/" else ("0.8" if clean.count("/") == 1 else "0.6")
        entries.append((loc, lastmod, pr))
    for p in posts:
        loc = f"{SITE_URL}/blog/{p['slug']}"
        lastmod = (p["published_at"] or p["updated_at"] or p["created_at"] or "")[:10]
        entries.append((loc, lastmod, "0.6"))

    seen, urls = set(), []
    for loc, lastmod, pr in entries:
        if loc in seen:
            continue
        seen.add(loc)
        u = f"  <url>\n    <loc>{e(loc)}</loc>\n"
        if lastmod:
            u += f"    <lastmod>{e(lastmod)}</lastmod>\n"
        u += f"    <changefreq>weekly</changefreq>\n    <priority>{pr}</priority>\n  </url>"
        urls.append(u)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "\n".join(urls) + "\n</urlset>\n")


def build_robots():
    """robots.txt: allow the public site (incl. AI answer engines), keep bots out
    of the admin panel/API, and point crawlers at the sitemap + llms.txt."""
    ai_bots = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-Web",
               "PerplexityBot", "Google-Extended", "Applebot-Extended", "Amazonbot", "CCBot"]
    lines = ["User-agent: *", "Allow: /", "Disallow: /admin/", "Disallow: /api/", ""]
    for b in ai_bots:                       # explicitly welcome AI answer engines
        lines += [f"User-agent: {b}", "Allow: /", ""]
    lines += [f"Sitemap: {SITE_URL}/sitemap.xml", f"# AI content map: {SITE_URL}/llms.txt", ""]
    return "\n".join(lines)


# ───────────────────────── SEO head injection ─────────────────────────

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_DESC_RE = re.compile(r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']', re.I | re.S)


def _breadcrumb_ld(clean, canonical):
    """BreadcrumbList from a clean URL: Home > seg > seg > current."""
    items = [{"@type": "ListItem", "position": 1, "name": "Home", "item": SITE_URL + "/"}]
    if clean == "/":
        return None
    parts = [p for p in clean.strip("/").split("/") if p]
    acc = ""
    for i, seg in enumerate(parts):
        acc += "/" + seg
        items.append({"@type": "ListItem", "position": i + 2,
                      "name": _SEG_LABEL.get(seg, seg.replace("-", " ").title()),
                      "item": SITE_URL + acc})
    return {"@type": "BreadcrumbList", "itemListElement": items}


def _seo_head(clean, title, desc):
    """Build the canonical + Open Graph + Twitter + JSON-LD block for a page."""
    e = html.escape
    canonical = SITE_URL + ("/" if clean == "/" else clean)
    og_img = SITE_URL + OG_IMAGE
    noindex = clean in ("/service",)
    robots = "noindex, follow" if noindex else "index, follow, max-image-preview:large, max-snippet:-1"
    og_type = "website"

    tags = [
        f'<link rel="canonical" href="{e(canonical)}">',
        f'<meta name="robots" content="{robots}">',
        f'<meta property="og:type" content="{og_type}">',
        f'<meta property="og:site_name" content="{e(BRAND_NAME)}">',
        f'<meta property="og:title" content="{e(title)}">',
        f'<meta property="og:description" content="{e(desc)}">',
        f'<meta property="og:url" content="{e(canonical)}">',
        f'<meta property="og:image" content="{e(og_img)}">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        '<meta property="og:locale" content="en_IN">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{e(title)}">',
        f'<meta name="twitter:description" content="{e(desc)}">',
        f'<meta name="twitter:image" content="{e(og_img)}">',
        '<meta name="author" content="' + e(BRAND_NAME) + '">',
        '<meta name="geo.region" content="IN-UP">',
        f'<meta name="geo.placename" content="{e(BRAND_LOCALITY)}">',
    ]

    # ── JSON-LD @graph ──
    org = {
        "@type": "Organization", "@id": SITE_URL + "/#organization",
        "name": BRAND_NAME, "url": SITE_URL + "/",
        "logo": {"@type": "ImageObject", "url": SITE_URL + "/assets/favicon.svg"},
        "image": og_img, "email": BRAND_EMAIL, "telephone": BRAND_PHONE,
        "sameAs": BRAND_SAMEAS,
        "contactPoint": {"@type": "ContactPoint", "telephone": BRAND_TEL,
                         "contactType": "customer service", "areaServed": "IN",
                         "availableLanguage": ["en", "hi"]},
    }
    website = {"@type": "WebSite", "@id": SITE_URL + "/#website", "url": SITE_URL + "/",
               "name": BRAND_NAME, "publisher": {"@id": SITE_URL + "/#organization"},
               "inLanguage": "en-IN"}
    webpage = {"@type": "WebPage", "@id": canonical + "#webpage", "url": canonical,
               "name": title, "description": desc, "isPartOf": {"@id": SITE_URL + "/#website"},
               "inLanguage": "en-IN"}
    graph = [org, website, webpage]

    crumb = _breadcrumb_ld(clean, canonical)
    if crumb:
        crumb["@id"] = canonical + "#breadcrumb"
        webpage["breadcrumb"] = {"@id": crumb["@id"]}
        graph.append(crumb)

    # LocalBusiness on the home & contact pages (rich local signals).
    if clean in ("/", "/contact"):
        graph.append({
            "@type": "ProfessionalService", "@id": SITE_URL + "/#localbusiness",
            "name": BRAND_NAME, "url": SITE_URL + "/", "image": og_img,
            "telephone": BRAND_PHONE, "email": BRAND_EMAIL, "priceRange": "₹₹",
            "address": {"@type": "PostalAddress", "streetAddress": BRAND_STREET,
                        "addressLocality": BRAND_LOCALITY, "addressRegion": BRAND_REGION,
                        "postalCode": BRAND_POSTAL, "addressCountry": "IN"},
            "geo": {"@type": "GeoCoordinates", "latitude": BRAND_GEO[0], "longitude": BRAND_GEO[1]},
            "areaServed": [{"@type": "Country", "name": "India"}],
            "openingHoursSpecification": [{"@type": "OpeningHoursSpecification",
                "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
                "opens": "10:00", "closes": "19:00"}],
            "sameAs": BRAND_SAMEAS,
        })

    # FAQPage on the homepage (AEO / rich results).
    if clean == "/":
        graph.append({"@type": "FAQPage", "@id": SITE_URL + "/#faq",
            "mainEntity": [{"@type": "Question", "name": q,
                            "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in HOME_FAQ]})

    ld = {"@context": "https://schema.org", "@graph": graph}
    tags.append('<script type="application/ld+json">'
                + json.dumps(ld, ensure_ascii=False) + '</script>')
    return "\n".join(tags) + "\n"


def inject_seo(html_text, clean):
    """Insert canonical/OG/Twitter/JSON-LD before </head>. Idempotent-ish: skips if
    a canonical is already present (e.g. a page that hard-codes its own SEO)."""
    if 'rel="canonical"' in html_text[:4000] or "</head>" not in html_text:
        return html_text
    mt = _TITLE_RE.search(html_text)
    md = _DESC_RE.search(html_text)
    title = html.unescape((mt.group(1).strip() if mt else BRAND_NAME))
    desc = html.unescape((md.group(1).strip() if md else ""))
    return html_text.replace("</head>", _seo_head(clean, title, desc) + "</head>", 1)


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

    def _client_ip(self):
        """Real visitor IP. Nginx sets X-Forwarded-For / X-Real-IP (see
        deploy/nginx-evision.conf); bind HOST=127.0.0.1 in production so those
        headers can only come from the proxy."""
        xff = self.headers.get("X-Forwarded-For", "")
        if xff:
            return xff.split(",")[0].strip()[:64]
        return (self.headers.get("X-Real-IP")
                or (self.client_address[0] if self.client_address else ""))[:64]

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

    def _account(self):
        """Current logged-in account row (dict) or None."""
        return account_by_email(self._auth())

    def _require_admin(self):
        """Like _require_auth but restricts to the main admin account (role=admin).
        Returns the admin's email, or None (after writing a 401/403) if not allowed."""
        acc = self._account()
        if not acc:
            self._json({"error": "Unauthorized"}, 401)
            return None
        if (acc.get("role") or "author") != "admin":
            self._json({"error": "This action is restricted to the main admin account."}, 403)
            return None
        return acc["email"]

    def _redirect301(self, location):
        self.send_response(301)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    # ---- dispatch ----
    def _send_text(self, text, content_type):
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        raw = self.path.split("?")[0]
        if raw.startswith("/api/"):
            return self.api_get()
        if raw == "/sitemap.xml":
            return self._send_text(build_sitemap(), "application/xml; charset=utf-8")
        if raw == "/robots.txt":
            return self._send_text(build_robots(), "text/plain; charset=utf-8")
        if raw == "/llms.txt":
            return self._send_text(build_llms(), "text/plain; charset=utf-8")
        # Old .html URL → 301 to the clean URL.
        fname = raw[1:] if raw.startswith("/") else raw
        if fname in FILE_TO_CLEAN:
            return self._redirect301(FILE_TO_CLEAN[fname])
        # Clean URL → serve the underlying file with SEO head injected server-side
        # (canonical, Open Graph, Twitter, JSON-LD) so crawlers/AI bots see it.
        clean = raw.rstrip("/") or "/"
        if clean in CLEAN_TO_FILE:
            return self.serve_page_with_seo(CLEAN_TO_FILE[clean], clean)
        # Blog article: /blog/<slug> → server-render the post (SEO meta + OG tags).
        m = re.match(r"^/blog/([a-z0-9][a-z0-9-]*)$", clean)
        if m:
            return self.serve_post(m.group(1))
        # Everything else (assets, /admin/, etc.) served as-is.
        return super().do_GET()

    def serve_page_with_seo(self, fname, clean):
        """Read a static HTML page and stream it with SEO/AEO head tags injected."""
        try:
            with open(os.path.join(ROOT, fname), "r", encoding="utf-8") as fh:
                html_text = fh.read()
        except OSError:
            return self.send_error(404, "Page not found")
        body = inject_seo(html_text, clean).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_post(self, slug):
        """Render a published blog post, or a draft when the admin passes a valid
        preview token (?preview=<token>) so authors can review before publishing."""
        qs = self.path.split("?", 1)[1] if "?" in self.path else ""
        preview_tok = ""
        for part in qs.split("&"):
            if part.startswith("preview="):
                preview_tok = part[8:]
        conn = db()
        row = conn.execute("SELECT * FROM posts WHERE slug=?", (slug,)).fetchone()
        post = dict(row) if row else None
        # No per-post bio? Fall back to the owning author's account bio (set in Settings).
        if post and not post.get("author_bio") and post.get("author_email"):
            acc = conn.execute("SELECT bio FROM admins WHERE email=?", (post["author_email"],)).fetchone()
            if acc and acc["bio"]:
                post["author_bio"] = acc["bio"]
        conn.close()
        allowed = row and (row["status"] == "published" or (preview_tok and session_email(preview_tok)))
        if not allowed:
            self.send_error(404, "Post not found")
            return
        body = render_post_page(post).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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
        # Public: client testimonials feed (clients page).
        if path == "/api/testimonials":
            conn = db()
            rows = conn.execute(
                "SELECT id,name,role,quote,photo,rating FROM testimonials WHERE active=1 ORDER BY sort, id"
            ).fetchall()
            conn.close()
            return self._json([dict(r) for r in rows])
        # Public: portfolio / case studies feed (portfolio page).
        if path == "/api/portfolio":
            conn = db()
            rows = conn.execute(
                "SELECT id,title,client,category,image,summary,metric,url FROM portfolio WHERE active=1 ORDER BY sort, id"
            ).fetchall()
            conn.close()
            return self._json([dict(r) for r in rows])
        # Public: blog listing feed (published posts only) for the /blog index page.
        if path == "/api/posts":
            conn = db()
            rows = conn.execute(
                """SELECT slug,title,excerpt,cover,tag,author,read_min,published_at
                   FROM posts WHERE status='published'
                   ORDER BY COALESCE(NULLIF(published_at,''), created_at) DESC, id DESC"""
            ).fetchall()
            conn.close()
            return self._json([dict(r) for r in rows])
        if path == "/api/admin/services":
            if not self._require_admin():
                return
            conn = db()
            rows = conn.execute("SELECT * FROM services ORDER BY sort, id").fetchall()
            conn.close()
            return self._json([dict(r) for r in rows])
        if path == "/api/admin/offers":
            if not self._require_admin():
                return
            conn = db()
            rows = conn.execute("SELECT * FROM offers ORDER BY id DESC").fetchall()
            conn.close()
            return self._json([dict(r) for r in rows])
        if path == "/api/admin/enquiries":
            if not self._require_admin():
                return
            conn = db()
            rows = conn.execute("SELECT * FROM enquiries ORDER BY id DESC").fetchall()
            conn.close()
            return self._json([dict(r) for r in rows])
        if path == "/api/admin/clients":
            if not self._require_admin():
                return
            conn = db()
            rows = conn.execute("SELECT * FROM clients ORDER BY id DESC").fetchall()
            conn.close()
            return self._json([dict(r) for r in rows])
        if path == "/api/admin/testimonials":
            if not self._require_admin():
                return
            conn = db()
            rows = conn.execute("SELECT * FROM testimonials ORDER BY sort, id").fetchall()
            conn.close()
            return self._json([dict(r) for r in rows])
        if path == "/api/admin/portfolio":
            if not self._require_admin():
                return
            conn = db()
            rows = conn.execute("SELECT * FROM portfolio ORDER BY sort, id").fetchall()
            conn.close()
            return self._json([dict(r) for r in rows])
        if path == "/api/admin/posts":
            acc = self._account()
            if not acc:
                return self._json({"error": "Unauthorized"}, 401)
            cols = """SELECT id,slug,title,excerpt,cover,tag,author,author_email,status,
                             read_min,created_at,updated_at,published_at FROM posts"""
            conn = db()
            if (acc.get("role") or "author") == "admin":
                rows = conn.execute(cols + " ORDER BY id DESC").fetchall()
            else:
                # Authors see only their own posts.
                rows = conn.execute(cols + " WHERE author_email=? ORDER BY id DESC",
                                    (acc["email"],)).fetchall()
            conn.close()
            return self._json([dict(r) for r in rows])
        m = re.match(r"^/api/admin/posts/(\d+)$", path)
        if m:
            acc = self._account()
            if not acc:
                return self._json({"error": "Unauthorized"}, 401)
            conn = db()
            row = conn.execute("SELECT * FROM posts WHERE id=?", (int(m.group(1)),)).fetchone()
            conn.close()
            if not row:
                return self._json({"error": "Post not found."}, 404)
            # Authors may only open their own posts.
            if (acc.get("role") or "author") != "admin" and (row["author_email"] or "") != acc["email"]:
                return self._json({"error": "Not your post."}, 403)
            return self._json(dict(row))
        if path == "/api/admin/accounts":
            if not self._require_admin():
                return
            conn = db()
            rows = conn.execute(
                "SELECT id,email,name,role,created_at FROM admins ORDER BY id"
            ).fetchall()
            conn.close()
            return self._json([dict(r) for r in rows])
        if path == "/api/admin/stats":
            if not self._require_admin():
                return
            conn = db()
            stats = {
                # "enquiries" counts real leads only — quarantined spam is
                # reported separately so the headline number stays honest.
                "enquiries": conn.execute("SELECT COUNT(*) n FROM enquiries WHERE status<>'spam'").fetchone()["n"],
                "new": conn.execute("SELECT COUNT(*) n FROM enquiries WHERE status='new'").fetchone()["n"],
                "spam": conn.execute("SELECT COUNT(*) n FROM enquiries WHERE status='spam'").fetchone()["n"],
                "clients": conn.execute("SELECT COUNT(*) n FROM clients").fetchone()["n"],
                "active": conn.execute("SELECT COUNT(*) n FROM clients WHERE status='active'").fetchone()["n"],
            }
            conn.close()
            return self._json(stats)
        if path == "/api/admin/me":
            acc = self._account()
            if not acc:
                return self._json({"error": "Unauthorized"}, 401)
            return self._json({"email": acc["email"], "role": acc.get("role") or "author",
                               "name": acc.get("name") or "", "bio": acc.get("bio") or ""})
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
            if not name:
                return self._json({"error": "Name is required."}, 400)
            if email and not EMAIL_RE.match(email):
                return self._json({"error": "Please enter a valid email."}, 400)
            if not email and not phone:
                return self._json({"error": "Please provide an email or phone number."}, 400)
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

            # ── anti-spam ──
            ip = self._client_ip()
            if enquiry_rate_limited(conn, ip):
                conn.close()
                log(f"[enquiry] Rate-limited {ip}")
                # Deliberately vague + 429 so a bot loop backs off.
                return self._json({"error": "Too many submissions. Please try again later."}, 429)

            elapsed = data.get("_t")
            try:
                elapsed = int(elapsed) if elapsed is not None else None
            except (TypeError, ValueError):
                elapsed = None
            ua = self.headers.get("User-Agent", "")[:300]
            score, why = score_enquiry(
                record, conn, ip=ip, ua=ua,
                origin=self.headers.get("Origin", ""),
                referer=self.headers.get("Referer", ""),
                elapsed_ms=elapsed,
                # _hp is stamped by assets/chrome.js; subject_line is the raw
                # honeypot input, which also catches bots that skip our JS and
                # POST the scraped field names straight at this endpoint.
                honeypot=str(data.get("_hp") or "") + str(data.get("subject_line") or ""),
            )
            is_spam = score >= SPAM_THRESHOLD
            record["status"] = "spam" if is_spam else "new"
            record["spam_score"], record["spam_reason"] = score, "; ".join(why)

            conn.execute(
                """INSERT INTO enquiries
                   (name,email,phone,company,website,service,budget,message,type,source,
                    consent,marketing,status,ip,ua,spam_score,spam_reason,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    record["name"], record["email"], record["phone"], record["company"],
                    record["website"], record["service"], record["budget"], record["message"],
                    record["type"], record["source"], record["consent"], record["marketing"],
                    record["status"], ip, ua, score, record["spam_reason"], now_iso(),
                ),
            )
            conn.commit()
            if is_spam:
                purge_old_spam(conn)
            conn.close()
            if is_spam:
                # Quarantined: no email, no "new" badge. Still visible under the
                # Spam filter in /admin/ so nothing is lost to a false positive.
                log(f"[enquiry] Spam ({score}) from {ip}: {record['name']} "
                    f"<{record['email']}> - {record['spam_reason']}")
            else:
                # Fire-and-forget alerts: email + whichever phone channels are
                # configured. Threaded so the visitor never waits on them.
                threading.Thread(target=alert_new_enquiry, args=(record,), daemon=True).start()
            # Bots get the same 201 as everyone else — an error would tell them
            # what to change.
            return self._json({"ok": True}, 201)

        # Public (shared-secret): the ElevenLabs phone agent, mid-conversation.
        # Authenticated with a header secret rather than a login, because the
        # caller is a machine. Failures answer 200 with a line for the agent to
        # say — see the voice_* handlers below.
        if path.startswith("/api/voice/"):
            if not voice.enabled():
                return self._json({"error": "Voice booking is not configured."}, 404)
            if not voice.secret_ok(self.headers.get("X-Voice-Secret", "")):
                log(f"[voice] Rejected {path} from {self._client_ip()} (bad secret)")
                return self._json({"error": "Unauthorized"}, 401)
            conversation = (self.headers.get("X-Conversation-Id")
                            or data.get("conversation_id") or "").strip()[:128]
            if path == "/api/voice/check-availability":
                return self.voice_check_availability(data, conversation)
            if path == "/api/voice/book-meeting":
                return self.voice_book_meeting(data, conversation)
            if path == "/api/voice/post-call":
                return self.voice_post_call(data, conversation)
            return self._json({"error": "Not found"}, 404)

        # Admin: login
        if path == "/api/admin/login":
            email = (data.get("email") or "").strip().lower()
            password = data.get("password") or ""
            conn = db()
            row = conn.execute("SELECT * FROM admins WHERE email=?", (email,)).fetchone()
            conn.close()
            if not row or not verify_password(password, row["pw_hash"], row["pw_salt"]):
                return self._json({"error": "Invalid email or password."}, 401)
            return self._json({"token": new_token(email), "email": email,
                               "role": row["role"] or "author", "name": row["name"] or ""})

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

        # Admin/author: update your own profile (display name + bio).
        if path == "/api/admin/profile":
            acc = self._account()
            if not acc:
                return self._json({"error": "Unauthorized"}, 401)
            fields, vals = [], []
            if "name" in data:
                fields.append("name=?")
                vals.append((data.get("name") or "").strip())
            if "bio" in data:
                fields.append("bio=?")
                vals.append((data.get("bio") or "").strip())
            if not fields:
                return self._json({"error": "Nothing to update."}, 400)
            vals.append(acc["email"])
            conn = db()
            conn.execute(f"UPDATE admins SET {','.join(fields)} WHERE email=?", vals)
            conn.commit()
            row = conn.execute("SELECT name,bio FROM admins WHERE email=?", (acc["email"],)).fetchone()
            conn.close()
            return self._json({"ok": True, "name": row["name"] or "", "bio": row["bio"] or ""})

        # Admin: add client
        if path == "/api/admin/clients":
            if not self._require_admin():
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
            if not self._require_admin():
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
            if not self._require_admin():
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

        # Admin: upload an image (base64 data URL) → returns its public /uploads/ path
        if path == "/api/admin/upload":
            if not self._require_auth():
                return
            try:
                url = save_upload(data.get("data") or "", data.get("filename") or "")
            except ValueError as ex:
                return self._json({"error": str(ex)}, 400)
            return self._json({"ok": True, "url": url}, 201)

        # Admin: add a testimonial
        if path == "/api/admin/testimonials":
            if not self._require_admin():
                return
            name = (data.get("name") or "").strip()
            quote = (data.get("quote") or "").strip()
            if not name or not quote:
                return self._json({"error": "Name and quote are required."}, 400)
            conn = db()
            cur = conn.execute(
                """INSERT INTO testimonials (name,role,quote,photo,rating,sort,active,created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (name, (data.get("role") or "").strip(), quote, (data.get("photo") or "").strip(),
                 int(data.get("rating") or 5), int(data.get("sort") or 0),
                 1 if data.get("active", 1) else 0, now_iso()),
            )
            conn.commit()
            tid = cur.lastrowid
            conn.close()
            return self._json({"ok": True, "id": tid}, 201)

        # Admin: add a portfolio item
        if path == "/api/admin/portfolio":
            if not self._require_admin():
                return
            title = (data.get("title") or "").strip()
            if not title:
                return self._json({"error": "Title is required."}, 400)
            conn = db()
            cur = conn.execute(
                """INSERT INTO portfolio (title,client,category,image,summary,metric,url,sort,active,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (title, (data.get("client") or "").strip(), (data.get("category") or "").strip(),
                 (data.get("image") or "").strip(), (data.get("summary") or "").strip(),
                 (data.get("metric") or "").strip(), (data.get("url") or "").strip(),
                 int(data.get("sort") or 0), 1 if data.get("active", 1) else 0, now_iso()),
            )
            conn.commit()
            pid = cur.lastrowid
            conn.close()
            return self._json({"ok": True, "id": pid}, 201)

        # Admin/author: create a blog post. Authors can only save drafts — only
        # the main admin account may publish (status forced to 'draft' otherwise).
        if path == "/api/admin/posts":
            acc = self._account()
            if not acc:
                return self._json({"error": "Unauthorized"}, 401)
            title = (data.get("title") or "").strip()
            if not title:
                return self._json({"error": "Title is required."}, 400)
            is_admin = (acc.get("role") or "author") == "admin"
            status = "published" if (is_admin and data.get("status") == "published") else "draft"
            # Byline defaults to the author's own name so it always shows on the post.
            author = (data.get("author") or "").strip() or acc.get("name") or acc["email"]
            conn = db()
            slug = unique_slug(conn, data.get("slug") or title)
            now = now_iso()
            cur = conn.execute(
                """INSERT INTO posts
                   (slug,title,excerpt,cover,body,tag,author,author_role,author_bio,author_email,read_min,
                    meta_title,meta_desc,og_title,og_desc,og_image,status,sort,
                    created_at,updated_at,published_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (slug, title, (data.get("excerpt") or "").strip(), (data.get("cover") or "").strip(),
                 data.get("body") or "", (data.get("tag") or "").strip(),
                 author, (data.get("author_role") or "").strip(),
                 (data.get("author_bio") or "").strip(), acc["email"],
                 int(data.get("read_min") or 5), (data.get("meta_title") or "").strip(),
                 (data.get("meta_desc") or "").strip(), (data.get("og_title") or "").strip(),
                 (data.get("og_desc") or "").strip(), (data.get("og_image") or "").strip(),
                 status, int(data.get("sort") or 0), now, now,
                 now if status == "published" else ""),
            )
            conn.commit()
            pid = cur.lastrowid
            conn.close()
            return self._json({"ok": True, "id": pid, "slug": slug, "status": status}, 201)

        # Admin only: create an author login account (role is always 'author').
        if path == "/api/admin/accounts":
            if not self._require_admin():
                return
            email = (data.get("email") or "").strip().lower()
            name = (data.get("name") or "").strip()
            password = data.get("password") or ""
            if not EMAIL_RE.match(email):
                return self._json({"error": "Please enter a valid email."}, 400)
            if len(password) < 8:
                return self._json({"error": "Password must be at least 8 characters."}, 400)
            conn = db()
            if conn.execute("SELECT id FROM admins WHERE email=?", (email,)).fetchone():
                conn.close()
                return self._json({"error": "An account with that email already exists."}, 409)
            h, s = hash_password(password)
            cur = conn.execute(
                "INSERT INTO admins (email,pw_hash,pw_salt,name,role,created_at) VALUES (?,?,?,?,?,?)",
                (email, h, s, name, "author", now_iso()),
            )
            conn.commit()
            aid = cur.lastrowid
            conn.close()
            return self._json({"ok": True, "id": aid}, 201)

        return self._json({"error": "Not found"}, 404)

    # ───────────── Voice agent handlers ─────────────
    # Reached only via /api/voice/* above, so the shared secret is already
    # checked. Each one answers 200 even when it fails: an HTTP error mid-call
    # makes the agent freeze or hallucinate a confirmation at the caller, which
    # is worse than losing the booking.

    def voice_check_availability(self, data, conversation):
        now = datetime.now(voice.IST)
        raw_date = (data.get("preferred_date") or "").strip()
        try:
            preferred = datetime.strptime(raw_date, "%Y-%m-%d").date()
        except ValueError:
            preferred = now.date()      # agent sent nonsense; start from today
        preferred = max(preferred, now.date())
        part = (data.get("part_of_day") or "any").strip().lower()
        try:
            duration = 45 if int(data.get("duration_minutes") or 30) > 30 else 30
        except (TypeError, ValueError):
            duration = 30

        try:
            busy = voice.busy_intervals(preferred, preferred + timedelta(days=voice.SEARCH_DAYS))
        except Exception as ex:
            log(f"[voice] Calendar unreachable: {ex}")
            return self._json(voice.reply_unavailable())

        day, starts = voice.find_slots(preferred, duration, part, now, busy)
        if not starts:
            log(f"[voice] Nothing free from {preferred} for {duration}min")
            return self._json(voice.reply_nothing_free(preferred))
        held = voice.hold_slots(starts, duration, conversation)
        log(f"[voice] Offered {len(held)} slot(s) on {day} to {conversation or 'unknown call'}")
        return self._json(voice.reply_slots(day, preferred, held))

    def voice_book_meeting(self, data, conversation):
        name = (data.get("full_name") or "").strip()
        email = (data.get("email") or "").strip().lower()
        slot_id = (data.get("slot_id") or "").strip()
        if not name or not EMAIL_RE.match(email):
            log(f"[voice] Refusing to book with name={name!r} email={email!r}")
            return self._json(voice.reply_book_failed())

        # Phone lines drop and agents retry. Keying on the call id means a retry
        # replays the same confirmation instead of booking a second meeting.
        key = conversation or f"slot:{slot_id}"
        conn = db()
        prior = conn.execute("SELECT * FROM bookings WHERE conversation_id=?", (key,)).fetchone()
        if prior:
            conn.close()
            log(f"[voice] Duplicate book_meeting for {key} — replaying confirmation")
            return self._json(voice.reply_booked(
                datetime.fromisoformat(prior["start_at"]), prior["meet_link"], prior["email"]))

        offer = voice.take_offer(slot_id)
        if not offer:
            conn.close()
            log(f"[voice] Unknown or expired slot_id {slot_id!r} for {key}")
            return self._json(voice.reply_slot_gone())

        lead = {
            "full_name": name, "email": email,
            "phone": (data.get("caller_phone") or "").strip(),
            "company": (data.get("company") or "").strip(),
            "project_type": (data.get("project_type") or "other").strip(),
            "budget_band": (data.get("budget_band") or "not_disclosed").strip(),
            "notes": (data.get("notes") or "").strip(),
            "lead_source": (data.get("lead_source") or "").strip(),
        }
        try:
            # Two callers can be quoted the same time within the same minute.
            if not voice.is_still_free(offer["start"], offer["duration"]):
                conn.close()
                log(f"[voice] Slot {offer['start']} was taken before {key} confirmed")
                return self._json(voice.reply_slot_gone())
            event_id, meet_link = voice.create_event(offer["start"], offer["duration"], lead)
        except Exception as ex:
            conn.close()
            log(f"[voice] Booking failed for {key}: {ex}")
            return self._json(voice.reply_book_failed())

        # Land it in the normal lead pipeline so it shows up in /admin/ and
        # fires the same phone alerts as a web enquiry.
        record = {
            "name": name, "email": email, "phone": lead["phone"],
            "company": lead["company"], "website": "",
            "service": voice.PROJECT_LABELS.get(lead["project_type"], lead["project_type"]),
            "budget": voice.BUDGET_LABELS.get(lead["budget_band"], ""),
            "message": (f"Call booked for {voice.spoken(offer['start'])} (IST).\n\n"
                        f"{lead['notes'] or '(no notes captured)'}"),
            "type": "voice-call",
            "source": lead["lead_source"] or "voice-agent",
            "consent": 1, "marketing": 0, "status": "new",
        }
        cur = conn.execute(
            """INSERT INTO enquiries
               (name,email,phone,company,website,service,budget,message,type,source,
                consent,marketing,status,ip,ua,spam_score,spam_reason,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'','',0,'',?)""",
            (record["name"], record["email"], record["phone"], record["company"],
             record["website"], record["service"], record["budget"], record["message"],
             record["type"], record["source"], record["consent"], record["marketing"],
             record["status"], now_iso()),
        )
        enquiry_id = cur.lastrowid
        conn.execute(
            """INSERT INTO bookings
               (conversation_id,enquiry_id,name,email,phone,company,project_type,
                budget_band,notes,start_at,duration_min,event_id,meet_link,
                lead_source,status,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,'booked',?)""",
            (key, enquiry_id, name, email, lead["phone"], lead["company"],
             lead["project_type"], lead["budget_band"], lead["notes"],
             offer["start"].isoformat(), offer["duration"], event_id, meet_link,
             lead["lead_source"], now_iso()),
        )
        conn.commit()
        conn.close()
        threading.Thread(target=alert_new_enquiry, args=(record,), daemon=True).start()
        log(f"[voice] Booked {name} <{email}> for {offer['start']} ({key})")
        return self._json(voice.reply_booked(offer["start"], meet_link, email))

    def voice_post_call(self, data, conversation):
        """Called once after the call ends, whether or not anything was booked."""
        key = conversation or ""
        summary = (data.get("summary") or "").strip()
        name = (data.get("caller_name") or "").strip()
        phone = (data.get("caller_phone") or "").strip()
        conn = db()
        booking = conn.execute("SELECT enquiry_id FROM bookings WHERE conversation_id=?",
                               (key,)).fetchone() if key else None

        if booking and booking["enquiry_id"]:
            conn.execute("UPDATE enquiries SET notes=? WHERE id=?",
                         (summary, booking["enquiry_id"]))
            conn.commit()
            conn.close()
            log(f"[voice] Call summary attached to enquiry #{booking['enquiry_id']}")
            return self._json({"ok": True})

        # Nobody booked. The call is still a lead worth chasing, so it goes into
        # the same inbox with status 'new' rather than disappearing.
        if not (name or phone):
            conn.close()
            log(f"[voice] Post-call with no caller details ({key or 'no id'}) — ignored")
            return self._json({"ok": True})
        record = {
            "name": name or "Unknown caller", "email": (data.get("email") or "").strip().lower(),
            "phone": phone, "company": "", "website": "", "service": "", "budget": "",
            "message": summary or "Voice call ended without a booking.",
            "type": "voice-call",
            "source": (data.get("lead_source") or "").strip() or "voice-agent",
            "consent": 0, "marketing": 0, "status": "new",
        }
        conn.execute(
            """INSERT INTO enquiries
               (name,email,phone,company,website,service,budget,message,type,source,
                consent,marketing,status,ip,ua,spam_score,spam_reason,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'','',0,'',?)""",
            (record["name"], record["email"], record["phone"], record["company"],
             record["website"], record["service"], record["budget"], record["message"],
             record["type"], record["source"], record["consent"], record["marketing"],
             record["status"], now_iso()),
        )
        conn.commit()
        conn.close()
        threading.Thread(target=alert_new_enquiry, args=(record,), daemon=True).start()
        log(f"[voice] Unbooked call from {record['name']} saved as a lead")
        return self._json({"ok": True})

    # ───────────── API: PATCH ─────────────
    def api_patch(self):
        acc = self._account()
        if not acc:
            return self._json({"error": "Unauthorized"}, 401)
        is_admin = (acc.get("role") or "author") == "admin"
        data = self._body()
        # Authors may only edit their own blog posts; everything else is admin-only.
        if not is_admin and not re.match(r"^/api/admin/posts/\d+$", self.path):
            return self._json({"error": "This action is restricted to the main admin account."}, 403)

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

        m = re.match(r"^/api/admin/testimonials/(\d+)$", self.path)
        if m:
            tid = int(m.group(1))
            allowed = ("name", "role", "quote", "photo", "rating", "sort", "active")
            ints = {"rating", "sort", "active"}
            fields, vals = [], []
            for k in allowed:
                if k in data:
                    fields.append(f"{k}=?")
                    vals.append(int(data[k]) if k in ints else data[k])
            if not fields:
                return self._json({"error": "Nothing to update."}, 400)
            vals.append(tid)
            conn = db()
            conn.execute(f"UPDATE testimonials SET {','.join(fields)} WHERE id=?", vals)
            conn.commit()
            conn.close()
            return self._json({"ok": True})

        m = re.match(r"^/api/admin/portfolio/(\d+)$", self.path)
        if m:
            pid = int(m.group(1))
            allowed = ("title", "client", "category", "image", "summary", "metric", "url", "sort", "active")
            ints = {"sort", "active"}
            fields, vals = [], []
            for k in allowed:
                if k in data:
                    fields.append(f"{k}=?")
                    vals.append(int(data[k]) if k in ints else data[k])
            if not fields:
                return self._json({"error": "Nothing to update."}, 400)
            vals.append(pid)
            conn = db()
            conn.execute(f"UPDATE portfolio SET {','.join(fields)} WHERE id=?", vals)
            conn.commit()
            conn.close()
            return self._json({"ok": True})

        m = re.match(r"^/api/admin/posts/(\d+)$", self.path)
        if m:
            pid = int(m.group(1))
            conn = db()
            row = conn.execute("SELECT * FROM posts WHERE id=?", (pid,)).fetchone()
            if not row:
                conn.close()
                return self._json({"error": "Post not found."}, 404)
            # Authors may only edit their own posts.
            if not is_admin and (row["author_email"] or "") != acc["email"]:
                conn.close()
                return self._json({"error": "Not your post."}, 403)
            allowed = ("title", "excerpt", "cover", "body", "tag", "author", "author_role",
                       "author_bio", "read_min", "meta_title", "meta_desc", "og_title",
                       "og_desc", "og_image", "status", "sort")
            ints = {"read_min", "sort"}
            fields, vals = [], []
            for k in allowed:
                if k in data:
                    # Only the admin can change publish status; authors keep it as-is.
                    if k == "status" and not is_admin:
                        continue
                    fields.append(f"{k}=?")
                    vals.append(int(data[k] or 0) if k in ints else data[k])
            # Slug: only regenerate when explicitly provided (keeps existing URLs stable).
            if data.get("slug"):
                fields.append("slug=?")
                vals.append(unique_slug(conn, data["slug"], exclude_id=pid))
            # Stamp published_at the first time a post goes live (admin only).
            if is_admin and data.get("status") == "published" and not row["published_at"]:
                fields.append("published_at=?")
                vals.append(now_iso())
            if not fields:
                conn.close()
                return self._json({"error": "Nothing to update."}, 400)
            fields.append("updated_at=?")
            vals.append(now_iso())
            vals.append(pid)
            conn.execute(f"UPDATE posts SET {','.join(fields)} WHERE id=?", vals)
            conn.commit()
            new_slug = conn.execute("SELECT slug FROM posts WHERE id=?", (pid,)).fetchone()["slug"]
            conn.close()
            return self._json({"ok": True, "slug": new_slug})

        # Admin only: rename an author or reset their password.
        m = re.match(r"^/api/admin/accounts/(\d+)$", self.path)
        if m:
            aid = int(m.group(1))
            conn = db()
            row = conn.execute("SELECT * FROM admins WHERE id=?", (aid,)).fetchone()
            if not row:
                conn.close()
                return self._json({"error": "Account not found."}, 404)
            fields, vals = [], []
            if "name" in data:
                fields.append("name=?")
                vals.append((data.get("name") or "").strip())
            if data.get("password"):
                if len(data["password"]) < 8:
                    conn.close()
                    return self._json({"error": "Password must be at least 8 characters."}, 400)
                h, s = hash_password(data["password"])
                fields += ["pw_hash=?", "pw_salt=?"]
                vals += [h, s]
            if not fields:
                conn.close()
                return self._json({"error": "Nothing to update."}, 400)
            vals.append(aid)
            conn.execute(f"UPDATE admins SET {','.join(fields)} WHERE id=?", vals)
            conn.commit()
            conn.close()
            return self._json({"ok": True})

        return self._json({"error": "Not found"}, 404)

    # ───────────── API: DELETE ─────────────
    def api_delete(self):
        acc = self._account()
        if not acc:
            return self._json({"error": "Unauthorized"}, 401)
        is_admin = (acc.get("role") or "author") == "admin"
        # Authors may only delete their own blog posts; everything else is admin-only.
        if not is_admin and not re.match(r"^/api/admin/posts/\d+$", self.path):
            return self._json({"error": "This action is restricted to the main admin account."}, 403)
        # Empty the spam quarantine in one go (must be matched before /(\d+)$).
        if self.path == "/api/admin/enquiries/spam":
            conn = db()
            n = conn.execute("SELECT COUNT(*) n FROM enquiries WHERE status='spam'").fetchone()["n"]
            conn.execute("DELETE FROM enquiries WHERE status='spam'")
            conn.commit()
            conn.close()
            return self._json({"ok": True, "deleted": n})
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
        m = re.match(r"^/api/admin/testimonials/(\d+)$", self.path)
        if m:
            conn = db()
            conn.execute("DELETE FROM testimonials WHERE id=?", (int(m.group(1)),))
            conn.commit()
            conn.close()
            return self._json({"ok": True})
        m = re.match(r"^/api/admin/portfolio/(\d+)$", self.path)
        if m:
            conn = db()
            conn.execute("DELETE FROM portfolio WHERE id=?", (int(m.group(1)),))
            conn.commit()
            conn.close()
            return self._json({"ok": True})
        m = re.match(r"^/api/admin/posts/(\d+)$", self.path)
        if m:
            pid = int(m.group(1))
            conn = db()
            if not is_admin:
                row = conn.execute("SELECT author_email FROM posts WHERE id=?", (pid,)).fetchone()
                if row and (row["author_email"] or "") != acc["email"]:
                    conn.close()
                    return self._json({"error": "Not your post."}, 403)
            conn.execute("DELETE FROM posts WHERE id=?", (pid,))
            conn.commit()
            conn.close()
            return self._json({"ok": True})
        # Admin only: delete an author account (never yourself or another admin).
        m = re.match(r"^/api/admin/accounts/(\d+)$", self.path)
        if m:
            aid = int(m.group(1))
            conn = db()
            row = conn.execute("SELECT * FROM admins WHERE id=?", (aid,)).fetchone()
            if not row:
                conn.close()
                return self._json({"error": "Account not found."}, 404)
            if row["email"] == acc["email"]:
                conn.close()
                return self._json({"error": "You can't delete your own account."}, 400)
            if (row["role"] or "author") == "admin":
                conn.close()
                return self._json({"error": "You can't delete an admin account."}, 400)
            conn.execute("DELETE FROM admins WHERE id=?", (aid,))
            conn.commit()
            conn.close()
            return self._json({"ok": True})
        return self._json({"error": "Not found"}, 404)


def main():
    init_db()
    conn = db()
    purge_old_spam(conn)          # keep the quarantine trimmed on every restart
    conn.close()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Evision Infoserve server running:")
    print(f"  Bound  ->  {HOST}:{PORT}")
    print(f"  Spam   ->  quarantine at score >= {SPAM_THRESHOLD}, kept {SPAM_RETENTION_DAYS} days")
    print(f"  Site   ->  http://localhost:{PORT}/")
    print(f"  Admin  ->  http://localhost:{PORT}/admin/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
