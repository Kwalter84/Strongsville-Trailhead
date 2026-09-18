#!/usr/bin/env python3
"""
Build the weekly "Mustangs Sports" section for The Strongsville Trailhead.

Last week's reported finals + the coming week's varsity schedule, written out
as email-ready HTML, plain text, and JSON for the curation pipeline.

Usage:
  python newsletter_section.py                    # live feed, window starts today
  python newsletter_section.py --offline          # use data/schedule_snapshot.csv
  python newsletter_section.py --date 2026-09-18  # pretend it is issue day
  python newsletter_section.py --levels Varsity JV
  python newsletter_section.py --max 14
"""
import argparse, html, json
from datetime import datetime, date, timedelta
from pathlib import Path

import build as pipeline  # reuses the feed cleaning: dedupe, mislabel guard, aliases

ROOT = Path(__file__).parent
APP = "https://www.strongsvillemustangs.org/calendar"
SKIP_SPORTS = {"Cheer"}  # cheer entries mirror the football schedule


def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def collect(args):
    data = pipeline.build(offline=args.offline)
    day0 = parse_date(args.date) if args.date else date.today()
    back, fwd = day0 - timedelta(days=7), day0 + timedelta(days=7)

    finals, upcoming = [], []
    for e in data["events"]:
        d = parse_date(e["date"])
        if e["sport"] in SKIP_SPORTS:
            continue
        if e.get("score") and back <= d <= day0:
            finals.append(e)
        elif day0 <= d <= fwd and e["level"] in args.levels:
            upcoming.append(e)

    finals.sort(key=lambda e: e["date"], reverse=True)
    extra = max(0, len(upcoming) - args.max)
    upcoming = upcoming[: args.max]
    return data, day0, finals, upcoming, extra


def label(e):
    squad = e["squad"].replace("Varsity", "varsity").replace("JV", "JV")
    return f"{e['gender']} {squad} {e['sport'].lower()}".replace("  ", " ")


def line_score(e):
    s = e["score"]
    verb = "beat" if s["result"] == "W" else "lost to" if s["result"] == "L" else "tied"
    when = parse_date(e["date"]).strftime("%A")
    return f"{label(e).capitalize()} {verb} {e['opponent']} {s['us']}-{s['them']} on {when}."


def line_game(e):
    when = parse_date(e["date"]).strftime("%a %b %-d")
    time = f", {e['time']}" if e["time"] else ""
    where = "home" if e["home"] else f"at {e['opponent']}"
    vs = f"vs {e['opponent']}" if e["home"] else f"at {e['opponent']}"
    return f"{when}{time} — {label(e)} {vs}" + (" (home)" if e["home"] else "")


def render_text(day0, finals, upcoming, extra=0):
    out = ["MUSTANGS SPORTS", ""]
    if finals:
        out.append("Last week's finals")
        out += [f"- {line_score(e)}" for e in finals]
        out.append("")
    out.append(f"This week ({day0.strftime('%b %-d')} to {(day0 + timedelta(days=7)).strftime('%b %-d')})")
    out += [f"- {line_game(e)}" for e in upcoming] or ["- No varsity games scheduled."]
    if extra:
        out.append(f"- Plus {extra} more varsity {'event' if extra == 1 else 'events'} later in the week.")
    out += ["", f"Full schedules for every team, including middle school, are in the "
                f"Strongsville Athletics app and at {APP}."]
    return "\n".join(out)


def render_html(day0, finals, upcoming, highlight=None, extra=0):
    e_ = html.escape
    p = ['<h2 style="font:700 20px Georgia,serif;color:#1B4332;margin:28px 0 10px">Mustangs Sports</h2>']
    if finals:
        p.append('<p style="font:600 14px Arial,sans-serif;color:#1B4332;margin:0 0 6px">'
                 "Last week&rsquo;s finals</p>")
        p.append('<ul style="font:15px/1.6 Arial,sans-serif;color:#222;margin:0 0 14px;padding-left:20px">')
        p += [f"<li>{e_(line_score(e))}</li>" for e in finals]
        p.append("</ul>")
    if highlight:
        p.append('<p style="font:15px/1.6 Arial,sans-serif;color:#222;margin:0 0 14px">'
                 f'{e_(highlight["summary"])} '
                 f'<a href="{e_(highlight["url"])}" style="color:#2D6A4F">Read the recap</a>.</p>')
    span = f"{day0.strftime('%b %-d')} to {(day0 + timedelta(days=7)).strftime('%b %-d')}"
    p.append('<p style="font:600 14px Arial,sans-serif;color:#1B4332;margin:0 0 6px">'
             f"This week ({e_(span)})</p>")
    if upcoming:
        p.append('<table role="presentation" cellpadding="0" cellspacing="0" '
                 'style="font:15px/1.5 Arial,sans-serif;color:#222;margin:0 0 12px;width:100%">')
        for e in upcoming:
            when = parse_date(e["date"]).strftime("%a %b %-d")
            time = e["time"] or "Time TBA"
            vs = ("vs " if e["home"] else "at ") + e["opponent"]
            bg = "#F2F7F3" if e["home"] else "#FFFFFF"
            p.append(f'<tr style="background:{bg}">'
                     f'<td style="padding:6px 8px;white-space:nowrap;width:1%"><b>{e_(when)}</b><br>'
                     f'<span style="color:#5B6B61;font-size:13px">{e_(time)}</span></td>'
                     f'<td style="padding:6px 8px">{e_(label(e))}<br>'
                     f'<b>{e_(vs)}</b>{" &middot; home" if e["home"] else ""}</td></tr>')
        p.append("</table>")
        if extra:
            p.append('<p style="font:14px/1.5 Arial,sans-serif;color:#5B6B61;margin:0 0 10px">'
                     f"Plus {extra} more varsity {'event' if extra == 1 else 'events'} later in the week.</p>")
    else:
        p.append('<p style="font:15px/1.6 Arial,sans-serif;color:#222">No varsity games scheduled.</p>')
    p.append('<p style="font:13px/1.5 Arial,sans-serif;color:#5B6B61;margin:0">'
             "Shaded rows are home games. Full schedules for every team, including middle school, "
             f'are in the Strongsville Athletics app and at <a href="{APP}" style="color:#2D6A4F">'
             "strongsvillemustangs.org</a>.</p>")
    return "\n".join(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--date")
    ap.add_argument("--levels", nargs="+", default=["Varsity"])
    ap.add_argument("--max", type=int, default=16)
    args = ap.parse_args()

    data, day0, finals, upcoming, extra = collect(args)
    hl = next((h for h in data.get("highlights", [])
               if (day0 - timedelta(days=7)).isoformat() <= h["date"] <= day0.isoformat()), None)

    out = ROOT / "dist"
    out.mkdir(exist_ok=True)
    text = render_text(day0, finals, upcoming, extra)
    (out / "sports_section.txt").write_text(text, encoding="utf-8")
    (out / "sports_section.html").write_text(render_html(day0, finals, upcoming, hl, extra), encoding="utf-8")
    (out / "sports_section.json").write_text(json.dumps({
        "issue_date": day0.isoformat(),
        "finals": [{"team": label(e), "opponent": e["opponent"], **e["score"], "date": e["date"]} for e in finals],
        "upcoming": [{"team": label(e), "opponent": e["opponent"], "home": e["home"],
                      "date": e["date"], "time": e["time"], "location": e["location"]} for e in upcoming],
        "highlight": hl,
    }, indent=1), encoding="utf-8")
    print(text)
    print(f"\n[{len(finals)} finals, {len(upcoming)} games, source: {data['source']}]")


if __name__ == "__main__":
    main()
