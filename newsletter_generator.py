"""
STRONGSVILLE TRAILHEAD NEWSLETTER — weekly generator + sender
---------------------------------------------------------------
Run weekly (via GitHub Actions cron). This script:
  1. Pulls recent local stories/events from RSS sources covering Strongsville, OH
  2. Sends them to Claude to select only genuinely positive / uplifting /
     family-and-kids-relevant items, and to sort them into sections
  3. Renders a branded HTML email
  4. Fetches the subscriber list from the Google Apps Script backend
  5. Sends the issue via SendGrid

Required environment variables (set as GitHub Actions secrets):
  ANTHROPIC_API_KEY   - Claude API key
  SENDGRID_API_KEY    - SendGrid API key
  SENDER_EMAIL        - verified SendGrid sender address, e.g. news@yourdomain.com
  APPS_SCRIPT_URL      - your deployed Google Apps Script Web App URL
  APPS_SCRIPT_SECRET   - the SECRET_KEY you set in Code.gs
"""

import os
import json
import time
import datetime
import feedparser
import requests
from anthropic import Anthropic

# ---------------------------------------------------------------------------
# 1. SOURCES
# ---------------------------------------------------------------------------
# Google News RSS search is the most reliable way to get fresh, indexed
# stories about Strongsville without depending on any one outlet's own feed
# (many local outlets don't maintain working RSS feeds).

RSS_SOURCES = [
    # General Strongsville news
    "https://news.google.com/rss/search?q=Strongsville+Ohio+when:10d&hl=en-US&gl=US&ceid=US:en",
    # Explicitly family/kids/events angle
    "https://news.google.com/rss/search?q=Strongsville+Ohio+(family+OR+kids+OR+event+OR+festival+OR+school)+when:10d&hl=en-US&gl=US&ceid=US:en",
    # City of Strongsville official announcements
    "https://news.google.com/rss/search?q=site:strongsville.org+when:14d&hl=en-US&gl=US&ceid=US:en",
    # Strongsville City Schools
    "https://news.google.com/rss/search?q=%22Strongsville+City+Schools%22+when:14d&hl=en-US&gl=US&ceid=US:en",
    # Regional day-trip-distance events (Greater Cleveland area, roughly 30-45 min drive)
    "https://news.google.com/rss/search?q=(Cleveland+OR+%22Cuyahoga+County%22+OR+%22North+Olmsted%22+OR+%22Medina+Ohio%22+OR+%22Berea+Ohio%22+OR+%22Brunswick+Ohio%22)+(festival+OR+fair+OR+event+OR+%22open+this+weekend%22)+when:9d&hl=en-US&gl=US&ceid=US:en",
    # Kid-friendly / family video game news
    "https://news.google.com/rss/search?q=(%22family+friendly%22+OR+%22kids%22+OR+%22all+ages%22)+(video+game+OR+Nintendo+OR+%22new+game+release%22)+when:9d&hl=en-US&gl=US&ceid=US:en",
    # Strongsville Patch
    "https://news.google.com/rss/search?q=site:patch.com+Strongsville+when:14d&hl=en-US&gl=US&ceid=US:en",
    # cleveland.com coverage of Strongsville
    "https://news.google.com/rss/search?q=site:cleveland.com+Strongsville+when:14d&hl=en-US&gl=US&ceid=US:en",
    # News 5 Cleveland (WEWS) coverage of Strongsville
    "https://news.google.com/rss/search?q=site:news5cleveland.com+Strongsville+when:14d&hl=en-US&gl=US&ceid=US:en",
    # Fox8 Cleveland coverage of Strongsville
    "https://news.google.com/rss/search?q=site:fox8.com+Strongsville+when:14d&hl=en-US&gl=US&ceid=US:en",
    # WKYC coverage of Strongsville
    "https://news.google.com/rss/search?q=site:wkyc.com+Strongsville+when:14d&hl=en-US&gl=US&ceid=US:en",
    # Strongsville Chamber of Commerce
    "https://news.google.com/rss/search?q=%22Strongsville+Chamber%22+when:21d&hl=en-US&gl=US&ceid=US:en",
]

MAX_ITEMS_TO_SEND_TO_CLAUDE = 100


FEED_HINTS = {
    4: "regional_event",  # index of the day-trip-distance events feed above
    5: "kids_gaming",     # index of the family/kids gaming feed above
}


def fetch_raw_items():
    items = []
    seen_links = set()
    for idx, url in enumerate(RSS_SOURCES):
        feed = feedparser.parse(url)
        for entry in feed.entries:
            link = entry.get("link", "")
            if link in seen_links:
                continue
            seen_links.add(link)
            items.append({
                "title": entry.get("title", "").strip(),
                "summary": entry.get("summary", "")[:500],
                "link": link,
                "published": entry.get("published", ""),
                "source": "rss",
                "feed_hint": FEED_HINTS.get(idx, ""),
            })
    return items[:MAX_ITEMS_TO_SEND_TO_CLAUDE]


def fetch_reader_tips():
    """Reader-submitted tips (via the Google Form linked to the Tips sheet).
    This is how things people see on Facebook groups/Pages make it into the
    newsletter, since Facebook itself can't be scraped or fetched directly."""
    url = os.environ["APPS_SCRIPT_URL"]
    key = os.environ["APPS_SCRIPT_SECRET"]
    headers = {"User-Agent": "Mozilla/5.0 (compatible; StrongsvilleTrailhead/1.0)"}
    try:
        resp = requests.get(url, params={"key": key, "type": "tips"}, headers=headers, timeout=30, allow_redirects=True)
        data = resp.json()
        if not data.get("success"):
            print(f"  Warning: could not fetch tips ({data})")
            return []
        return [
            {
                "title": t["tip"],
                "summary": f"Reader-submitted tip (via {t.get('submitted_by') or 'anonymous'})",
                "link": t.get("link", ""),
                "published": "",
                "source": "reader_tip",
            }
            for t in data.get("tips", [])
        ]
    except Exception as e:
        print(f"  Warning: tips fetch failed ({e})")
        return []


# ---------------------------------------------------------------------------
# 2. CLAUDE: FILTER + CATEGORIZE + WRITE
# ---------------------------------------------------------------------------

CURATION_PROMPT = """You are curating a weekly community newsletter called "The Strongsville Trailhead"
for residents of Strongsville, Ohio. The newsletter's entire purpose is to be a genuinely
positive, uplifting counterpoint to normal local news. Families with young kids are a
core audience.

Below is a list of raw headlines/snippets pulled from news feeds covering Strongsville.

Your job:
1. SELECT items that are genuinely positive, uplifting, constructive, OR simply pleasant/neutral
   local-interest news - for example a new business opening, a completed road or park project, an
   upcoming event, a school achievement, a local sports win. You do NOT need a story to be dramatically
   inspiring to include it - ordinary good local news counts (this is meant to feel like "here's
   what's going on in town that's worth knowing," not just headline-grabbing feel-good stories).
   REJECT: crime, accidents, political conflict/controversy, obituaries, complaints, lawsuits,
   anything negative or divisive, and anything not actually about Strongsville/the local area
   (except the day_trip_events and kids_gaming categories, which are intentionally broader - see below).
   When in doubt about whether an item is "positive enough," err on the side of including it if it's
   simply neutral/informative local news rather than negative.
2. SORT each selected item into exactly one category:
   - "community_wins" (good things happening in town, volunteering, civic good news, local achievements)
   - "work_business" (local business openings, workforce/economic good news, job fairs)
   - "family_kids" (specific events, activities, or things to do with kids/families IN Strongsville itself)
   - "school_youth" (student/school achievements, youth sports, scouts, etc.)
   - "day_trip_events" (events, festivals, fairs, or things to do within roughly a 30-45 minute drive
     of Strongsville - Greater Cleveland area, Medina, Berea, Brunswick, North Olmsted, etc. - worth a
     family day trip, but NOT in Strongsville itself)
   - "kids_gaming" (new video game releases, updates, or gaming news that's specifically family-friendly
     or kid-appropriate - e.g. Nintendo, all-ages titles. REJECT anything violent, mature-rated, or not
     genuinely kid-appropriate, even if it's popular)
   Items with "feed_hint": "regional_event" are likely day_trip_events; items with
   "feed_hint": "kids_gaming" are likely kids_gaming - but still use judgment, don't sort on the hint alone.
3. For each selected item, write ONE clean, warm, plain-English sentence summary
   (do not copy the original headline verbatim - rewrite it in your own words).
   Items with "source": "reader_tip" came from a neighbor (often something they saw
   on a local Facebook group/Page) - treat these as trustworthy leads, but if the
   tip text is vague, still summarize only what's actually stated; don't invent details.
   For "day_trip_events", briefly note roughly how far/what area it's in.
   For "kids_gaming", briefly note the platform and why it's good for kids (age range if known).
4. Also write 2-3 short original "Weekend Ideas for Young Families" suggestions —
   general, evergreen ideas for family activities in Strongsville
   (e.g. Cleveland Metroparks Mill Stream Run Reservation trails, SouthPark Mall play areas,
   Strongsville branch library storytimes, Ehrnfelt Recreation Center, local splash pads/parks)
   appropriate for the current season. These should NOT be copied from any source - write
   them yourself as genuinely useful local suggestions.

Return ONLY valid JSON (no markdown fences, no preamble) in this exact shape:
{
  "community_wins": [{"summary": "...", "link": "..."}],
  "work_business": [{"summary": "...", "link": "..."}],
  "family_kids": [{"summary": "...", "link": "..."}],
  "school_youth": [{"summary": "...", "link": "..."}],
  "day_trip_events": [{"summary": "...", "link": "..."}],
  "kids_gaming": [{"summary": "...", "link": "..."}],
  "weekend_ideas": ["...", "...", "..."]
}

If a category has no genuinely good items this week, return an empty array for it - never
force in something negative or unrelated just to fill a section.

RAW ITEMS:
{items_json}
"""


def curate_with_claude(raw_items):
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    prompt = CURATION_PROMPT.replace("{items_json}", json.dumps(raw_items, indent=2))

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    text = text.replace("```json", "").replace("```", "").strip()
    return json.loads(text)


# ---------------------------------------------------------------------------
# 3. RENDER HTML EMAIL
# ---------------------------------------------------------------------------

def render_section(title, emoji, items):
    if not items:
        return ""
    rows = ""
    for item in items:
        link = item.get("link", "")
        rows += f"""
        <tr>
          <td style="padding:14px 0; border-bottom:1px solid #e7e0cf;">
            <p style="margin:0; font-size:15px; color:#1B241E; line-height:1.5;">{item['summary']}</p>
            {f'<a href="{link}" style="font-size:13px; color:#B4472F; text-decoration:none;">Read more &rarr;</a>' if link else ''}
          </td>
        </tr>"""
    return f"""
    <tr><td style="padding:32px 0 8px;">
      <p style="margin:0; font-family:Georgia, serif; font-size:20px; font-weight:700; color:#153328;">{emoji} {title}</p>
    </td></tr>
    <tr><td><table width="100%" cellpadding="0" cellspacing="0">{rows}</table></td></tr>
    """


def render_weekend_ideas(ideas):
    if not ideas:
        return ""
    lis = "".join(f'<li style="margin-bottom:8px; color:#1B241E; font-size:15px;">{idea}</li>' for idea in ideas)
    return f"""
    <tr><td style="padding:24px 24px; background:#EFE9D8; border-radius:6px;">
      <p style="margin:0 0 10px; font-family:Georgia, serif; font-size:18px; font-weight:700; color:#153328;">🏞️ Weekend Ideas for Young Families</p>
      <ul style="padding-left:20px; margin:0;">{lis}</ul>
    </td></tr>
    """


def build_html(curated):
    date_str = datetime.date.today().strftime("%B %d, %Y")
    sections = (
        render_section("Community Wins", "🌳", curated.get("community_wins", []))
        + render_section("Work & Local Business", "💼", curated.get("work_business", []))
        + render_section("Family & Kids Corner", "🧒", curated.get("family_kids", []))
        + render_section("School & Youth Achievements", "🎓", curated.get("school_youth", []))
        + render_section("Worth the Drive — Day Trip Events", "🚗", curated.get("day_trip_events", []))
        + render_section("Kids' Gaming Corner", "🎮", curated.get("kids_gaming", []))
    )
    weekend = render_weekend_ideas(curated.get("weekend_ideas", []))

    return f"""<!DOCTYPE html>
<html><body style="margin:0; padding:0; background:#F7F1E3; font-family:'Source Sans Pro', Arial, sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F7F1E3;">
<tr><td align="center" style="padding:40px 16px;">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px; width:100%;">

  <tr><td style="background:#153328; padding:36px 32px; border-radius:6px 6px 0 0; text-align:center;">
    <p style="margin:0 0 6px; color:#D9A441; letter-spacing:2px; font-size:11px; font-weight:700; text-transform:uppercase;">The Strongsville Trailhead</p>
    <p style="margin:0; color:#F7F1E3; font-size:14px;">{date_str} &middot; Good news only</p>
  </td></tr>

  <tr><td style="background:#ffffff; padding:8px 32px 32px;">
    <table width="100%" cellpadding="0" cellspacing="0">
      {sections}
      {weekend}
    </table>
  </td></tr>

  <tr><td style="padding:20px 32px 0; text-align:center;">
    <table width="100%" cellpadding="0" cellspacing="0" style="border-top:1px solid #e7e0cf; padding-top:20px;">
      <tr><td style="text-align:center; padding-top:20px;">
        <p style="margin:0; font-size:13px; color:#6b7469;">This newsletter is brought to you by</p>
        <p style="margin:4px 0 2px;"><a href="https://fixa.house" style="color:#B4472F; font-weight:700; font-size:15px; text-decoration:none;">Fixa House</a></p>
        <p style="margin:0; font-size:12px; color:#6b7469; max-width:380px; margin-left:auto; margin-right:auto;">Free home repair cost estimates and a list of qualified Strongsville contractors, sent straight to your inbox.</p>
      </td></tr>
    </table>
  </td></tr>

  <tr><td style="padding:12px 32px 24px; text-align:center; color:#6b7469; font-size:12px;">
    Made for neighbors, by neighbors, in Strongsville, OH.<br>
    You're getting this because you signed up at the Trailhead. Reply to unsubscribe.
  </td></tr>

</table>
</td></tr>
</table>
</body></html>"""


# ---------------------------------------------------------------------------
# 4. SUBSCRIBERS
# ---------------------------------------------------------------------------

def get_subscribers():
    url = os.environ["APPS_SCRIPT_URL"]
    key = os.environ["APPS_SCRIPT_SECRET"]
    headers = {"User-Agent": "Mozilla/5.0 (compatible; StrongsvilleTrailhead/1.0)"}

    last_error = None
    for attempt in range(3):
        resp = requests.get(url, params={"key": key}, headers=headers, timeout=30, allow_redirects=True)
        print(f"  Subscriber fetch attempt {attempt + 1} status code: {resp.status_code}")
        try:
            data = resp.json()
            if data.get("success"):
                return data["emails"]
            last_error = RuntimeError(f"Failed to fetch subscribers: {data}")
        except requests.exceptions.JSONDecodeError:
            print("  Response was not valid JSON. First 300 chars:")
            print(resp.text[:300])
            last_error = RuntimeError("Apps Script returned non-JSON response")

        if attempt < 2:
            print("  Retrying in 5 seconds...")
            time.sleep(5)

    raise last_error


# ---------------------------------------------------------------------------
# 5. SEND VIA SENDGRID
# ---------------------------------------------------------------------------

def send_newsletter(html, subscribers):
    api_key = os.environ["SENDGRID_API_KEY"]
    sender = os.environ["SENDER_EMAIL"]
    subject = f"The Strongsville Trailhead — {datetime.date.today().strftime('%B %d, %Y')}"

    if not subscribers:
        print("No subscribers yet — skipping send.")
        return

    payload = {
        "personalizations": [{"to": [{"email": email}]} for email in subscribers],
        "from": {"email": sender, "name": "The Strongsville Trailhead"},
        "subject": subject,
        "content": [{"type": "text/html", "value": html}],
    }
    # SendGrid personalizations each get their own "to" but share subject/content,
    # which keeps this simple and avoids exposing subscriber emails to each other.
    resp = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    print(f"SendGrid response: {resp.status_code}")
    if resp.status_code >= 300:
        print(resp.text)
        resp.raise_for_status()


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    print("Fetching raw local news items...")
    raw_items = fetch_raw_items()
    print(f"  {len(raw_items)} raw items pulled from RSS")

    print("Fetching reader-submitted tips...")
    tips = fetch_reader_tips()
    print(f"  {len(tips)} reader tips pulled")
    raw_items += tips

    print("Curating with Claude...")
    curated = curate_with_claude(raw_items)
    total = sum(len(v) for k, v in curated.items() if k != "weekend_ideas")
    print(f"  {total} items selected as genuinely positive")

    print("Building HTML...")
    html = build_html(curated)

    # Save a local copy for review/debugging every run
    with open("latest_issue.html", "w") as f:
        f.write(html)

    print("Fetching subscriber list...")
    subscribers = get_subscribers()
    print(f"  {len(subscribers)} subscribers")

    print("Sending...")
    send_newsletter(html, subscribers)
    print("Done.")


if __name__ == "__main__":
    main()
