#!/usr/bin/env python3
"""Send a fake lead through every configured alert channel, so you can check
your phone actually lights up before a real enquiry depends on it.

    python scripts/test_alert.py

Reads the same env vars as the server (TELEGRAM_*, NTFY_*, TWILIO_*, SMTP_*),
so run it the way the server runs — on the VPS:

    sudo systemctl show evision -p Environment      # confirm what's set
    sudo -u www-data .venv/bin/python scripts/test_alert.py

If TELEGRAM_BOT_TOKEN is set but TELEGRAM_CHAT_ID isn't, this prints the chat ID
of whoever messaged your bot last — that's the value you still need.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server  # noqa: E402

FAKE = {
    "name": "Test Lead (ignore)", "email": "test@example.com", "phone": "9811122233",
    "company": "Test Co", "service": "SEO Services", "budget": "Rs 25k - 50k",
    "message": "This is a test alert from scripts/test_alert.py — no action needed.",
    "type": "quote", "source": "alert self-test",
}


def find_chat_id():
    """Telegram won't tell you your chat ID until you message the bot once."""
    try:
        import json
        raw = server._http(
            f"https://api.telegram.org/bot{server.TELEGRAM_BOT_TOKEN}/getUpdates")
        for upd in reversed(json.loads(raw).get("result", [])):
            chat = (upd.get("message") or upd.get("channel_post") or {}).get("chat") or {}
            if chat.get("id"):
                who = chat.get("username") or chat.get("title") or chat.get("first_name") or ""
                return chat["id"], who
    except Exception as ex:
        print(f"  could not read getUpdates: {ex}")
    return None, None


def main():
    print("Configured channels:")
    checks = [
        ("email (SMTP)", bool(server.SMTP_HOST and server.SMTP_USER and server.SMTP_PASS)),
        ("telegram", bool(server.TELEGRAM_BOT_TOKEN and server.TELEGRAM_CHAT_ID)),
        ("ntfy", bool(server.NTFY_TOPIC)),
        ("phone call (twilio)", bool(server.TWILIO_SID and server.TWILIO_TOKEN
                                     and server.TWILIO_FROM and server.ALERT_PHONE)),
    ]
    for name, on in checks:
        print(f"  [{'x' if on else ' '}] {name}")

    if server.TELEGRAM_BOT_TOKEN and not server.TELEGRAM_CHAT_ID:
        print("\nTELEGRAM_BOT_TOKEN is set but TELEGRAM_CHAT_ID is missing.")
        print("Send your bot any message in Telegram, then re-run this. Looking now…")
        cid, who = find_chat_id()
        if cid:
            print(f"  → TELEGRAM_CHAT_ID={cid}   (from {who or 'your chat'})")
        else:
            print("  → no messages found yet. Open the bot in Telegram and tap Start.")

    if not any(on for _, on in checks):
        print("\nNothing configured yet — see the 'Instant lead alerts' section of the README.")
        return

    print("\nSending the test lead…")
    server.alert_new_enquiry(dict(FAKE))
    print("Done. Check your phone; anything that failed is logged above.")


if __name__ == "__main__":
    main()
