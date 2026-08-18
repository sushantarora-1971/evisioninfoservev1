# Evision Infoserve — Website + Admin Panel

Marketing site for Evision Infoserve (Greater Noida digital marketing agency),
plus a lightweight, zero-dependency Python backend with an authenticated admin
panel for managing enquiries and clients.

## Features

- **Static marketing site** — Home, Services (SEO, Social, PPC, Content, ORM, AI), Pricing, Blog, About, Contact.
- **Free Audit popup** — site-wide modal (opens from every "Get a Free Audit" / "Request a Quote" CTA) with a required Terms & marketing-consent checkbox.
- **Enquiry capture** — the contact form and audit popup post real submissions to the backend.
- **Admin panel** (`/admin/`) — login-protected dashboard to view enquiries (quote + audit), manage clients, convert enquiries to clients, and change the admin password.
- **Instant lead alerts** — a new enquiry pushes to your phone (Telegram / ntfy / an actual phone call) plus email, and rings in the admin panel.
- **Spam filter** — bot submissions are scored and quarantined instead of landing in the inbox (see below).

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

## Instant lead alerts (phone)

Email is too slow to call someone back while they're still on the site, so a new
(non-spam) enquiry also pushes straight to your phone. Every channel is optional
— set its env vars and restart. Test any time with:

```bash
python scripts/test_alert.py     # sends a fake lead through every live channel
```

### Telegram — free, instant, recommended

1. In Telegram, message **@BotFather** → `/newbot` → pick a name. It replies with
   a token like `8123456:AAF…`.
2. Open your new bot and tap **Start** (Telegram won't deliver until you do).
3. Set `TELEGRAM_BOT_TOKEN`, restart, and run `python scripts/test_alert.py` —
   it prints the `TELEGRAM_CHAT_ID` to set. Restart once more.

You get the lead's name, phone, service, budget and message, with a **WhatsApp
them** button that opens the chat with a greeting pre-typed. Add your team to a
Telegram group and use the group's chat ID so everyone is alerted at once.

### ntfy — free, loud

Install the **ntfy** app (Android/iOS), subscribe to a topic nobody could guess
(e.g. `evision-leads-7f3a91`), set `NTFY_TOPIC` to it. Alerts arrive at `urgent`
priority, which rings through a silenced phone. Anyone who knows the topic name
can read your alerts, so keep it long and random.

### A real phone call — paid

With Twilio credentials set, a new lead makes your phone actually ring and a
voice reads out who it is (~₹2/call).

```
TELEGRAM_BOT_TOKEN=8123456:AAF…
TELEGRAM_CHAT_ID=987654321
NTFY_TOPIC=evision-leads-7f3a91
NTFY_SERVER=https://ntfy.sh          # only if you self-host
TWILIO_SID=AC…
TWILIO_TOKEN=…
TWILIO_FROM=+15550001111             # your Twilio number
ALERT_PHONE=+919311221517            # the phone to ring
ALERT_SKIP_TYPES=newsletter          # types that email only, no phone alert
```

### While the admin panel is open

The dashboard polls every 30 seconds and chimes on a new lead, with a desktop
notification and a tab-title badge. Toggle it with the **🔔 Alerts** button on
the dashboard (the browser needs one click on the page before it will play
sound).

## Spam filtering

Every `/api/enquiry` submission is scored (`score_enquiry` in `server.py`). At or
above **60 points** it is stored with `status='spam'`: no email alert, no "new"
badge, hidden from the enquiries list until you pick the **Spam** status filter.
Nothing is auto-deleted, so a false positive is one "Not spam — restore" click
away. Quarantined rows are purged after 30 days.

What it looks at:

| Signal | Points |
| --- | --- |
| Honeypot field filled (hidden input no human sees) | 100 |
| Throwaway / blocklisted email domain | 100 |
| Automated user-agent (`python-requests`, `curl`, …) | 100 |
| Form submitted in under 3 seconds | 60 |
| Posted from another site / no `Origin` + `Referer` | 60 / 45 |
| Guest-post, backlink, casino, loan… phrases | 50 |
| Links in the message | 40–60 |
| Phone number already used by a different sender | 45 |
| Several different senders from one IP in an hour | 60 |
| Company name identical to the person's name | 35 |
| Quote request with an empty message | 35 |

A genuine lead trips none of these; a visitor who grabs three lead magnets and
then asks for a quote still scores 0. One IP is also hard-capped at 12
submissions/hour (429), which stops a bot loop from filling the database.

Tune without editing code:

```
SPAM_THRESHOLD=60           # lower = stricter
SPAM_DOMAINS=foo.com,bar.io # extra blocked email domains
SPAM_RETENTION_DAYS=30      # how long quarantined spam is kept
ENQUIRY_RATE_HOUR=12        # hard cap per IP per hour
ENQUIRY_RATE_DAY=40
```

Junk that arrived **before** the filter existed can be swept up with:

```bash
python scripts/rescore_enquiries.py            # dry run — shows what it would flag
python scripts/rescore_enquiries.py --apply    # move those rows to Spam
```

If spam ever gets through, add its domain to `SPAM_DOMAINS`, restart, and run the
rescore script. If a determined bot starts faking browser headers and delays, the
next step is a CAPTCHA — Cloudflare Turnstile is free and drops into the contact
form plus a token check in `/api/enquiry`.

## Voice booking agent (ElevenLabs)

An ElevenLabs phone agent can qualify a caller and book a meeting on Google
Calendar during the call. Booked or not, **every call lands in `enquiries` as
`type='voice-call'`**, so it appears in `/admin/` and fires the same phone
alerts as a web enquiry — a call that ends without a booking is still a lead.

Three endpoints, all authenticated with a shared secret header
(`X-Voice-Secret`), all in `voice_booking.py` + the `voice_*` handlers in
`server.py`:

| Endpoint | Called when | Does |
| --- | --- | --- |
| `POST /api/voice/check-availability` | mid-call | Returns up to 3 free slots as opaque `slot_id`s |
| `POST /api/voice/book-meeting` | caller says yes | Creates the Calendar event + Meet link, saves the lead |
| `POST /api/voice/post-call` | call ends | Attaches the summary, or saves an unbooked call as a lead |

### Setup

```bash
python scripts/google_calendar_setup.py    # prints the three GOOGLE_* env vars
```

Then set these and restart:

```
VOICE_SHARED_SECRET=<long random string — same value in the ElevenLabs tools>
VOICE_HOST_EMAIL=you@evisioninfoserve.com   # who the caller is meeting
GOOGLE_CLIENT_ID=…
GOOGLE_CLIENT_SECRET=…
GOOGLE_REFRESH_TOKEN=…
GOOGLE_CALENDAR_ID=primary
```

Attach `deploy/elevenlabs_server_tools.json` to the agent, replacing `BASE_URL`
(use `ngrok http 8000` while testing) and the secret. Until
`VOICE_SHARED_SECRET` is set the endpoints return 404, so a half-configured
server exposes nothing.

Google auth uses an **OAuth refresh token, not a service account** — signing a
service-account JWT needs RS256, which the standard library cannot do, and this
project takes no pip installs. It also avoids Workspace domain-wide delegation.

### Booking rules

Tunable by env var; the defaults are in `voice_booking.py`.

| Rule | Default | Why |
| --- | --- | --- |
| Working hours | Mon–Fri 10–19, Sat 10–17, Sun closed | `VOICE_DAY_START` / `VOICE_DAY_END` / `VOICE_SAT_END` |
| Buffer around existing events | 15 min | Never books you back-to-back (`VOICE_BUFFER_MIN`) |
| Minimum lead time | 3 hours | Never books you into the meeting you are in (`VOICE_LEAD_HOURS`) |
| Slots offered | 3, spread across the day | Three consecutive half-hours is not a real choice |
| Preferred day full | rolls forward up to 3 days | The agent is told to say the date changed |

Two behaviours matter on a live line. Every response is an **instruction to the
agent**, never raw data — a voice model handed JSON will read it aloud. And
every failure answers **HTTP 200** with a graceful script (apologise, promise a
WhatsApp follow-up): an error status mid-call makes the agent freeze or invent a
confirmation at the caller.

Booking is idempotent on the ElevenLabs conversation id, so a dropped line and a
retry replay the same confirmation instead of double-booking.

```bash
python scripts/test_voice_slots.py    # 22 offline tests, no credentials needed
```

## Project layout

```
server.py              # site + JSON API server
voice_booking.py       # voice agent: slot arithmetic + Google Calendar
index.html, *.html     # marketing pages
assets/                # css + js (chrome.js injects shared chrome + audit modal + honeypots)
admin/                 # admin login + dashboard
scripts/               # one-off maintenance (e.g. rescore_enquiries.py)
deploy/                # nginx + systemd unit + ElevenLabs tool config
evision.db             # SQLite data (git-ignored)
```

> Note: this is intended for local/internal use. Put it behind HTTPS before exposing publicly.
