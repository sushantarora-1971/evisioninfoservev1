#!/usr/bin/env python3
"""
Evision Infoserve — voice agent booking (zero external dependencies).

Backs the three webhooks the ElevenLabs phone agent calls: find free slots,
book one, and log the call afterwards. server.py owns the routes, the database
and the lead alerts; this module owns the slot arithmetic and the Google
Calendar conversation.

Google auth uses an OAuth **refresh token**, not a service account, for two
reasons: signing a service-account JWT needs RS256 (impossible in the standard
library, and this project takes no pip installs), and a refresh token works on
a plain Gmail account without Workspace domain-wide delegation. Run
scripts/google_calendar_setup.py once to mint one.

Every network failure raises. Callers in server.py catch and hand the agent a
graceful script — an HTTP error mid-call makes a voice agent freeze or invent a
confirmation, which is worse than a lost booking.
"""

import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, time as dtime, timedelta, timezone
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

# ── Configuration ─────────────────────────────────────────────────────────
# The agent's shared secret. Endpoints stay closed until this is set, so a half
# configured server cannot leak calendar data to anyone who finds the URL.
SHARED_SECRET = os.environ.get("VOICE_SHARED_SECRET", "")

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REFRESH_TOKEN = os.environ.get("GOOGLE_REFRESH_TOKEN", "")
CALENDAR_ID = os.environ.get("GOOGLE_CALENDAR_ID", "primary")
# Who the caller is actually meeting — added to the invite so it lands in their
# calendar too, and so the Meet link has a host.
HOST_EMAIL = os.environ.get("VOICE_HOST_EMAIL", "")

# Working hours, Asia/Kolkata. Sunday is closed and has no entry.
DAY_START = int(os.environ.get("VOICE_DAY_START", "10"))
DAY_END = int(os.environ.get("VOICE_DAY_END", "19"))
SAT_END = int(os.environ.get("VOICE_SAT_END", "17"))

BUFFER_MINUTES = int(os.environ.get("VOICE_BUFFER_MIN", "15"))   # dead air around every event
LEAD_TIME_HOURS = int(os.environ.get("VOICE_LEAD_HOURS", "3"))   # never offer something imminent
GRID_MINUTES = 30      # candidate starts land on :00 and :30
MAX_SLOTS = 3          # a caller cannot hold more than three options in their head
SEARCH_DAYS = 3        # if the preferred day is full, look this many days further
OFFER_TTL = 10 * 60    # a quoted slot is held this long, then released

PART_OF_DAY = {
    "morning": (dtime(0, 0), dtime(13, 0)),
    "afternoon": (dtime(13, 0), dtime(17, 0)),
    "evening": (dtime(17, 0), dtime(23, 59)),
    "any": (dtime(0, 0), dtime(23, 59)),
}

# Readable labels for the admin panel and the lead alerts, so a voice lead reads
# like every other lead in the inbox instead of like an enum.
PROJECT_LABELS = {
    "new_website": "New website", "redesign": "Website redesign",
    "ecommerce": "Ecommerce", "web_app": "Web application",
    "seo_only": "SEO", "maintenance": "Maintenance", "other": "Other",
}
BUDGET_LABELS = {
    "under_50k": "Under ₹50k", "50k_150k": "₹50k–1.5L",
    "150k_500k": "₹1.5L–5L", "above_500k": "₹5L+", "not_disclosed": "",
}

# slot_id -> {"start", "duration", "expires", "conversation"}. In memory on
# purpose, exactly like SESSIONS in server.py: an offer is only alive for the
# minute between quoting it and the caller saying yes, so surviving a restart
# is not worth a table.
OFFERS = {}
_OFFER_LOCK = threading.Lock()

# Cached bearer token: {"token": str, "expires": float}
_TOKEN = {}
_TOKEN_LOCK = threading.Lock()


def enabled():
    """True when the webhooks should answer at all."""
    return bool(SHARED_SECRET)


def calendar_configured():
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and GOOGLE_REFRESH_TOKEN)


def secret_ok(supplied):
    return bool(SHARED_SECRET) and secrets.compare_digest(supplied or "", SHARED_SECRET)


# ── Slot arithmetic ───────────────────────────────────────────────────────
# Pure and offline: no network, no database. Everything these agents get wrong
# in production is decided here — offering a time twenty minutes from now,
# booking into the meeting you are currently in, offering three consecutive
# slots that are not a real choice — so it stays testable without credentials
# (scripts/test_voice_slots.py).

def working_window(day):
    """Opening and closing datetime for `day`, or None if closed."""
    weekday = day.weekday()
    if weekday == 6:                      # Sunday
        return None
    closes = SAT_END if weekday == 5 else DAY_END
    return (datetime.combine(day, dtime(DAY_START, 0), tzinfo=IST),
            datetime.combine(day, dtime(closes, 0), tzinfo=IST))


def _ceil_to_grid(moment):
    truncated = moment.replace(second=0, microsecond=0)
    remainder = truncated.minute % GRID_MINUTES
    if remainder:
        return truncated + timedelta(minutes=GRID_MINUTES - remainder)
    if moment != truncated:
        return truncated + timedelta(minutes=GRID_MINUTES)
    return truncated


def _collides(start, duration_minutes, busy):
    """True if a meeting at `start` would land inside a padded busy block."""
    end = start + timedelta(minutes=duration_minutes)
    pad = timedelta(minutes=BUFFER_MINUTES)
    return any(start < b_end + pad and end > b_start - pad for b_start, b_end in busy)


def free_starts(day, duration_minutes, part_of_day, now, busy):
    """Every bookable start time on `day`, in order."""
    window = working_window(day)
    if window is None:
        return []
    opens, closes = window
    part_from, part_to = PART_OF_DAY.get(part_of_day, PART_OF_DAY["any"])
    earliest = max(opens, datetime.combine(day, part_from, tzinfo=IST),
                   _ceil_to_grid(now + timedelta(hours=LEAD_TIME_HOURS)))
    latest = min(closes, datetime.combine(day, part_to, tzinfo=IST))

    starts, candidate = [], _ceil_to_grid(earliest)
    while candidate + timedelta(minutes=duration_minutes) <= latest:
        if not _collides(candidate, duration_minutes, busy):
            starts.append(candidate)
        candidate += timedelta(minutes=GRID_MINUTES)
    return starts


def pick_spread(starts, max_slots=MAX_SLOTS):
    """Thin a run of candidates down to options that feel like a real choice.

    Three consecutive half-hours is not a choice, so offer the first, the middle
    and the last of whatever is open.
    """
    if len(starts) <= max_slots:
        return list(starts)
    return [starts[i] for i in sorted({0, len(starts) // 2, len(starts) - 1})]


def find_slots(preferred_date, duration_minutes, part_of_day, now, busy):
    """Slots for the caller's preferred day, rolling forward if it is full.

    Returns (date_used, [start, ...]). `date_used` differs from `preferred_date`
    when the roll-forward kicked in and is None when nothing was open at all —
    the caller has to be told which, so the two stay distinguishable.
    """
    for offset in range(SEARCH_DAYS + 1):
        day = preferred_date + timedelta(days=offset)
        starts = free_starts(day, duration_minutes, part_of_day, now, busy)
        if starts:
            return day, pick_spread(starts)
        # A part-of-day preference is a preference, not a constraint. Once the
        # preferred day itself is exhausted, widen before sending the caller away.
        if offset == 0 and part_of_day != "any":
            starts = free_starts(day, duration_minutes, "any", now, busy)
            if starts:
                return day, pick_spread(starts)
    return None, []


def spoken(moment):
    """Phrase a slot the way the agent should say it out loud."""
    hour12 = moment.hour % 12 or 12
    meridiem = "AM" if moment.hour < 12 else "PM"
    return f"{moment:%A} {moment.day} {moment:%B} at {hour12}:{moment.minute:02d} {meridiem}"


# ── Slot offers ───────────────────────────────────────────────────────────

def hold_slots(starts, duration_minutes, conversation_id=""):
    """Register offered slots and return [(slot_id, start), ...].

    The id is a short opaque token, never a timestamp. The agent copies it back
    verbatim, so it never has to re-parse "three thirty on Thursday" into a
    datetime — which is precisely where these systems book the wrong day.
    """
    held, expires = [], time.time() + OFFER_TTL
    with _OFFER_LOCK:
        for start in starts:
            slot_id = secrets.token_urlsafe(6)
            OFFERS[slot_id] = {"start": start, "duration": duration_minutes,
                               "expires": expires, "conversation": conversation_id}
            held.append((slot_id, start))
        for sid in [s for s, o in OFFERS.items() if o["expires"] < time.time()]:
            OFFERS.pop(sid, None)
    return held


def take_offer(slot_id):
    """Resolve a slot_id to its offer, or None if unknown/expired."""
    with _OFFER_LOCK:
        offer = OFFERS.get(slot_id or "")
        if not offer:
            return None
        if offer["expires"] < time.time():
            OFFERS.pop(slot_id, None)
            return None
        return dict(offer)


# ── Google Calendar over plain HTTPS ──────────────────────────────────────

def _access_token():
    """A cached bearer token, refreshed a minute before it expires."""
    with _TOKEN_LOCK:
        if _TOKEN.get("token") and _TOKEN["expires"] > time.time():
            return _TOKEN["token"]
    body = urllib.parse.urlencode({
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "refresh_token": GOOGLE_REFRESH_TOKEN,
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=body,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=10) as r:
        payload = json.loads(r.read().decode())
    with _TOKEN_LOCK:
        _TOKEN["token"] = payload["access_token"]
        _TOKEN["expires"] = time.time() + int(payload.get("expires_in", 3600)) - 60
        return _TOKEN["token"]


def _api(url, payload=None, method="GET", timeout=15):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + _access_token(),
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:400]
        raise RuntimeError(f"Calendar API {e.code}: {detail}") from e


def _parse_rfc3339(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(IST)


def busy_intervals(from_day, through_day):
    """Busy blocks on the host calendar across an inclusive day range."""
    window_start = datetime.combine(from_day, dtime(0, 0), tzinfo=IST)
    window_end = datetime.combine(through_day + timedelta(days=1), dtime(0, 0), tzinfo=IST)
    result = _api("https://www.googleapis.com/calendar/v3/freeBusy", {
        "timeMin": window_start.isoformat(),
        "timeMax": window_end.isoformat(),
        "timeZone": "Asia/Kolkata",
        "items": [{"id": CALENDAR_ID}],
    }, method="POST")
    calendars = result.get("calendars", {})
    entry = calendars.get(CALENDAR_ID) or next(iter(calendars.values()), {})
    if entry.get("errors"):
        raise RuntimeError(f"Calendar freeBusy: {entry['errors']}")
    return [(_parse_rfc3339(b["start"]), _parse_rfc3339(b["end"]))
            for b in entry.get("busy", [])]


def is_still_free(start, duration_minutes):
    """Re-check one window immediately before booking it.

    Two callers can be quoted the same time within the same minute; without this
    the second one silently double-books the host.
    """
    busy = busy_intervals(start.date(), start.date())
    return not _collides(start, duration_minutes, busy)


def create_event(start, duration_minutes, lead):
    """Create the calendar event with a Meet link. Returns (event_id, meet_link)."""
    end = start + timedelta(minutes=duration_minutes)
    detail = " · ".join(filter(None, [
        lead.get("company"),
        PROJECT_LABELS.get(lead.get("project_type"), lead.get("project_type") or ""),
        BUDGET_LABELS.get(lead.get("budget_band"), ""),
    ]))
    description = "\n".join(filter(None, [
        "Booked by the Evision voice agent.",
        f"Caller  : {lead.get('full_name')}",
        f"Email   : {lead.get('email')}",
        f"Phone   : {lead.get('phone') or '—'}",
        f"Details : {detail or '—'}",
        f"Source  : {lead.get('lead_source') or 'phone'}",
        "",
        lead.get("notes") or "",
    ]))
    attendees = [{"email": lead["email"]}]
    if HOST_EMAIL:
        attendees.append({"email": HOST_EMAIL})
    body = {
        "summary": f"Evision — {lead.get('full_name')} ({detail or 'enquiry'})",
        "description": description,
        "start": {"dateTime": start.isoformat(), "timeZone": "Asia/Kolkata"},
        "end": {"dateTime": end.isoformat(), "timeZone": "Asia/Kolkata"},
        "attendees": attendees,
        "conferenceData": {"createRequest": {
            "requestId": secrets.token_hex(8),
            "conferenceSolutionKey": {"type": "hangoutsMeet"},
        }},
    }
    url = (f"https://www.googleapis.com/calendar/v3/calendars/"
           f"{urllib.parse.quote(CALENDAR_ID)}/events"
           f"?conferenceDataVersion=1&sendUpdates=all")
    event = _api(url, body, method="POST", timeout=25)
    return event.get("id", ""), event.get("hangoutLink", "")


# ── Agent-facing replies ──────────────────────────────────────────────────
# Every reply is an instruction to the model, not data for the caller. A voice
# agent handed raw JSON will read it aloud; telling it what to do next keeps it
# on rails.

def reply_slots(day_used, requested_date, held):
    lines = [f"{sid} = {spoken(start)}" for sid, start in held]
    if day_used != requested_date:
        preface = (f"Nothing was open on {requested_date:%A %d %B}. "
                   f"These are the next available times, on {day_used:%A %d %B} — "
                   "say that clearly to the caller before offering them.")
    else:
        preface = f"These times are open on {day_used:%A %d %B}."
    return {
        "slots": [{"slot_id": sid, "spoken": spoken(start)} for sid, start in held],
        "instruction": (
            f"{preface} Offer them in one natural sentence and let the caller pick. "
            "Never read the slot_id out loud and never invent a time that is not "
            "in this list. Once they choose, collect their full name and email, "
            "read the email back letter by letter to confirm it, then call "
            "book_meeting with that slot_id copied exactly. Slots: "
            + "; ".join(lines)
        ),
    }


def reply_nothing_free(requested_date):
    return {"slots": [], "instruction": (
        f"The calendar is full from {requested_date:%A %d %B} for the next few working days. "
        "Apologise briefly, tell the caller the team will message them on WhatsApp today "
        "with times, and confirm the best number to use. Do not offer a time yourself.")}


def reply_unavailable():
    """Calendar unreachable. Never surface an error to the caller."""
    return {"slots": [], "instruction": (
        "The calendar could not be reached. Do not mention a technical problem. "
        "Tell the caller you will have the team confirm a time by WhatsApp shortly, "
        "collect their name and the best number, and continue the conversation normally.")}


def reply_booked(start, meet_link, email):
    return {"booked": True, "instruction": (
        f"Booked for {spoken(start)} India time. Tell the caller it is confirmed, "
        f"say the day and time back to them, and say the invite and video link are "
        f"on their way to {email}. Do not read the video link out loud. "
        "Then thank them and close the call warmly."
    ), "meet_link": meet_link}


def reply_slot_gone():
    return {"booked": False, "instruction": (
        "That time was taken while you were talking. Apologise once, briefly, then "
        "call check_availability again and offer the caller the new times.")}


def reply_book_failed():
    return {"booked": False, "instruction": (
        "The booking could not be completed. Do not mention a technical problem and "
        "do not promise a specific time. Tell the caller the team will confirm by "
        "WhatsApp shortly, thank them, and close the call politely.")}
