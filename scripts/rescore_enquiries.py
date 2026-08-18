#!/usr/bin/env python3
"""Re-score enquiries that were saved before the spam filter existed.

Runs server.py's scorer over rows still marked 'new' and reports which ones it
would quarantine. Only content and history rules can apply — the request-shape
rules (honeypot, timing, Origin/Referer) need headers that were never recorded,
so old rows are given the benefit of the doubt on those.

    python scripts/rescore_enquiries.py            # dry run: just show the verdict
    python scripts/rescore_enquiries.py --apply    # set status='spam' on the hits

Rows already marked contacted / converted / closed are never touched: someone
has worked those, so they are real by definition.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server  # noqa: E402  (path juggling first)

APPLY = "--apply" in sys.argv


def main():
    conn = server.db()
    rows = conn.execute(
        "SELECT * FROM enquiries WHERE status='new' ORDER BY id DESC").fetchall()
    if not rows:
        print("No 'new' enquiries to check.")
        return

    hits = []
    for r in rows:
        rec = dict(r)
        score, why = server.score_enquiry(
            rec, conn,
            ip=rec.get("ip") or "",
            # Pretend the request looked fine: these rows predate header capture,
            # so scoring them on missing headers would flag every old lead.
            ua=rec.get("ua") or "Mozilla/5.0",
            origin=server.SITE_URL,
            elapsed_ms=None,
            honeypot="",
        )
        if score >= server.SPAM_THRESHOLD:
            hits.append((rec, score, "; ".join(why)))

    print(f"Checked {len(rows)} new enquiries — {len(hits)} score "
          f">= {server.SPAM_THRESHOLD} (spam):\n")
    for rec, score, why in hits:
        print(f"  #{rec['id']:<4} {score:>4}  {(rec['name'] or '')[:24]:<24} "
              f"{(rec['email'] or '')[:34]:<34} {rec['created_at'][:10]}")
        print(f"        {why}")

    if not hits:
        return
    if not APPLY:
        print("\nDry run. Re-run with --apply to move these to the Spam filter "
              "in /admin/ (nothing is deleted — you can restore any of them).")
        return

    conn.executemany(
        "UPDATE enquiries SET status='spam', spam_score=?, spam_reason=? WHERE id=?",
        [(s, w, rec["id"]) for rec, s, w in hits])
    conn.commit()
    print(f"\nMoved {len(hits)} enquiries to spam. Review them under "
          f"Enquiries > status 'Spam' in the admin panel.")
    conn.close()


if __name__ == "__main__":
    main()
