# Mustangs sports section

Builds the weekly sports block for The Strongsville Trailhead:
last week's reported finals + the coming week's varsity schedule.

Run it (no extra Python packages needed):

    python newsletter_section.py

Writes three files to sports/dist/ — use whichever your email template wants:
  sports_section.html   ready-to-paste email HTML
  sports_section.txt    plain text
  sports_section.json   structured, if you'd rather let the curation prompt word it

Options:
  --date 2026-09-18       build as of a specific issue day
  --levels Varsity JV     include more than varsity
  --max 20                more rows before the "plus N more" line
  --offline               test without hitting the live feed

Scores: edit data/scores.csv (date,team,opponent,us,them,source,source_url).
The school isn't posting results this season, so only what you add shows up.
