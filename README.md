# Evision Infoserve — Website + Admin Panel

Marketing site for Evision Infoserve (Greater Noida digital marketing agency),
plus a lightweight, zero-dependency Python backend with an authenticated admin
panel for managing enquiries and clients.

## Features

- **Static marketing site** — Home, Services (SEO, Social, PPC, Content, ORM, AI), Pricing, Blog, About, Contact.
- **Free Audit popup** — site-wide modal (opens from every "Get a Free Audit" / "Request a Quote" CTA) with a required Terms & marketing-consent checkbox.
- **Enquiry capture** — the contact form and audit popup post real submissions to the backend.
- **Admin panel** (`/admin/`) — login-protected dashboard to view enquiries (quote + audit), manage clients, convert enquiries to clients, and change the admin password.
- **Email alerts** — optional admin notification on every new enquiry (configurable SMTP).

## Tech

- Frontend: plain HTML/CSS/JS (no build step). Shared header/footer/widgets injected by `assets/chrome.js`.
- Backend: `server.py` — Python standard library only (`http.server` + `sqlite3`). No pip installs.
- Storage: SQLite (`evision.db`, created automatically; **git-ignored**).
- Auth: PBKDF2-HMAC-SHA256 password hashing + in-memory bearer tokens.

## Run it

```bash
python server.py
```

Then open:

- Site: http://localhost:8000/
- Admin: http://localhost:8000/admin/

### Default admin login

- Email: `evisiononweb@gmail.com`
- Password: `Evision@2026`  *(change it in the panel → Settings after first login)*

Override the seed via env vars before first run: `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `PORT`.

### Enable email notifications (optional)

Set these before starting the server (Gmail requires an App Password):

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASS=your-app-password
SMTP_FROM=you@gmail.com
NOTIFY_TO=info@evisioninfoserve.com
```

Without these, enquiries are still saved and shown in the admin panel — the server just logs instead of emailing.

## Project layout

```
server.py              # site + JSON API server
index.html, *.html     # marketing pages
assets/                # css + js (chrome.js injects shared chrome + audit modal)
admin/                 # admin login + dashboard
evision.db             # SQLite data (git-ignored)
```

> Note: this is intended for local/internal use. Put it behind HTTPS before exposing publicly.
