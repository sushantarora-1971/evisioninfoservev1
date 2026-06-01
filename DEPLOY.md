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
