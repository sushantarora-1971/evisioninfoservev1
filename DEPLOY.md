# Deploy on a Hostinger VPS (Ubuntu) — alongside an existing site

This runs the app via **systemd + a Python venv**, with **Nginx** reverse-proxying
on a **dedicated port `8080`**. Your existing website on ports 80/443 is not touched.

Final URL: **`http://YOUR_VPS_IP:8080/`**  (admin at `/admin/`).

> Run these as a user with sudo. Replace `YOUR_VPS_IP` with your server's IP.

## 1. Install prerequisites

```bash
sudo apt update
sudo apt install -y python3 python3-venv git
# nginx is already installed since you have a site running
```

## 2. Get the code

```bash
sudo git clone https://github.com/sushantarora-1971/evisioninfoservev1.git /var/www/evisioninfoservev1
cd /var/www/evisioninfoservev1
```

## 3. Create the virtualenv

The app uses only the Python standard library, so there's nothing to `pip install` —
the venv just isolates the interpreter.

```bash
sudo python3 -m venv .venv
```

## 4. Give the service user ownership (so it can write the database)

```bash
sudo chown -R www-data:www-data /var/www/evisioninfoservev1
```

## 5. Install & start the systemd service

```bash
sudo cp deploy/evision.service /etc/systemd/system/evision.service
sudo systemctl daemon-reload
sudo systemctl enable --now evision
sudo systemctl status evision --no-pager
```

Verify the app answers locally (should print HTML):

```bash
curl -s http://127.0.0.1:8000/ | head -n 5
```

## 6. Add the Nginx server block (port 8080)

```bash
sudo cp deploy/nginx-evision.conf /etc/nginx/sites-available/evision.conf
sudo ln -s /etc/nginx/sites-available/evision.conf /etc/nginx/sites-enabled/
sudo nginx -t          # must say "syntax is ok" / "test is successful"
sudo systemctl reload nginx
```

## 7. Open the port in the firewall

```bash
# If ufw is active:
sudo ufw allow 8080/tcp
```

**Also open port 8080** in the **Hostinger control panel firewall** (hPanel → VPS →
Firewall), or the connection will time out even though Nginx is listening.

## 8. Test

Open **`http://YOUR_VPS_IP:8080/`** in a browser. Admin panel: **`/admin/`**.

Default login (change it immediately under Settings):
- Email: `evisiononweb@gmail.com`
- Password: `Evision@2026`

---

## Updating later

```bash
cd /var/www/evisioninfoservev1
sudo -u www-data git pull
sudo systemctl restart evision
```

## Enabling email alerts

Edit the service file, uncomment the `SMTP_*` lines, then:

```bash
sudo systemctl daemon-reload && sudo systemctl restart evision
```

## Enabling phone alerts on new leads

Same file, the `TELEGRAM_* / NTFY_* / TWILIO_*` block (setup steps are in the
README). After `daemon-reload` + `restart`, confirm it reaches your phone:

```bash
cd /var/www/evisioninfoservev1
sudo -u www-data .venv/bin/python scripts/test_alert.py
```

The script lists which channels are live, sends a test lead through each, and —
if you've set `TELEGRAM_BOT_TOKEN` but not `TELEGRAM_CHAT_ID` — prints the chat
ID you still need.

## Deploying the voice booking agent

The agent needs two things this deployment doesn't have yet: **HTTPS on a real
domain** and **Google Calendar credentials**. Do them in this order — each step
is testable on its own, and the last one is useless without the first.

### 1. Ship the code

`scripts/` has never been committed, so a `git pull` on the server won't bring
it (this is also why `test_alert.py` and `rescore_enquiries.py`, referenced
above, aren't on the VPS):

```bash
git add scripts voice_booking.py deploy/elevenlabs_server_tools.json \
        deploy/nginx-evision-tls.conf deploy/evision.service README.md DEPLOY.md
git commit -m "Voice booking agent: ElevenLabs webhooks + Google Calendar"
git push
```

Then on the VPS:

```bash
cd /var/www/evisioninfoservev1
sudo -u www-data git pull
sudo systemctl restart evision
sudo journalctl -u evision -n 20 --no-pager    # should start clean
```

The slot maths needs the system timezone database. Ubuntu normally has it, but
check — the failure is otherwise a confusing 500 on the first call:

```bash
.venv/bin/python -c "from zoneinfo import ZoneInfo; print(ZoneInfo('Asia/Kolkata'))"
# ZoneInfoNotFoundError  ->  sudo apt install -y tzdata
```

Offline tests, no credentials needed — run them on the server to confirm the
deploy is sane:

```bash
.venv/bin/python scripts/test_voice_slots.py     # 22 tests
```

### 2. Put it on HTTPS

`http://YOUR_VPS_IP:8080` cannot be used: ElevenLabs calls the webhooks from
their own servers and requires HTTPS on a name.

1. Point an **A record** at the VPS — e.g. `voice.evisioninfoserve.com`.
2. Open **80 and 443** in ufw *and* in the Hostinger panel firewall (hPanel →
   VPS → Firewall). Certbot cannot issue a certificate until 80 is reachable.

```bash
sudo ufw allow 80/tcp && sudo ufw allow 443/tcp

sudo cp deploy/nginx-evision-tls.conf /etc/nginx/sites-available/evision-tls.conf
sudo nano /etc/nginx/sites-available/evision-tls.conf     # set server_name
sudo ln -s /etc/nginx/sites-available/evision-tls.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d voice.evisioninfoserve.com
```

Confirm before going further:

```bash
curl -sI https://voice.evisioninfoserve.com/ | head -n 1     # HTTP/1.1 200 OK
```

### 3. Mint the Google credentials

Create the OAuth client first (Cloud Console → enable **Google Calendar API** →
**OAuth consent screen** → External, add the calendar owner as a **test user** →
**Credentials** → OAuth client ID → **Desktop app**). Then, over SSH:

```bash
cd /var/www/evisioninfoservev1
.venv/bin/python scripts/google_calendar_setup.py
```

It prints a URL — open it on your laptop, approve as the calendar owner, paste
the code back into the SSH session. It prints the three `GOOGLE_*` values.

### 4. Set the environment

```bash
openssl rand -hex 32              # this is your VOICE_SHARED_SECRET
sudo systemctl edit --full evision
```

Uncomment and fill the `VOICE_*` and `GOOGLE_*` block, then:

```bash
sudo systemctl daemon-reload && sudo systemctl restart evision
```

> The secret is the only thing between the open internet and your calendar.
> Generate it, don't invent it.

### 5. Prove it works before touching ElevenLabs

```bash
curl -X POST https://voice.evisioninfoserve.com/api/voice/check-availability \
  -H "Content-Type: application/json" \
  -H "X-Voice-Secret: YOUR_SECRET" \
  -d '{"preferred_date":"2026-08-19","part_of_day":"any"}'
```

- Real slots that avoid your real meetings → done, go configure the agent.
- A "team will confirm by WhatsApp" instruction → the Google credentials are
  wrong. `journalctl -u evision -f` prints the exact Calendar API error.
- `404` → `VOICE_SHARED_SECRET` isn't set, or the service didn't restart.
- `401` → the secret in the header doesn't match the one in the unit file.

Finally, put `https://voice.evisioninfoserve.com` in as `BASE_URL` in both tools
in `deploy/elevenlabs_server_tools.json`, and attach them to the agent.

> **Don't enable the post-call webhook yet.** ElevenLabs signs those with HMAC
> and sends a different payload shape than `/api/voice/post-call` currently
> expects, so every delivery would be rejected. Booked calls still become leads
> via `book_meeting`; only unbooked-call logging is affected.

## Spam filter

On by default — see the README for how scoring works. Two deployment details
matter:

- The service binds `HOST=127.0.0.1` and nginx forwards `X-Forwarded-For`
  (already set in `nginx-evision.conf`). That pairing is what makes per-IP rules
  trustworthy: the header can only come from the proxy.
- Quarantined spam shows in the admin panel under **Enquiries → status "Spam"**,
  and `journalctl -u evision` logs one line per blocked submission with the
  reason. To sweep junk that arrived before the filter existed:

```bash
cd /var/www/evisioninfoservev1
sudo -u www-data .venv/bin/python scripts/rescore_enquiries.py          # dry run
sudo -u www-data .venv/bin/python scripts/rescore_enquiries.py --apply
```

## Logs / troubleshooting

```bash
sudo journalctl -u evision -f          # app logs (and enquiry notifications)
sudo tail -f /var/log/nginx/error.log  # proxy errors
```

- **502 Bad Gateway** → the app isn't running; check `systemctl status evision`.
- **Connection timed out** → port 8080 not open in ufw *and/or* Hostinger firewall.
- **DB permission error** → re-run the `chown` in step 4.

## Moving to a real domain + HTTPS (when ready)

1. Point a domain/subdomain's DNS **A record** at the VPS IP.
2. In `nginx-evision.conf`: change `listen 8080;` → `listen 80;` and
   `server_name _;` → `server_name yourdomain.com;`, reload nginx.
3. `sudo apt install -y certbot python3-certbot-nginx && sudo certbot --nginx -d yourdomain.com`
