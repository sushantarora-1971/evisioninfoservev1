#!/usr/bin/env python3
"""Sync live facts from the codebase into the Obsidian vault's topic notes.

Replaces only the content inside <!-- AUTO:<key> start -->...<!-- AUTO:<key> end -->
markers, so hand-written prose is never touched. Runs from the Claude Code Stop
hook (see .claude/settings.json) so the vault refreshes whenever code changes.
Safe to run anytime; idempotent; exits quietly if the vault isn't present.
"""
import os
import re
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # project dir
VAULT = os.path.join(os.path.dirname(ROOT), "EvisionInfoserve-Vault")


def read(rel):
    try:
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def first(pattern, text, default="—"):
    m = re.search(pattern, text)
    return m.group(1) if m else default


def set_block(note, key, body):
    """Replace text between the AUTO:<key> markers inside a vault note."""
    path = os.path.join(VAULT, note)
    try:
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
    except OSError:
        return False
    start, end = f"<!-- AUTO:{key} start -->", f"<!-- AUTO:{key} end -->"
    if start not in content or end not in content:
        return False
    new = start + "\n" + body.rstrip() + "\n" + end
    content = re.sub(re.escape(start) + r".*?" + re.escape(end), new, content, flags=re.S)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return True


def main():
    if not os.path.isdir(VAULT):
        return
    server = read("server.py")
    pricing = read("pricing.html")
    index = read("index.html")
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── Contact (from server.py brand constants) ──
    phone = first(r'BRAND_PHONE\s*=\s*"([^"]+)"', server)
    email = first(r'BRAND_EMAIL\s*=\s*"([^"]+)"', server)
    set_block("Brand & Contact.md", "contact",
              f"**Live from code:** 📞 {phone} · ✉️ {email}  \n"
              f"<sub>auto-synced {stamp}</sub>")

    # ── Pricing (entry + Grow, from the pages) ──
    entry = first(r'pk-price">₹([\d,]+)<small>\s*one-time', index,
                  first(r'price-amt">₹([\d,]+)</span>', pricing))
    grow = first(r'data-monthly="([\d,]+)"', pricing)
    set_block("Pricing & Packages.md", "pricing",
              f"> **Live prices from code:** Launch from **₹{entry}** one-time · "
              f"Grow **₹{grow}/mo**.  <sub>auto-synced {stamp}</sub>")

    # ── Routes (count of public clean URLs from FILE_TO_CLEAN) ──
    routes = re.findall(r'"[a-z0-9-]+\.html":\s*"(/[^"]*)"', server)
    seg = sorted(set(routes))
    sample = ", ".join(f"`{r}`" for r in seg[:8])
    set_block("Site Architecture.md", "routes",
              f"> **{len(seg)} public clean URLs** served (from `FILE_TO_CLEAN`), e.g. "
              f"{sample} …  <sub>auto-synced {stamp}</sub>")

    # ── SEO feature checklist (presence in code) ──
    def yn(ok):
        return "✅" if ok else "❌"
    checks = [
        ("Server-side head injection (`inject_seo`)", "def inject_seo" in server),
        ("`/llms.txt` route", "/llms.txt" in server),
        ("AI crawlers welcomed in robots (GPTBot/ClaudeBot…)", "GPTBot" in server),
        ("Branded OG image", os.path.exists(os.path.join(ROOT, "assets", "og-default.png"))),
        ("FAQPage schema (home)", "HOME_FAQ" in server),
        ("LocalBusiness schema", "ProfessionalService" in server),
    ]
    body = "> **SEO/AEO features present in code:**\n" + "\n".join(
        f"> - {yn(ok)} {label}" for label, ok in checks
    ) + f"\n> <sub>auto-synced {stamp}</sub>"
    set_block("SEO & AEO.md", "seo", body)

    print(f"[update_vault] synced code facts -> vault ({stamp})")


if __name__ == "__main__":
    main()
