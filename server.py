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
                     ("marketing", "marketing INTEGER DEFAULT 0")):
        if col not in existing_cols:
            c.execute(f"ALTER TABLE enquiries ADD COLUMN {ddl}")
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
            "INSERT INTO admins (email, pw_hash, pw_salt, created_at) VALUES (?,?,?,?)",
            (SEED_EMAIL.lower(), h, s, now_iso()),
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

# ── Clean / hierarchical URLs ──────────────────────────────────────────────
# Map each file to its pretty URL. The server serves the file at the clean URL
# and 301-redirects the old .html URL to it.
_SEO_CHILDREN = ["ai-seo", "llm-optimization", "agentic-ai-seo", "enterprise-seo",
                 "ecommerce-seo", "technical-seo", "local-seo", "multilingual-seo",
                 "link-building", "white-label-seo", "seo-audit", "industry-seo"]
_CONTENT_CHILDREN = ["content-writing", "guest-posting", "digital-pr"]
FILE_TO_CLEAN = {
    "index.html": "/",
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


def notify_new_enquiry(e):
    """Email the admin about a new enquiry. Runs in a background thread so the
    visitor's request is never blocked. Degrades gracefully if SMTP is unset."""
    label = {"audit": "Free Audit", "get-started": "Get Started"}.get(e.get("type"), "Quote")
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
        author_box = (
            '<div class="author-box"><div class="av">' + e(initials) + '</div><div>'
            '<div class="an">' + e(post["author"]) + '</div>'
            '<div class="ar">' + e(role) + '</div></div></div>'
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
<link rel="icon" type="image/svg+xml" href="/assets/favicon.svg?v=1">
<meta name="robots" content="noindex, nofollow"><!-- DEV PHASE: remove before launch -->
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
<link rel="stylesheet" href="/assets/tokens.css?v=4">
<link rel="stylesheet" href="/assets/site.css?v=4">
<link rel="stylesheet" href="/assets/chrome.css?v=4">
<link rel="stylesheet" href="/assets/blog.css?v=1">
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
    <div><h2 class="h-lg" style="color:#fff;max-width:20ch">Want results like this for your brand?</h2><p class="lead" style="margin-top:12px;color:var(--fg-muted-dark)">Get a free SEO + AI-visibility audit and see where you stand today.</p></div>
    <a href="/contact.html" class="btn btn-primary btn-lg">Get a Free Audit</a>
  </div>
</section>

<script src="/assets/site.js?v=4"></script>
<script src="/assets/chrome.js?v=4"></script>
</body>
</html>"""


# ───────────────────────── request handler ─────────────────────────

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def log_message(self, fmt, *args):
        # Quieter logging
        pass

    def end_headers(self):
        # DEV PHASE — block all indexing until launch. Remove this header before going live.
        self.send_header("X-Robots-Tag", "noindex, nofollow")
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

    def _redirect301(self, location):
        self.send_response(301)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    # ---- dispatch ----
    def do_GET(self):
        raw = self.path.split("?")[0]
        if raw.startswith("/api/"):
            return self.api_get()
        # Old .html URL → 301 to the clean URL.
        fname = raw[1:] if raw.startswith("/") else raw
        if fname in FILE_TO_CLEAN:
            return self._redirect301(FILE_TO_CLEAN[fname])
        # Clean URL → serve the underlying file.
        clean = raw.rstrip("/") or "/"
        if clean in CLEAN_TO_FILE:
            self.path = "/" + CLEAN_TO_FILE[clean]
            return super().do_GET()
        # Blog article: /blog/<slug> → server-render the post (SEO meta + OG tags).
        m = re.match(r"^/blog/([a-z0-9][a-z0-9-]*)$", clean)
        if m:
            return self.serve_post(m.group(1))
        # Everything else (assets, /admin/, etc.) served as-is.
        return super().do_GET()

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
        conn.close()
        allowed = row and (row["status"] == "published" or (preview_tok and session_email(preview_tok)))
        if not allowed:
            self.send_error(404, "Post not found")
            return
        body = render_post_page(dict(row)).encode("utf-8")
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
        if path == "/api/admin/testimonials":
            if not self._require_auth():
                return
            conn = db()
            rows = conn.execute("SELECT * FROM testimonials ORDER BY sort, id").fetchall()
            conn.close()
            return self._json([dict(r) for r in rows])
        if path == "/api/admin/portfolio":
            if not self._require_auth():
                return
            conn = db()
            rows = conn.execute("SELECT * FROM portfolio ORDER BY sort, id").fetchall()
            conn.close()
            return self._json([dict(r) for r in rows])
        if path == "/api/admin/posts":
            if not self._require_auth():
                return
            conn = db()
            rows = conn.execute(
                """SELECT id,slug,title,excerpt,cover,tag,author,status,read_min,
                          created_at,updated_at,published_at
                   FROM posts ORDER BY id DESC"""
            ).fetchall()
            conn.close()
            return self._json([dict(r) for r in rows])
        m = re.match(r"^/api/admin/posts/(\d+)$", path)
        if m:
            if not self._require_auth():
                return
            conn = db()
            row = conn.execute("SELECT * FROM posts WHERE id=?", (int(m.group(1)),)).fetchone()
            conn.close()
            if not row:
                return self._json({"error": "Post not found."}, 404)
            return self._json(dict(row))
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
            if not self._require_auth():
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
            if not self._require_auth():
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

        # Admin: create a blog post
        if path == "/api/admin/posts":
            if not self._require_auth():
                return
            title = (data.get("title") or "").strip()
            if not title:
                return self._json({"error": "Title is required."}, 400)
            status = "published" if (data.get("status") == "published") else "draft"
            conn = db()
            slug = unique_slug(conn, data.get("slug") or title)
            now = now_iso()
            cur = conn.execute(
                """INSERT INTO posts
                   (slug,title,excerpt,cover,body,tag,author,author_role,read_min,
                    meta_title,meta_desc,og_title,og_desc,og_image,status,sort,
                    created_at,updated_at,published_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (slug, title, (data.get("excerpt") or "").strip(), (data.get("cover") or "").strip(),
                 data.get("body") or "", (data.get("tag") or "").strip(),
                 (data.get("author") or "").strip(), (data.get("author_role") or "").strip(),
                 int(data.get("read_min") or 5), (data.get("meta_title") or "").strip(),
                 (data.get("meta_desc") or "").strip(), (data.get("og_title") or "").strip(),
                 (data.get("og_desc") or "").strip(), (data.get("og_image") or "").strip(),
                 status, int(data.get("sort") or 0), now, now,
                 now if status == "published" else ""),
            )
            conn.commit()
            pid = cur.lastrowid
            conn.close()
            return self._json({"ok": True, "id": pid, "slug": slug}, 201)

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
            allowed = ("title", "excerpt", "cover", "body", "tag", "author", "author_role",
                       "read_min", "meta_title", "meta_desc", "og_title", "og_desc",
                       "og_image", "status", "sort")
            ints = {"read_min", "sort"}
            fields, vals = [], []
            for k in allowed:
                if k in data:
                    fields.append(f"{k}=?")
                    vals.append(int(data[k] or 0) if k in ints else data[k])
            # Slug: only regenerate when explicitly provided (keeps existing URLs stable).
            if data.get("slug"):
                fields.append("slug=?")
                vals.append(unique_slug(conn, data["slug"], exclude_id=pid))
            # Stamp published_at the first time a post goes live.
            if data.get("status") == "published" and not row["published_at"]:
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
            conn = db()
            conn.execute("DELETE FROM posts WHERE id=?", (int(m.group(1)),))
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
