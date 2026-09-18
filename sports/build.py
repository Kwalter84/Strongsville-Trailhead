#!/usr/bin/env python3
"""
Mustangs Sports dashboard builder for The Strongsville Trailhead.

Pulls the official Strongsville athletics calendar, cleans it up, merges in
scores and highlights, and writes a single self-contained dist/index.html.

Usage:
  python build.py            # live: fetch the official ICS feed (falls back to CSV)
  python build.py --offline  # use data/schedule_snapshot.csv (for testing)

Inputs you maintain (plain CSVs, or published Google Sheets via env vars):
  data/scores.csv      date,team,opponent,us,them,source,source_url
  data/highlights.csv  date,team,title,summary,source,url
  data/times.csv       date,team,opponent,time   (use * as a wildcard)
Env vars (optional): SCORES_CSV_URL, HIGHLIGHTS_CSV_URL
"""
import csv, io, json, os, re, sys, urllib.request
from datetime import datetime, date, timezone
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data"
ICS_URL = "https://mmboltapi.azurewebsites.net/api/v2/events/calendar/2483490/0/calendar.ics"
CSV_URL = "https://www.strongsvillemustangs.org/Calendar/Schedule.csv"
UA = {"User-Agent": "StrongsvilleTrailhead/1.0 (+community newsletter)"}

SPORTS = ["Cross Country", "Football Cheer", "Basketball Cheer", "Football", "Golf",
          "Soccer", "Tennis", "Volleyball", "Basketball", "Baseball", "Softball",
          "Swimming and Diving", "Wrestling", "Ice Hockey", "Indoor Track",
          "Track and Field", "Lacrosse", "Gymnastics", "Dance", "Cheer"]

# Opponent spellings that vary inside the official feed
ALIASES = {
    "shaker hts": "Shaker Heights", "cleveland hts": "Cleveland Heights",
    "riverside": "Painesville Riverside", "painesville riverside": "Painesville Riverside",
    "glenoak": "Glen Oak", "berea-midpark": "Berea Midpark", "berea - midpark": "Berea Midpark",
    "lora": "Lorain", "massilon jackson": "Massillon Jackson",
    "hudson inv.": "Hudson Invite", "north ridgeville inv.": "North Ridgeville Invite",
    "strongsville inv.": "Strongsville Invitational", "brunswick (scrim.)": "Brunswick (scrimmage)",
    "walsh": "Walsh Jesuit", "jackson tourn.": "Jackson Tournament", "multiple": "Multi-team meet",
    "front gym": "Opponent not listed", "bnorth royalton - aack gym": "North Royalton",
    "tba": "Opponent TBA",
}

HUDL = "https://fan.hudl.com/usa/oh/strongsville/organization/8783/strongsville-high-school"


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8-sig", errors="replace")


# ---------- readers ----------
def rows_from_csv(text):
    for r in csv.DictReader(io.StringIO(text.lstrip("\ufeff"))):
        d = datetime.strptime(r["Start Date"], "%m/%d/%Y").date()
        t = r.get("Start Time", "").strip()
        # The feed uses 12:00 AM as a placeholder for "time not set"
        if r.get("All day event") == "True" or t in ("", "12:00 AM"):
            t = ""
        yield {"subject": r["Subject"].strip(), "date": d, "time": t,
               "location": r.get("Location", "").strip()}


def rows_from_ics(text):
    text = re.sub(r"\r?\n[ \t]", "", text)  # unfold lines
    for block in text.split("BEGIN:VEVENT")[1:]:
        f = {}
        for line in block.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                f[k.split(";")[0]] = v.replace("\\,", ",").replace("\\n", " ").strip()
        start = f.get("DTSTART", "")
        if not start:
            continue
        d = datetime.strptime(start[:8], "%Y%m%d").date()
        t = ""
        if "T" in start:
            dt = datetime.strptime(start[:15], "%Y%m%dT%H%M%S")
            if start.endswith("Z"):  # convert UTC to Eastern
                from zoneinfo import ZoneInfo
                dt = dt.replace(tzinfo=timezone.utc).astimezone(ZoneInfo("America/New_York"))
            t = dt.strftime("%-I:%M %p")
            if t == "12:00 AM":
                t = ""
        yield {"subject": f.get("SUMMARY", ""), "date": d, "time": t,
               "location": f.get("LOCATION", "")}


# ---------- parsing ----------
def parse_subject(subject):
    m = re.match(r"^(Boys|Girls)\s+(.*?)\s+(vs|at)\s+(.*)$", subject, re.I)
    if not m:
        return None
    gender, team_part, ha, opp = m.groups()
    sport = next((s for s in SPORTS if team_part.lower().endswith(s.lower())), None)
    if not sport:
        return None
    level_raw = team_part[: -len(sport)].strip()
    sport = "Cheer" if "Cheer" in sport else sport
    lr = level_raw.lower()
    if lr.startswith("varsity"):
        level = "Varsity"
    elif lr.startswith("jv"):
        level = "JV"
    elif lr.startswith("freshman") or lr.startswith("9th"):
        level = "Freshman"
    else:
        level = "Middle school"
    opp = re.sub(r"\s+Varsity$", "", opp.strip())
    opp = ALIASES.get(opp.lower(), opp)
    return {"team": f"{gender} {team_part}".strip(), "gender": gender.title(),
            "sport": sport, "level": level, "squad": level_raw,
            "home": ha.lower() == "vs", "opponent": opp}


def norm(s):
    return re.sub(r"[^a-z0-9]", "", ALIASES.get(s.lower(), s).lower())


def load_csv(path, env_url=None):
    if env_url and os.environ.get(env_url):
        return list(csv.DictReader(io.StringIO(fetch(os.environ[env_url]))))
    if path.exists():
        return list(csv.DictReader(path.open(encoding="utf-8")))
    return []


def build(offline=False):
    source = "snapshot"
    if offline:
        raw = list(rows_from_csv((DATA / "schedule_snapshot.csv").read_text(encoding="utf-8")))
    else:
        try:
            raw = list(rows_from_ics(fetch(ICS_URL)))
            source = "ics"
            if not raw:
                raise ValueError("empty ICS")
        except Exception as e:
            print(f"ICS failed ({e}); falling back to CSV", file=sys.stderr)
            raw = list(rows_from_csv(fetch(CSV_URL)))
            source = "csv"

    events, seen, skipped = [], {}, 0
    for r in raw:
        p = parse_subject(r["subject"])
        if not p:
            skipped += 1
            continue
        key = (p["team"].lower(), r["date"], norm(p["opponent"]))
        if key in seen:  # the feed lists many games twice
            ev = seen[key]
            ev["time"] = ev["time"] or r["time"]
            if len(r["location"]) > len(ev["location"]):
                ev["location"] = r["location"]
            continue
        ev = {**p, "date": r["date"], "time": r["time"], "location": r["location"]}
        seen[key] = ev
        events.append(ev)

    # Guard: the feed has a block of girls soccer games mislabeled as varsity football.
    gsoc = {(e["date"], norm(e["opponent"])) for e in events
            if e["team"] == "Girls Varsity Soccer"}
    before = len(events)
    events = [e for e in events if not (
        e["team"] == "Boys Varsity Football" and (e["date"], norm(e["opponent"])) in gsoc)]
    mislabeled = before - len(events)

    # Known times
    for t in load_csv(DATA / "times.csv"):
        for e in events:
            if e["time"]:
                continue
            if t["team"] != e["team"]:
                continue
            if t["date"] != "*" and t["date"] != e["date"].isoformat():
                continue
            if t["opponent"] != "*" and norm(t["opponent"]) != norm(e["opponent"]):
                continue
            e["time"] = t["time"]

    # Scores
    for s in load_csv(DATA / "scores.csv", "SCORES_CSV_URL"):
        for e in events:
            if (e["team"] == s["team"] and e["date"].isoformat() == s["date"]
                    and norm(e["opponent"]) == norm(s["opponent"])):
                us, them = int(s["us"]), int(s["them"])
                e["score"] = {"us": us, "them": them,
                              "result": "W" if us > them else "L" if us < them else "T",
                              "source": s.get("source", ""), "url": s.get("source_url", "")}

    highlights = load_csv(DATA / "highlights.csv", "HIGHLIGHTS_CSV_URL")
    highlights.sort(key=lambda h: h["date"], reverse=True)

    events.sort(key=lambda e: (e["date"], e["time"] == "", _time_key(e["time"]), e["sport"]))
    for i, e in enumerate(events):
        e["id"] = i
        e["date"] = e["date"].isoformat()

    return {
        "generated": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "source": source,
        "stats": {"raw": len(raw), "events": len(events), "unparsed": skipped,
                  "mislabeled_removed": mislabeled},
        "links": {"hudl": HUDL, "official": "https://www.strongsvillemustangs.org/calendar",
                  "tickets": "https://events.hometownticketing.com/boxoffice/strongnet/L2VtYmVkL2FsbA%3D%3D"},
        "events": events,
        "highlights": highlights,
    }


def _time_key(t):
    try:
        return datetime.strptime(t, "%I:%M %p").time().isoformat()
    except ValueError:
        return "99"


def main():
    offline = "--offline" in sys.argv
    data = build(offline)
    tpl = (ROOT / "template.html").read_text(encoding="utf-8")
    payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    html = tpl.replace("/*__DATA__*/null", payload)
    out = ROOT / "dist"
    out.mkdir(exist_ok=True)
    (out / "index.html").write_text(html, encoding="utf-8")
    (out / "data.json").write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(json.dumps(data["stats"]), "source:", data["source"])


if __name__ == "__main__":
    main()
