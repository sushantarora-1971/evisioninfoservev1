#!/usr/bin/env python3
"""
One-time helper: mint the Google Calendar refresh token the voice agent needs.

A service account would need RS256 to sign its JWT, which the standard library
cannot do (and this project takes no pip installs). A refresh token needs no
signing, and works on a plain Gmail account without Workspace admin rights.

Before running, create the OAuth client in Google Cloud Console:

  1. console.cloud.google.com -> APIs & Services -> Library -> enable
     "Google Calendar API".
  2. OAuth consent screen -> External -> add the calendar owner's Google account
     under "Test users". (Leave it in Testing; no verification needed.)
  3. Credentials -> Create credentials -> OAuth client ID -> "Desktop app".
  4. Copy the client ID and secret into the prompts below.

Then:

    python scripts/google_calendar_setup.py

It prints the three env vars to set. The refresh token does not expire while the
app stays in Testing and is used at least every six months.
"""

import json
import sys
import urllib.parse
import urllib.request

SCOPE = "https://www.googleapis.com/auth/calendar"
# Google's documented loopback flow for desktop clients: the code is shown in
# the browser and pasted back here, so this script needs no local web server.
REDIRECT = "urn:ietf:wg:oauth:2.0:oob"


def main():
    print(__doc__)
    client_id = input("OAuth client ID     : ").strip()
    client_secret = input("OAuth client secret : ").strip()
    if not client_id or not client_secret:
        sys.exit("Both values are required.")

    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": REDIRECT,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",          # forces a refresh_token every time
    })
    print("\n1. Open this URL, sign in as the calendar owner, and approve:\n")
    print("   " + auth_url + "\n")
    print("2. Google shows you a code. Paste it here.\n")
    code = input("Authorization code  : ").strip()
    if not code:
        sys.exit("No code entered.")

    body = urllib.parse.urlencode({
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT,
        "grant_type": "authorization_code",
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=body,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            payload = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        sys.exit(f"\nGoogle rejected the exchange: {e.read().decode('utf-8', 'replace')[:500]}")

    refresh = payload.get("refresh_token")
    if not refresh:
        sys.exit("No refresh_token came back. Re-run and make sure you approved a fresh consent.")

    print("\n" + "=" * 68)
    print("Set these on the server (deploy/evision.service, or your shell):\n")
    print(f"GOOGLE_CLIENT_ID={client_id}")
    print(f"GOOGLE_CLIENT_SECRET={client_secret}")
    print(f"GOOGLE_REFRESH_TOKEN={refresh}")
    print("\nAlso set, if you have not already:")
    print("VOICE_SHARED_SECRET=<a long random string, same value in the ElevenLabs tools>")
    print("VOICE_HOST_EMAIL=<who the caller is meeting, e.g. you@evisioninfoserve.com>")
    print("=" * 68)


if __name__ == "__main__":
    main()
