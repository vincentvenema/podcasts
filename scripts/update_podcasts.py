#!/usr/bin/env python3
"""
update_podcasts.py

Detects new "Podcast voor de Week" picks on Adformatie's public dossier page
and adds them to podcasts.json, using only Spotify for metadata. No AI, no
Anthropic key.

For each new pick the show is looked up on Spotify (Client Credentials). If a
candidate's title is a confident match, the entry is filled from Spotify: the
show id, URL, publisher and the publisher's own description (lightly cleaned).
If there is no confident match (or the pick is not on Spotify), it is skipped
and retried next run, so nothing wrong or blank is published. Add those by hand.

Requires SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET.
"""

import base64
import datetime as dt
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

import requests
from bs4 import BeautifulSoup

DOSSIER_URL = "https://www.adformatie.nl/dossier/podcast-voor-de-week"
JSON_PATH = Path(__file__).resolve().parent.parent / "podcasts.json"

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_SEARCH_URL = "https://api.spotify.com/v1/search"

# Promo tails to trim off Spotify descriptions.
PROMO_MARKERS = [
    "See omnystudio", "Hosted on Acast", "Learn more about your ad choices",
    "Luister de hele serie", "Beluister de hele serie", "Zie het privacybeleid",
]


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def clean_title(raw: str) -> str:
    raw = re.sub(r"^\s*podcast voor de week\s*[:\-\u2013]\s*", "", raw, flags=re.I)
    return raw.strip()


def slug_from_url(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1]


def clean_description(text: str) -> str:
    text = (text or "").strip()
    for marker in PROMO_MARKERS:
        i = text.find(marker)
        if i != -1:
            text = text[:i].strip()
    return re.sub(r"\s+", " ", text).strip()


def fetch_dossier_picks() -> list:
    resp = requests.get(DOSSIER_URL, headers={"User-Agent": UA}, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    picks = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "podcast-voor-de-week-" not in href:
            continue
        url = href if href.startswith("http") else "https://www.adformatie.nl" + href
        slug = slug_from_url(url)

        title = ""
        heading = a.find(["h1", "h2", "h3"])
        if heading and heading.get_text(strip=True):
            title = heading.get_text(" ", strip=True)
        if not title:
            title = a.get_text(" ", strip=True)
        if not title:
            img = a.find("img", alt=True)
            if img:
                title = img["alt"]

        title = clean_title(title)
        if title and slug not in picks:
            picks[slug] = {"slug": slug, "title": title, "url": url}

    return list(picks.values())


def spotify_token():
    cid = os.environ.get("SPOTIFY_CLIENT_ID")
    secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    if not (cid and secret):
        print("  ! no SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET set.")
        return None
    try:
        auth = base64.b64encode(f"{cid}:{secret}".encode()).decode()
        r = requests.post(
            SPOTIFY_TOKEN_URL,
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials"},
            timeout=30,
        )
        r.raise_for_status()
        return r.json().get("access_token")
    except Exception as err:
        print(f"  ! Spotify token failed: {err}")
        return None


def spotify_match(title: str, token):
    """Return Spotify fields for a confident title match, else None."""
    if not token:
        return None
    try:
        r = requests.get(
            SPOTIFY_SEARCH_URL,
            headers={"Authorization": f"Bearer {token}"},
            params={"q": title, "type": "show", "market": "NL", "limit": 5},
            timeout=30,
        )
        r.raise_for_status()
        items = (r.json().get("shows") or {}).get("items", [])
    except Exception as err:
        print(f"  ! Spotify search failed for '{title}': {err}")
        return None

    want = normalise(title)
    for s in items:
        if not s:
            continue
        name = normalise(s.get("name", ""))
        if not name:
            continue
        # Confident match: identical, or one clearly contains the other.
        if name == want or (len(want) >= 6 and (want in name or name in want)):
            return {
                "makers": s.get("publisher") or "",
                "description": clean_description(s.get("description")),
                "spotify_id": s.get("id"),
                "spotify_url": (s.get("external_urls") or {}).get("spotify"),
                "category": "",
            }
    return None


def main() -> int:
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    weeks = data["weeks"]

    known_slugs = {w["source_slug"] for w in weeks if w.get("source_slug")}
    known_titles = {normalise(w["title"]) for w in weeks}

    picks = fetch_dossier_picks()
    if not picks:
        print("No pick cards found on the dossier page. Layout may have changed.")
        return 2

    new_picks = [
        p for p in picks
        if p["slug"] not in known_slugs and normalise(p["title"]) not in known_titles
    ]

    if not new_picks:
        print(f"No new picks. Checked {len(picks)} cards, all already in podcasts.json.")
        write_output(0)
        return 0

    today = dt.date.today()
    iso_year, iso_week, _ = today.isocalendar()
    week_label = f"{iso_year}-W{iso_week:02d}"
    token = spotify_token()

    added = 0
    for p in reversed(new_picks):
        print(f"+ new pick: {p['title']}  ({p['url']})")
        fields = spotify_match(p["title"], token)
        if fields is None or not fields["description"]:
            print(f"  - no confident Spotify match for '{p['title']}'; skipping. Add by hand if wanted.")
            continue
        entry = {
            "week": week_label,
            "date": today.isoformat(),
            "title": p["title"],
            "makers": fields["makers"],
            "description": fields["description"],
            "spotify_id": fields["spotify_id"],
            "spotify_url": fields["spotify_url"],
            "category": fields["category"],
            "source_url": p["url"],
            "source_slug": p["slug"],
        }
        weeks.insert(0, entry)
        added += 1
        print(f"  + added from Spotify: {fields['spotify_url']}")

    if added:
        data["meta"]["last_checked"] = today.isoformat()
        JSON_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    write_output(added)
    return 0


def write_output(n: int) -> None:
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"new_count={n}\n")


if __name__ == "__main__":
    sys.exit(main())
